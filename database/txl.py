"""Database operations for Thanh Xử Lý (THANH_XU_LY)."""

from __future__ import annotations
from dataclasses import dataclass, field
import database


@dataclass
class H4Item:
    inventory_id: int
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    item_type_id: int
    item_code: str
    item_name: str
    unit_of_measure: str
    quantity: int
    lot_number: str = ""
    received_at_unit_date: str = ""
    months_at_unit: int | None = None
    notes: str = ""


@dataclass
class TxlLine:
    inventory_id: int
    item_type_id: int
    item_code: str
    item_name: str
    unit_of_measure: str
    quantity: int
    notes: str = ""
    id: int | None = None


@dataclass
class TxlRecord:
    id: int | None
    reference_number: str
    warehouse_id: int
    warehouse_name: str
    transaction_date: str
    notes: str = ""
    created_by: str = ""
    line_count: int = 0


def get_h4_inventory(wh_type: str) -> list[H4Item]:
    """Trả về tất cả lô H4 còn hàng theo loại kho."""
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT i.id AS inv_id,
               w.id AS wh_id, w.code AS wh_code, w.name AS wh_name,
               t.id AS item_id, t.code AS item_code, t.name AS item_name,
               t.unit_of_measure,
               i.quantity, i.lot_number, i.received_at_unit_date, i.notes,
               CASE
                   WHEN i.received_at_unit_date IS NOT NULL
                   THEN CAST(
                       (julianday(date('now','localtime'))
                        - julianday(i.received_at_unit_date)) / 30.44 AS INTEGER)
                   ELSE NULL
               END AS months_at_unit
        FROM inventory i
        JOIN warehouses w ON w.id = i.warehouse_id
        JOIN item_types t  ON t.id = i.item_type_id
        WHERE i.quality_level = 'H4'
          AND i.quantity > 0
          AND w.type = ?
        ORDER BY w.name, t.name
    """, (wh_type,)).fetchall()
    return [
        H4Item(
            inventory_id=r["inv_id"],
            warehouse_id=r["wh_id"],
            warehouse_code=r["wh_code"],
            warehouse_name=r["wh_name"],
            item_type_id=r["item_id"],
            item_code=r["item_code"],
            item_name=r["item_name"],
            unit_of_measure=r["unit_of_measure"],
            quantity=r["quantity"],
            lot_number=r["lot_number"] or "",
            received_at_unit_date=r["received_at_unit_date"] or "",
            months_at_unit=r["months_at_unit"],
            notes=r["notes"] or "",
        )
        for r in rows
    ]


def get_all(wh_type: str, year: int | None = None) -> list[TxlRecord]:
    """Lịch sử phiếu THANH_XU_LY theo loại kho."""
    conn = database.get_conn()
    clauses = ["t.type = 'THANH_XU_LY'", "w.type = ?"]
    params: list = [wh_type]
    if year:
        clauses.append("strftime('%Y', t.transaction_date) = ?")
        params.append(str(year))
    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(f"""
        SELECT t.id, t.reference_number, t.from_warehouse_id,
               w.name AS wh_name,
               t.transaction_date, t.notes, t.created_by,
               COUNT(tl.id) AS line_count
        FROM transactions t
        JOIN warehouses w   ON w.id  = t.from_warehouse_id
        LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.transaction_date DESC, t.id DESC
    """, params).fetchall()
    return [
        TxlRecord(
            id=r["id"],
            reference_number=r["reference_number"] or "",
            warehouse_id=r["from_warehouse_id"],
            warehouse_name=r["wh_name"] or "",
            transaction_date=r["transaction_date"] or "",
            notes=r["notes"] or "",
            created_by=r["created_by"] or "",
            line_count=r["line_count"] or 0,
        )
        for r in rows
    ]


def get_lines(tx_id: int) -> list[TxlLine]:
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT tl.id, tl.inventory_id, tl.item_type_id,
               it.code AS item_code, it.name AS item_name, it.unit_of_measure,
               tl.quantity, tl.notes
        FROM transaction_lines tl
        JOIN item_types it ON it.id = tl.item_type_id
        WHERE tl.transaction_id = ?
        ORDER BY tl.id
    """, (tx_id,)).fetchall()
    return [
        TxlLine(
            id=r["id"],
            inventory_id=r["inventory_id"] or 0,
            item_type_id=r["item_type_id"],
            item_code=r["item_code"] or "",
            item_name=r["item_name"] or "",
            unit_of_measure=r["unit_of_measure"] or "",
            quantity=r["quantity"],
            notes=r["notes"] or "",
        )
        for r in rows
    ]


def create(
    warehouse_id: int,
    ref_num: str,
    date: str,
    notes: str,
    created_by: str,
    items: list[tuple[int, int, int, str]],  # (inventory_id, item_type_id, qty, notes)
) -> int:
    """Tạo phiếu THANH_XU_LY và trừ tồn kho H4."""
    conn = database.get_conn()
    cur = conn.execute("""
        INSERT INTO transactions
            (type, reference_number, from_warehouse_id,
             transaction_date, notes, created_by)
        VALUES ('THANH_XU_LY', ?, ?, ?, ?, ?)
    """, (ref_num, warehouse_id, date, notes, created_by))
    tx_id = cur.lastrowid

    for inv_id, item_type_id, qty, item_notes in items:
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, inventory_id, item_type_id,
                 quality_level_from, quality_level_to, quantity, notes)
            VALUES (?, ?, ?, 'H4', 'H4', ?, ?)
        """, (tx_id, inv_id, item_type_id, qty, item_notes))
        conn.execute("""
            UPDATE inventory SET quantity = MAX(0, quantity - ?)
            WHERE id = ?
        """, (qty, inv_id))

    conn.commit()
    return tx_id


def delete(tx_id: int) -> None:
    """Xóa phiếu TXL và hoàn lại tồn kho."""
    conn = database.get_conn()
    lines = get_lines(tx_id)
    for line in lines:
        if line.inventory_id:
            conn.execute("""
                UPDATE inventory SET quantity = quantity + ?
                WHERE id = ?
            """, (line.quantity, line.inventory_id))
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (tx_id,))
    conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
    conn.commit()
