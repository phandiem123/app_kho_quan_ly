from __future__ import annotations
from dataclasses import dataclass, field
import database

_TX = {
    "to_unit":     "XUAT_KHO",
    "shared_loan": "MUON",
}


@dataclass
class IssueLine:
    item_type_id: int
    item_code: str
    item_name: str
    unit_of_measure: str
    quantity: int
    unit_price: float = 0.0
    quality_level: str = "H1"
    notes: str = ""
    id: int | None = None


@dataclass
class Issue:
    id: int | None
    reference_number: str
    from_warehouse_id: int
    from_warehouse_name: str
    to_warehouse_id: int | None
    to_warehouse_name: str
    transaction_date: str
    tx_type: str = "XUAT_KHO"
    recipient: str = ""
    created_by: str = ""
    transporter: str = ""
    notes: str = ""
    line_count: int = 0
    status: str = ""
    lines: list[IssueLine] = field(default_factory=list)

    @property
    def subtype(self) -> str:
        return "shared_loan" if self.tx_type == "MUON" else "to_unit"


def get_all(year: int | None = None, subtype: str = "to_unit") -> list[Issue]:
    conn = database.get_conn()
    tx_type = _TX[subtype]
    clauses = [f"t.type = '{tx_type}'"]
    params: list = []
    if year:
        clauses.append("strftime('%Y', t.transaction_date) = ?")
        params.append(str(year))
    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(f"""
        SELECT t.id, t.type AS tx_type, t.reference_number,
               t.from_warehouse_id, wfrom.name AS from_warehouse_name,
               t.to_warehouse_id,   wto.name   AS to_warehouse_name,
               t.transaction_date, t.supplier AS recipient,
               t.created_by, t.transporter, t.notes,
               COUNT(tl.id) AS line_count
        FROM transactions t
        LEFT JOIN warehouses wfrom ON wfrom.id = t.from_warehouse_id
        LEFT JOIN warehouses wto   ON wto.id   = t.to_warehouse_id
        LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.transaction_date DESC, t.id DESC
    """, params).fetchall()
    issues = [
        Issue(
            id=r["id"],
            tx_type=r["tx_type"],
            reference_number=r["reference_number"] or "",
            from_warehouse_id=r["from_warehouse_id"] or 0,
            from_warehouse_name=r["from_warehouse_name"] or "",
            to_warehouse_id=r["to_warehouse_id"],
            to_warehouse_name=r["to_warehouse_name"] or "",
            transaction_date=r["transaction_date"] or "",
            recipient=r["recipient"] or "",
            created_by=r["created_by"] or "",
            transporter=r["transporter"] or "",
            notes=r["notes"] or "",
            line_count=r["line_count"] or 0,
        )
        for r in rows
    ]
    if subtype == "shared_loan" and issues:
        statuses = _batch_status(conn, issues)
        for iss in issues:
            iss.status = statuses.get(iss.id, "Đã xuất")
    return issues


def _batch_status(conn, issues: list[Issue]) -> dict[int, str]:
    """Compute phiếu status for a list of MUON issues in minimal queries."""
    ids = [i.id for i in issues]
    ph = ",".join("?" * len(ids))

    # Quantities loaned per (tx_id, item_type_id)
    loaned_rows = conn.execute(
        f"SELECT transaction_id, item_type_id, SUM(quantity) AS qty "
        f"FROM transaction_lines WHERE transaction_id IN ({ph}) "
        f"GROUP BY transaction_id, item_type_id",
        ids,
    ).fetchall()
    loaned: dict[int, dict[int, int]] = {}
    for r in loaned_rows:
        loaned.setdefault(r["transaction_id"], {})[r["item_type_id"]] = r["qty"]

    returned: dict[int, dict[int, int]] = {}

    # Event loans: linked via loan_transaction_id on TRA transactions
    event_ids = [i.id for i in issues if i.to_warehouse_id is None]
    if event_ids:
        eph = ",".join("?" * len(event_ids))
        ev_rows = conn.execute(
            f"SELECT t.loan_transaction_id AS muon_id, tl.item_type_id, SUM(tl.quantity) AS qty "
            f"FROM transactions t JOIN transaction_lines tl ON tl.transaction_id = t.id "
            f"WHERE t.type = 'TRA' AND t.loan_transaction_id IN ({eph}) "
            f"GROUP BY t.loan_transaction_id, tl.item_type_id",
            event_ids,
        ).fetchall()
        for r in ev_rows:
            returned.setdefault(r["muon_id"], {})[r["item_type_id"]] = r["qty"]

    # Unit loans: match by (from_wh → to_wh) warehouse pair
    unit_pairs: dict[tuple, list[int]] = {}
    for i in issues:
        if i.to_warehouse_id is not None:
            unit_pairs.setdefault(
                (i.to_warehouse_id, i.from_warehouse_id), []
            ).append(i.id)

    for (to_wh, from_wh), issue_ids in unit_pairs.items():
        ret_rows = conn.execute(
            "SELECT tl.item_type_id, SUM(tl.quantity) AS qty "
            "FROM transactions t JOIN transaction_lines tl ON tl.transaction_id = t.id "
            "WHERE t.type = 'TRA' AND t.from_warehouse_id = ? AND t.to_warehouse_id = ? "
            "GROUP BY tl.item_type_id",
            (to_wh, from_wh),
        ).fetchall()
        if ret_rows:
            ret_map = {r["item_type_id"]: r["qty"] for r in ret_rows}
            for iid in issue_ids:
                returned[iid] = ret_map

    result: dict[int, str] = {}
    for iss in issues:
        iss_loaned = loaned.get(iss.id, {})
        iss_returned = returned.get(iss.id, {})
        if not iss_returned:
            result[iss.id] = "Đã xuất"
        elif all(iss_returned.get(k, 0) >= v for k, v in iss_loaned.items()):
            result[iss.id] = "Hoàn thành"
        else:
            result[iss.id] = "Chưa trả hết"
    return result


