from __future__ import annotations
from dataclasses import dataclass, field
import database

# subtype → transaction type in DB
_TX = {
    "new":             "NHAP_KHO",
    "from_unit":       "NHAP_KHO",
    "unit_return":     "TRA",
    "event_return":    "TRA",
    "shared_return":   "TRA",       # backwards-compat alias
    "shared_from_wh":  "NHAP_DC_TU_KHO",  # nhập hàng DC từ kho thường
}
# subtype → quality level for items
_QUALITY = {
    "new":             "H1",
    "from_unit":       "H4",
    "unit_return":     "H3",
    "event_return":    "H3",
    "shared_return":   "H3",
    "shared_from_wh":  "H3",
}


@dataclass
class ReceiptLine:
    item_type_id: int
    item_code: str
    item_name: str
    unit_of_measure: str
    quantity: int
    unit_price: float = 0.0
    notes: str = ""
    quality_level: str = "H1"
    quality_level_from: str | None = None  # quality tại kho nguồn (shared_from_wh)
    id: int | None = None
    is_shared: bool = False  # runtime-only; DC lines in from_unit handled as auto-TRA


@dataclass
class Receipt:
    id: int | None
    reference_number: str
    to_warehouse_id: int
    to_warehouse_name: str
    transaction_date: str
    tx_type: str = "NHAP_KHO"
    from_warehouse_id: int | None = None
    from_warehouse_name: str = ""
    supplier: str = ""
    created_by: str = ""
    transporter: str = ""
    notes: str = ""
    line_count: int = 0
    loan_transaction_id: int | None = None
    lines: list[ReceiptLine] = field(default_factory=list)

    @property
    def subtype(self) -> str:
        if self.tx_type == "NHAP_DC_TU_KHO":
            return "shared_from_wh"
        if self.tx_type == "TRA":
            return "unit_return" if self.from_warehouse_id else "event_return"
        if self.from_warehouse_id:
            return "from_unit"
        return "new"


def get_all(year: int | None = None, subtype: str = "new") -> list[Receipt]:
    conn = database.get_conn()
    params: list = []

    if subtype == "shared_return":
        clauses = ["(t.type = 'TRA' OR t.type = 'NHAP_DC_TU_KHO')"]
    else:
        tx_type = _TX[subtype]
        clauses = [f"t.type = '{tx_type}'"]
        if subtype in ("new", "event_return"):
            clauses.append("t.from_warehouse_id IS NULL")
        elif subtype in ("from_unit", "unit_return"):
            clauses.append("t.from_warehouse_id IS NOT NULL")

    if year:
        clauses.append("strftime('%Y', t.transaction_date) = ?")
        params.append(str(year))

    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(f"""
        SELECT t.id, t.type AS tx_type, t.reference_number,
               t.to_warehouse_id,  wto.name AS to_warehouse_name,
               t.from_warehouse_id, wfrom.name AS from_warehouse_name,
               t.transaction_date, t.supplier, t.created_by,
               t.transporter, t.notes, t.loan_transaction_id,
               COUNT(tl.id) AS line_count
        FROM transactions t
        LEFT JOIN warehouses wto   ON wto.id  = t.to_warehouse_id
        LEFT JOIN warehouses wfrom ON wfrom.id = t.from_warehouse_id
        LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.transaction_date DESC, t.id DESC
    """, params).fetchall()
    return [
        Receipt(
            id=r["id"],
            tx_type=r["tx_type"],
            reference_number=r["reference_number"] or "",
            to_warehouse_id=r["to_warehouse_id"] or 0,
            to_warehouse_name=r["to_warehouse_name"] or "",
            from_warehouse_id=r["from_warehouse_id"],
            from_warehouse_name=r["from_warehouse_name"] or "",
            transaction_date=r["transaction_date"] or "",
            supplier=r["supplier"] or "",
            created_by=r["created_by"] or "",
            transporter=r["transporter"] or "",
            notes=r["notes"] or "",
            loan_transaction_id=r["loan_transaction_id"],
            line_count=r["line_count"] or 0,
        )
        for r in rows
    ]


