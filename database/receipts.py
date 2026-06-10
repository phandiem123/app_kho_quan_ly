from __future__ import annotations
from dataclasses import dataclass, field
import database


@dataclass
class ReceiptLine:
    item_type_id: int
    item_code: str
    item_name: str
    unit_of_measure: str
    quantity: int
    unit_price: float = 0.0
    notes: str = ""
    id: int | None = None


@dataclass
class Receipt:
    id: int | None
    reference_number: str
    to_warehouse_id: int
    to_warehouse_name: str
    transaction_date: str
    supplier: str = ""
    created_by: str = ""
    transporter: str = ""
    notes: str = ""
    line_count: int = 0
    lines: list[ReceiptLine] = field(default_factory=list)


def get_all(year: int | None = None) -> list[Receipt]:
    conn = database.get_conn()
    where = "WHERE t.type = 'NHAP_KHO'"
    params: list = []
    if year:
        where += " AND strftime('%Y', t.transaction_date) = ?"
        params.append(str(year))
    rows = conn.execute(f"""
        SELECT t.id, t.reference_number, t.to_warehouse_id,
               w.name AS warehouse_name,
               t.transaction_date, t.supplier, t.created_by,
               t.transporter, t.notes,
               COUNT(tl.id) AS line_count
        FROM transactions t
        LEFT JOIN warehouses w ON w.id = t.to_warehouse_id
        LEFT JOIN transaction_lines tl ON tl.transaction_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.transaction_date DESC, t.id DESC
    """, params).fetchall()
    return [
        Receipt(
            id=r["id"],
            reference_number=r["reference_number"] or "",
            to_warehouse_id=r["to_warehouse_id"] or 0,
            to_warehouse_name=r["warehouse_name"] or "",
            transaction_date=r["transaction_date"] or "",
            supplier=r["supplier"] or "",
            created_by=r["created_by"] or "",
            transporter=r["transporter"] or "",
            notes=r["notes"] or "",
            line_count=r["line_count"] or 0,
        )
        for r in rows
    ]


def get_lines(transaction_id: int) -> list[ReceiptLine]:
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT tl.id, tl.item_type_id, it.code AS item_code,
               it.name AS item_name, it.unit_of_measure,
               tl.quantity, tl.unit_price, tl.notes
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
        )
        for r in rows
    ]


def insert(receipt: Receipt) -> int:
    conn = database.get_conn()
    cur = conn.execute("""
        INSERT INTO transactions
            (type, reference_number, to_warehouse_id, transaction_date,
             supplier, created_by, transporter, notes)
        VALUES ('NHAP_KHO', ?, ?, ?, ?, ?, ?, ?)
    """, (receipt.reference_number, receipt.to_warehouse_id,
          receipt.transaction_date, receipt.supplier,
          receipt.created_by, receipt.transporter, receipt.notes))
    tx_id = cur.lastrowid
    for line in receipt.lines:
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, unit_price, notes)
            VALUES (?, ?, NULL, 'H1', ?, ?, ?)
        """, (tx_id, line.item_type_id, line.quantity, line.unit_price, line.notes))
        existing = conn.execute("""
            SELECT id FROM inventory
            WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
              AND received_at_unit_date IS NULL
            LIMIT 1
        """, (receipt.to_warehouse_id, line.item_type_id)).fetchone()
        if existing:
            conn.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?",
                         (line.quantity, existing["id"]))
        else:
            conn.execute("""
                INSERT INTO inventory (warehouse_id, item_type_id, quality_level, quantity)
                VALUES (?, ?, 'H1', ?)
            """, (receipt.to_warehouse_id, line.item_type_id, line.quantity))
    conn.commit()
    return tx_id


def update(receipt: Receipt) -> None:
    conn = database.get_conn()
    old_wh = conn.execute(
        "SELECT to_warehouse_id FROM transactions WHERE id=?", (receipt.id,)
    ).fetchone()
    old_wh_id = old_wh["to_warehouse_id"] if old_wh else None
    for line in get_lines(receipt.id):
        if old_wh_id:
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
                  AND received_at_unit_date IS NULL
            """, (line.quantity, old_wh_id, line.item_type_id))
    conn.execute("""
        UPDATE transactions SET
            reference_number=?, to_warehouse_id=?, transaction_date=?,
            supplier=?, created_by=?, transporter=?, notes=?
        WHERE id=?
    """, (receipt.reference_number, receipt.to_warehouse_id,
          receipt.transaction_date, receipt.supplier,
          receipt.created_by, receipt.transporter, receipt.notes, receipt.id))
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (receipt.id,))
    for line in receipt.lines:
        conn.execute("""
            INSERT INTO transaction_lines
                (transaction_id, item_type_id, quality_level_from,
                 quality_level_to, quantity, unit_price, notes)
            VALUES (?, ?, NULL, 'H1', ?, ?, ?)
        """, (receipt.id, line.item_type_id, line.quantity, line.unit_price, line.notes))
        existing = conn.execute("""
            SELECT id FROM inventory
            WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
              AND received_at_unit_date IS NULL
            LIMIT 1
        """, (receipt.to_warehouse_id, line.item_type_id)).fetchone()
        if existing:
            conn.execute("UPDATE inventory SET quantity=quantity+? WHERE id=?",
                         (line.quantity, existing["id"]))
        else:
            conn.execute("""
                INSERT INTO inventory (warehouse_id, item_type_id, quality_level, quantity)
                VALUES (?, ?, 'H1', ?)
            """, (receipt.to_warehouse_id, line.item_type_id, line.quantity))
    conn.commit()


def delete(receipt_id: int) -> None:
    conn = database.get_conn()
    old_wh = conn.execute(
        "SELECT to_warehouse_id FROM transactions WHERE id=?", (receipt_id,)
    ).fetchone()
    old_wh_id = old_wh["to_warehouse_id"] if old_wh else None
    for line in get_lines(receipt_id):
        if old_wh_id:
            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level='H1'
                  AND received_at_unit_date IS NULL
            """, (line.quantity, old_wh_id, line.item_type_id))
    conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (receipt_id,))
    conn.execute("DELETE FROM transactions WHERE id=?", (receipt_id,))
    conn.commit()


def ref_exists(ref: str, exclude_id: int | None = None) -> bool:
    conn = database.get_conn()
    if exclude_id:
        row = conn.execute(
            "SELECT 1 FROM transactions WHERE reference_number=? AND type='NHAP_KHO' AND id!=?",
            (ref, exclude_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM transactions WHERE reference_number=? AND type='NHAP_KHO'",
            (ref,)
        ).fetchone()
    return row is not None