def get_loan_events() -> list[dict]:
    """Return all MUON-to-event transactions for populating the event dropdown."""
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT t.id, t.reference_number, t.supplier, t.transaction_date,
               wfrom.name AS from_warehouse_name
        FROM transactions t
        LEFT JOIN warehouses wfrom ON wfrom.id = t.from_warehouse_id
        WHERE t.type = 'MUON' AND t.to_warehouse_id IS NULL
          AND t.supplier IS NOT NULL AND TRIM(t.supplier) != ''
        ORDER BY t.transaction_date DESC, t.id DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_lines(transaction_id: int) -> list[IssueLine]:
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT tl.id, tl.item_type_id, it.code AS item_code,
               it.name AS item_name, it.unit_of_measure,
               tl.quantity, tl.unit_price, tl.notes, tl.quality_level_to
        FROM transaction_lines tl
        JOIN item_types it ON it.id = tl.item_type_id
        WHERE tl.transaction_id = ?
        ORDER BY tl.id
    """, (transaction_id,)).fetchall()
    return [
        IssueLine(
            id=r["id"],
            item_type_id=r["item_type_id"],
            item_code=r["item_code"] or "",
            item_name=r["item_name"] or "",
            unit_of_measure=r["unit_of_measure"] or "",
            quantity=r["quantity"],
            unit_price=float(r["unit_price"] or 0),
            notes=r["notes"] or "",
            quality_level=r["quality_level_to"] or "H1",
        )
        for r in rows
    ]


def _dec_inv_tong(conn, wh_id, item_type_id, qty, quality_level: str = "H1"):
    conn.execute("""
        UPDATE inventory SET quantity = MAX(0, quantity - ?)
        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
          AND received_at_unit_date IS NULL AND is_shared=0
    """, (qty, wh_id, item_type_id, quality_level))


def _add_inv_at_unit(conn, wh_id, item_type_id, qty, date, quality_level: str = "H1"):
    row = conn.execute("""
        SELECT id FROM inventory
        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
          AND received_at_unit_date=? AND is_shared=0
        LIMIT 1
    """, (wh_id, item_type_id, quality_level, date)).fetchone()
    if row:
        conn.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?",
                     (qty, row["id"]))
    else:
        conn.execute("""
            INSERT INTO inventory
                (warehouse_id, item_type_id, quality_level, quantity, received_at_unit_date)
            VALUES (?, ?, ?, ?, ?)
        """, (wh_id, item_type_id, quality_level, qty, date))


def insert(issue: Issue) -> int:
    conn = database.get_conn()
    cur = conn.execute("""
        INSERT INTO transactions
            (type, reference_number, from_warehouse_id, to_warehouse_id,
             transaction_date, supplier, created_by, transporter, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (_TX[issue.subtype], issue.reference_number,
          issue.from_warehouse_id, issue.to_warehouse_id,
          issue.transaction_date, issue.recipient,
          issue.created_by, issue.transporter, issue.notes))
    tx_id = cur.lastrowid

    for line in issue.lines:
        ql = line.quality_level or "H1"
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, unit_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tx_id, line.item_type_id, ql, ql, line.quantity, line.unit_price, line.notes))

        if issue.subtype == "to_unit":
            _dec_inv_tong(conn, issue.from_warehouse_id, line.item_type_id, line.quantity, ql)
            if issue.to_warehouse_id:
                _add_inv_at_unit(conn, issue.to_warehouse_id, line.item_type_id,
                                 line.quantity, issue.transaction_date, ql)
        elif issue.subtype == "shared_loan":
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                  AND received_at_unit_date IS NULL
            """, (line.quantity, issue.from_warehouse_id, line.item_type_id))

    conn.commit()
    return tx_id


def update(issue: Issue) -> None:
    conn = database.get_conn()
    old = conn.execute(
        "SELECT from_warehouse_id, to_warehouse_id, type FROM transactions WHERE id=?",
        (issue.id,)
    ).fetchone()
    if old:
        old_subtype = "shared_loan" if old["type"] == "MUON" else "to_unit"
        for line in get_lines(issue.id):
            ql = line.quality_level or "H1"
            if old_subtype == "to_unit":
                if old["from_warehouse_id"]:
                    conn.execute("""
                        UPDATE inventory SET quantity = quantity + ?
                        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                          AND received_at_unit_date IS NULL AND is_shared=0
                    """, (line.quantity, old["from_warehouse_id"], line.item_type_id, ql))
                if old["to_warehouse_id"]:
                    conn.execute("""
                        UPDATE inventory SET quantity = MAX(0, quantity - ?)
                        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                    """, (line.quantity, old["to_warehouse_id"], line.item_type_id, ql))
            elif old_subtype == "shared_loan" and old["from_warehouse_id"]:
                conn.execute("""
                    UPDATE inventory SET quantity = quantity + ?
                    WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                      AND received_at_unit_date IS NULL
                """, (line.quantity, old["from_warehouse_id"], line.item_type_id))

    conn.execute("""
        UPDATE transactions SET
            type=?, reference_number=?, from_warehouse_id=?, to_warehouse_id=?,
            transaction_date=?, supplier=?, created_by=?, transporter=?, notes=?
        WHERE id=?
    """, (_TX[issue.subtype], issue.reference_number,
          issue.from_warehouse_id, issue.to_warehouse_id,
          issue.transaction_date, issue.recipient,
          issue.created_by, issue.transporter, issue.notes, issue.id))
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (issue.id,))

    for line in issue.lines:
        ql = line.quality_level or "H1"
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, unit_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (issue.id, line.item_type_id, ql, ql, line.quantity, line.unit_price, line.notes))

        if issue.subtype == "to_unit":
            _dec_inv_tong(conn, issue.from_warehouse_id, line.item_type_id, line.quantity, ql)
            if issue.to_warehouse_id:
                _add_inv_at_unit(conn, issue.to_warehouse_id, line.item_type_id,
                                 line.quantity, issue.transaction_date, ql)
        elif issue.subtype == "shared_loan":
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                  AND received_at_unit_date IS NULL
            """, (line.quantity, issue.from_warehouse_id, line.item_type_id))

    conn.commit()


