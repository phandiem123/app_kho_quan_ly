from __future__ import annotations
from dataclasses import dataclass, field
import database

_TX = {
    "kho_kho": "LUAN_CHUYEN_KHO",
    "dv_dv":   "LUAN_CHUYEN_DV",
}


@dataclass
class TransferLine:
    item_type_id: int
    item_code: str
    item_name: str
    unit_of_measure: str
    quantity: int
    quality_level: str = "H1"
    notes: str = ""
    id: int | None = None


@dataclass
class Transfer:
    id: int | None
    reference_number: str
    from_warehouse_id: int
    from_warehouse_name: str
    to_warehouse_id: int | None
    to_warehouse_name: str
    transaction_date: str
    tx_type: str = "LUAN_CHUYEN_KHO"
    created_by: str = ""
    transporter: str = ""
    deliverer: str = ""
    notes: str = ""
    line_count: int = 0
    lines: list[TransferLine] = field(default_factory=list)

    @property
    def subtype(self) -> str:
        return "dv_dv" if self.tx_type == "LUAN_CHUYEN_DV" else "kho_kho"


def get_all(year: int | None = None, subtype: str = "kho_kho") -> list[Transfer]:
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
               t.transaction_date, t.created_by, t.transporter, t.supplier AS deliverer, t.notes,
               COUNT(tl.id) AS line_count
        FROM transactions t
        LEFT JOIN warehouses wfrom ON wfrom.id = t.from_warehouse_id
        LEFT JOIN warehouses wto   ON wto.id   = t.to_warehouse_id
        LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.transaction_date DESC, t.id DESC
    """, params).fetchall()
    return [
        Transfer(
            id=r["id"],
            tx_type=r["tx_type"],
            reference_number=r["reference_number"] or "",
            from_warehouse_id=r["from_warehouse_id"] or 0,
            from_warehouse_name=r["from_warehouse_name"] or "",
            to_warehouse_id=r["to_warehouse_id"],
            to_warehouse_name=r["to_warehouse_name"] or "",
            transaction_date=r["transaction_date"] or "",
            created_by=r["created_by"] or "",
            transporter=r["transporter"] or "",
            deliverer=r["deliverer"] or "",
            notes=r["notes"] or "",
            line_count=r["line_count"] or 0,
        )
        for r in rows
    ]


def get_lines(transaction_id: int) -> list[TransferLine]:
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT tl.id, tl.item_type_id, it.code AS item_code,
               it.name AS item_name, it.unit_of_measure,
               tl.quantity, tl.quality_level_to, tl.notes
        FROM transaction_lines tl
        JOIN item_types it ON it.id = tl.item_type_id
        WHERE tl.transaction_id = ?
        ORDER BY tl.id
    """, (transaction_id,)).fetchall()
    return [
        TransferLine(
            id=r["id"],
            item_type_id=r["item_type_id"],
            item_code=r["item_code"] or "",
            item_name=r["item_name"] or "",
            unit_of_measure=r["unit_of_measure"] or "",
            quantity=r["quantity"],
            quality_level=r["quality_level_to"] or "H1",
            notes=r["notes"] or "",
        )
        for r in rows
    ]


def _upsert_kho(conn, wh_id, item_type_id, qty):
    """Add H1 inventory at a TONG warehouse (no received_at_unit_date)."""
    row = conn.execute("""
        SELECT id FROM inventory
        WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
          AND received_at_unit_date IS NULL AND is_shared=0
        LIMIT 1
    """, (wh_id, item_type_id)).fetchone()
    if row:
        conn.execute("UPDATE inventory SET quantity = quantity + ? WHERE id=?",
                     (qty, row["id"]))
    else:
        conn.execute("""
            INSERT INTO inventory
                (warehouse_id, item_type_id, quality_level, quantity)
            VALUES (?, ?, 'H1', ?)
        """, (wh_id, item_type_id, qty))


def _upsert_unit(conn, wh_id, item_type_id, ql, qty, received_at_unit_date):
    """Add inventory at a DON_VI unit, merging by (wh, item, ql, date)."""
    row = conn.execute("""
        SELECT id FROM inventory
        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
          AND COALESCE(received_at_unit_date,'') = COALESCE(?,'')
          AND is_shared=0
        LIMIT 1
    """, (wh_id, item_type_id, ql, received_at_unit_date)).fetchone()
    if row:
        conn.execute("UPDATE inventory SET quantity = quantity + ? WHERE id=?",
                     (qty, row["id"]))
    else:
        conn.execute("""
            INSERT INTO inventory
                (warehouse_id, item_type_id, quality_level, quantity, received_at_unit_date)
            VALUES (?, ?, ?, ?, ?)
        """, (wh_id, item_type_id, ql, qty, received_at_unit_date))


def _do_kho_transfer(conn, from_id, to_id, item_type_id, qty):
    """Move H1 between two TONG warehouses."""
    conn.execute("""
        UPDATE inventory SET quantity = MAX(0, quantity - ?)
        WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
          AND received_at_unit_date IS NULL AND is_shared=0
    """, (qty, from_id, item_type_id))
    _upsert_kho(conn, to_id, item_type_id, qty)