def get_lines(transaction_id: int) -> list[ReceiptLine]:
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT tl.id, tl.item_type_id, it.code AS item_code,
               it.name AS item_name, it.unit_of_measure,
               tl.quantity, tl.unit_price, tl.notes,
               tl.quality_level_from, tl.quality_level_to
        FROM transaction_lines tl
        JOIN item_types it ON it.id = tl.item_type_id
        WHERE tl.transaction_id = ?
        ORDER BY tl.id
    """, (transaction_id,)).fetchall()
    return [
        ReceiptLine(
            id=r["id"],
            item_type_id=r["item_type_id"],
            item_code=r["item_code"] or "",
            item_name=r["item_name"] or "",
            unit_of_measure=r["unit_of_measure"] or "",
            quantity=r["quantity"],
            unit_price=float(r["unit_price"] or 0),
            notes=r["notes"] or "",
            quality_level=r["quality_level_to"] or "H1",
            quality_level_from=r["quality_level_from"],
        )
        for r in rows
    ]


def _upsert_inv(conn, wh_id, item_type_id, quality, qty, is_shared=0):
    row = conn.execute("""
        SELECT id FROM inventory
        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
          AND received_at_unit_date IS NULL AND is_shared=?
        LIMIT 1
    """, (wh_id, item_type_id, quality, is_shared)).fetchone()
    if row:
        conn.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?",
                     (qty, row["id"]))
    else:
        conn.execute("""
            INSERT INTO inventory (warehouse_id, item_type_id, quality_level, quantity, is_shared)
            VALUES (?, ?, ?, ?, ?)
        """, (wh_id, item_type_id, quality, qty, is_shared))


def _upsert_inv_dated(conn, wh_id, item_type_id, quality, qty, received_at_unit_date):
    """Upsert inventory preserving a specific received_at_unit_date (for items returned from units)."""
    row = conn.execute("""
        SELECT id FROM inventory
        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
          AND COALESCE(received_at_unit_date,'') = COALESCE(?,'')
          AND is_shared=0
        LIMIT 1
    """, (wh_id, item_type_id, quality, received_at_unit_date)).fetchone()
    if row:
        conn.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?",
                     (qty, row["id"]))
    else:
        conn.execute("""
            INSERT INTO inventory
                (warehouse_id, item_type_id, quality_level, quantity, received_at_unit_date)
            VALUES (?, ?, ?, ?, ?)
        """, (wh_id, item_type_id, quality, qty, received_at_unit_date))


def insert(receipt: Receipt) -> int:
    conn = database.get_conn()
    subtype = receipt.subtype
    cur = conn.execute("""
        INSERT INTO transactions
            (type, reference_number, from_warehouse_id, to_warehouse_id,
             transaction_date, supplier, created_by, transporter, notes,
             loan_transaction_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (_TX[subtype], receipt.reference_number,
          receipt.from_warehouse_id, receipt.to_warehouse_id,
          receipt.transaction_date, receipt.supplier,
          receipt.created_by, receipt.transporter, receipt.notes,
          receipt.loan_transaction_id))
    tx_id = cur.lastrowid

    for line in receipt.lines:
        if subtype in ("from_unit", "shared_from_wh"):
            ql_from = line.quality_level
            ql      = "H3" if subtype == "shared_from_wh" else line.quality_level
        else:
            ql_from = None
            ql      = _QUALITY[subtype]
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, unit_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tx_id, line.item_type_id, ql_from, ql,
              line.quantity, line.unit_price, line.notes))
        if subtype == "new":
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H1", line.quantity)
        elif subtype == "from_unit" and receipt.from_warehouse_id:
            src = conn.execute("""
                SELECT received_at_unit_date FROM inventory
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=? AND quantity > 0
                ORDER BY COALESCE(received_at_unit_date,'9999') ASC LIMIT 1
            """, (receipt.from_warehouse_id, line.item_type_id, ql_from)).fetchone()
            rad = src["received_at_unit_date"] if src else None
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
            """, (line.quantity, receipt.from_warehouse_id, line.item_type_id, ql_from))
            _upsert_inv_dated(conn, receipt.to_warehouse_id, line.item_type_id, ql_from, line.quantity, rad)
        elif subtype in ("unit_return", "shared_return") and receipt.from_warehouse_id:
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
            """, (line.quantity, receipt.from_warehouse_id, line.item_type_id))
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H3", line.quantity, is_shared=1)
        elif subtype == "event_return" or (subtype == "shared_return" and not receipt.from_warehouse_id):
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H3", line.quantity, is_shared=1)
        elif subtype == "shared_from_wh" and receipt.from_warehouse_id:
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=? AND is_shared=0
            """, (line.quantity, receipt.from_warehouse_id, line.item_type_id, ql_from))
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H3", line.quantity, is_shared=1)

    conn.commit()
    return tx_id


def update(receipt: Receipt) -> None:
    conn = database.get_conn()
    old = conn.execute(
        "SELECT to_warehouse_id, from_warehouse_id, type FROM transactions WHERE id=?",
        (receipt.id,)
    ).fetchone()
    old_subtype = receipt.subtype
    if old:
        old_tx = old["type"]
        if old_tx == "NHAP_DC_TU_KHO":
            old_subtype = "shared_from_wh"
        elif old_tx == "TRA":
            old_subtype = "unit_return" if old["from_warehouse_id"] else "event_return"
        elif old["from_warehouse_id"]:
            old_subtype = "from_unit"
        else:
            old_subtype = "new"
        for line in get_lines(receipt.id):
            if old_subtype == "new":
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
                      AND received_at_unit_date IS NULL
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id))
            elif old_subtype == "from_unit":
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id, line.quality_level))
            elif old_subtype in ("unit_return", "event_return"):
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id))
            elif old_subtype == "shared_from_wh" and old["from_warehouse_id"]:
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id))
                _upsert_inv(conn, old["from_warehouse_id"], line.item_type_id, "H1", line.quantity, is_shared=0)

    subtype = receipt.subtype
    conn.execute("""
        UPDATE transactions SET
            type=?, reference_number=?, from_warehouse_id=?, to_warehouse_id=?,
            transaction_date=?, supplier=?, created_by=?, transporter=?, notes=?,
            loan_transaction_id=?
        WHERE id=?
    """, (_TX[subtype], receipt.reference_number,
          receipt.from_warehouse_id, receipt.to_warehouse_id,
          receipt.transaction_date, receipt.supplier,
          receipt.created_by, receipt.transporter, receipt.notes,
          receipt.loan_transaction_id, receipt.id))
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (receipt.id,))
    for line in receipt.lines:
        if subtype in ("from_unit", "shared_from_wh"):
            ql_from = line.quality_level
            ql      = "H3" if subtype == "shared_from_wh" else line.quality_level
        else:
            ql_from = None
            ql      = _QUALITY[subtype]
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, unit_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (receipt.id, line.item_type_id, ql_from, ql,
              line.quantity, line.unit_price, line.notes))
        if subtype == "new":
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H1", line.quantity)
        elif subtype == "from_unit" and receipt.from_warehouse_id:
            src = conn.execute("""
                SELECT received_at_unit_date FROM inventory
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=? AND quantity > 0
                ORDER BY COALESCE(received_at_unit_date,'9999') ASC LIMIT 1
            """, (receipt.from_warehouse_id, line.item_type_id, ql_from)).fetchone()
            rad = src["received_at_unit_date"] if src else None
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
            """, (line.quantity, receipt.from_warehouse_id, line.item_type_id, ql_from))
            _upsert_inv_dated(conn, receipt.to_warehouse_id, line.item_type_id, ql_from, line.quantity, rad)
        elif subtype in ("unit_return", "shared_return") and receipt.from_warehouse_id:
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
            """, (line.quantity, receipt.from_warehouse_id, line.item_type_id))
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H3", line.quantity, is_shared=1)
        elif subtype == "event_return" or (subtype == "shared_return" and not receipt.from_warehouse_id):
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H3", line.quantity, is_shared=1)
        elif subtype == "shared_from_wh" and receipt.from_warehouse_id:
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=? AND is_shared=0
            """, (line.quantity, receipt.from_warehouse_id, line.item_type_id, ql_from))
            _upsert_inv(conn, receipt.to_warehouse_id, line.item_type_id, "H3", line.quantity, is_shared=1)
    conn.commit()