def delete(issue_id: int) -> None:
    conn = database.get_conn()
    old = conn.execute(
        "SELECT from_warehouse_id, to_warehouse_id, type FROM transactions WHERE id=?",
        (issue_id,)
    ).fetchone()
    if old:
        subtype = "shared_loan" if old["type"] == "MUON" else "to_unit"
        for line in get_lines(issue_id):
            ql = line.quality_level or "H1"
            if subtype == "to_unit":
                if old["from_warehouse_id"]:
                    conn.execute("""
                        UPDATE inventory SET quantity = quantity + ?
                        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                          AND received_at_unit_date IS NULL AND is_shared=0
                    """, (line.quantity, old["from_warehouse_id"], line.item_type_id, ql))
                if old["to_warehouse_id"]:
                    conn.execute("""
                        UPDATE inventory SET quantity = MAX(0, quantity - ?)
                        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                    """, (line.quantity, old["to_warehouse_id"], line.item_type_id, ql))
            elif subtype == "shared_loan" and old["from_warehouse_id"]:
                conn.execute("""
                    UPDATE inventory SET quantity = quantity + ?
                    WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                      AND received_at_unit_date IS NULL
                """, (line.quantity, old["from_warehouse_id"], line.item_type_id))

    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (issue_id,))
    conn.execute("DELETE FROM transactions WHERE id=?", (issue_id,))
    conn.commit()


def ref_exists(ref: str, exclude_id: int | None = None) -> bool:
    conn = database.get_conn()
    if exclude_id:
        row = conn.execute(
            "SELECT 1 FROM transactions WHERE reference_number=? AND id!=?",
            (ref, exclude_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM transactions WHERE reference_number=?", (ref,)
        ).fetchone()
    return row is not None