def _do_dv_transfer(conn, from_id, to_id, item_type_id, ql, qty):
    """Move quality-level items between two DON_VI units, preserving received_at_unit_date (FIFO)."""
    lots = conn.execute("""
        SELECT id, quantity, received_at_unit_date
        FROM inventory
        WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
          AND quantity > 0
        ORDER BY COALESCE(received_at_unit_date, '9999') ASC, id ASC
    """, (from_id, item_type_id, ql)).fetchall()
    remaining = qty
    for lot in lots:
        if remaining <= 0:
            break
        take = min(remaining, lot["quantity"])
        conn.execute("UPDATE inventory SET quantity = quantity - ? WHERE id=?",
                     (take, lot["id"]))
        _upsert_unit(conn, to_id, item_type_id, ql, take, lot["received_at_unit_date"])
        remaining -= take


def _undo_transfer(conn, from_id, to_id, lines, subtype):
    """Reverse inventory effects of a transfer (for update/delete)."""
    for line in lines:
        ql = line.quality_level
        if subtype == "kho_kho":
            _upsert_kho(conn, from_id, line.item_type_id, line.quantity)
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
                  AND received_at_unit_date IS NULL AND is_shared=0
            """, (line.quantity, to_id, line.item_type_id))
        else:
            # Undo DV: move back from to_unit → from_unit (FIFO from destination)
            lots = conn.execute("""
                SELECT id, quantity, received_at_unit_date
                FROM inventory
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=?
                  AND quantity > 0
                ORDER BY COALESCE(received_at_unit_date, '9999') ASC, id ASC
            """, (to_id, line.item_type_id, ql)).fetchall()
            remaining = line.quantity
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(remaining, lot["quantity"])
                conn.execute("UPDATE inventory SET quantity = quantity - ? WHERE id=?",
                             (take, lot["id"]))
                _upsert_unit(conn, from_id, line.item_type_id, ql, take,
                             lot["received_at_unit_date"])
                remaining -= take


def insert(transfer: Transfer) -> int:
    conn = database.get_conn()
    cur = conn.execute("""
        INSERT INTO transactions
            (type, reference_number, from_warehouse_id, to_warehouse_id,
             transaction_date, created_by, transporter, supplier, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (_TX[transfer.subtype], transfer.reference_number,
          transfer.from_warehouse_id, transfer.to_warehouse_id,
          transfer.transaction_date, transfer.created_by,
          transfer.transporter, transfer.deliverer, transfer.notes))
    tx_id = cur.lastrowid

    for line in transfer.lines:
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tx_id, line.item_type_id, line.quality_level, line.quality_level,
              line.quantity, line.notes))
        if transfer.to_warehouse_id:
            if transfer.subtype == "kho_kho":
                _do_kho_transfer(conn, transfer.from_warehouse_id,
                                 transfer.to_warehouse_id, line.item_type_id, line.quantity)
            else:
                _do_dv_transfer(conn, transfer.from_warehouse_id,
                                transfer.to_warehouse_id, line.item_type_id,
                                line.quality_level, line.quantity)

    conn.commit()
    return tx_id


def update(transfer: Transfer) -> None:
    conn = database.get_conn()
    old = conn.execute(
        "SELECT from_warehouse_id, to_warehouse_id, type FROM transactions WHERE id=?",
        (transfer.id,)
    ).fetchone()
    if old and old["from_warehouse_id"] and old["to_warehouse_id"]:
        old_subtype = "dv_dv" if old["type"] == "LUAN_CHUYEN_DV" else "kho_kho"
        _undo_transfer(conn, old["from_warehouse_id"], old["to_warehouse_id"],
                       get_lines(transfer.id), old_subtype)

    conn.execute("""
        UPDATE transactions SET
            type=?, reference_number=?, from_warehouse_id=?, to_warehouse_id=?,
            transaction_date=?, created_by=?, transporter=?, supplier=?, notes=?
        WHERE id=?
    """, (_TX[transfer.subtype], transfer.reference_number,
          transfer.from_warehouse_id, transfer.to_warehouse_id,
          transfer.transaction_date, transfer.created_by,
          transfer.transporter, transfer.deliverer, transfer.notes, transfer.id))
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (transfer.id,))

    for line in transfer.lines:
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (transfer.id, line.item_type_id, line.quality_level, line.quality_level,
              line.quantity, line.notes))
        if transfer.to_warehouse_id:
            if transfer.subtype == "kho_kho":
                _do_kho_transfer(conn, transfer.from_warehouse_id,
                                 transfer.to_warehouse_id, line.item_type_id, line.quantity)
            else:
                _do_dv_transfer(conn, transfer.from_warehouse_id,
                                transfer.to_warehouse_id, line.item_type_id,
                                line.quality_level, line.quantity)

    conn.commit()


def delete(transfer_id: int) -> None:
    conn = database.get_conn()
    old = conn.execute(
        "SELECT from_warehouse_id, to_warehouse_id, type FROM transactions WHERE id=?",
        (transfer_id,)
    ).fetchone()
    if old and old["from_warehouse_id"] and old["to_warehouse_id"]:
        old_subtype = "dv_dv" if old["type"] == "LUAN_CHUYEN_DV" else "kho_kho"
        _undo_transfer(conn, old["from_warehouse_id"], old["to_warehouse_id"],
                       get_lines(transfer_id), old_subtype)

    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (transfer_id,))
    conn.execute("DELETE FROM transactions WHERE id=?", (transfer_id,))
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