def delete(receipt_id: int) -> None:
    conn = database.get_conn()
    old = conn.execute(
        "SELECT to_warehouse_id, from_warehouse_id, type FROM transactions WHERE id=?",
        (receipt_id,)
    ).fetchone()
    if old:
        tx = old["type"]
        if tx == "NHAP_DC_TU_KHO":
            subtype = "shared_from_wh"
        elif tx == "TRA":
            subtype = "unit_return" if old["from_warehouse_id"] else "event_return"
        elif old["from_warehouse_id"]:
            subtype = "from_unit"
        else:
            subtype = "new"
        for line in get_lines(receipt_id):
            if subtype == "new":
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
                      AND received_at_unit_date IS NULL
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id))
            elif subtype == "from_unit":
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id, line.quality_level))
            elif subtype in ("unit_return", "event_return"):
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id))
            elif subtype == "shared_from_wh" and old["from_warehouse_id"]:
                conn.execute("""
                    UPDATE inventory SET quantity = MAX(0, quantity - ?)
                    WHERE warehouse_id=? AND item_type_id=? AND is_shared=1
                """, (line.quantity, old["to_warehouse_id"], line.item_type_id))
                restore_ql = line.quality_level_from or "H1"
                _upsert_inv(conn, old["from_warehouse_id"], line.item_type_id, restore_ql, line.quantity, is_shared=0)
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (receipt_id,))
    conn.execute("DELETE FROM transactions WHERE id=?", (receipt_id,))
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
