from __future__ import annotations
from dataclasses import dataclass, field
import database


@dataclass
class Warehouse:
    code: str
    name: str
    type: str           # 'TONG' | 'DON_VI'
    address: str = ""
    notes: str = ""
    is_active: int = 1
    id: int | None = None


def get_all(active_only: bool = True) -> list[Warehouse]:
    conn = database.get_conn()
    where = "WHERE is_active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT * FROM warehouses {where} ORDER BY type, name"
    ).fetchall()
    return [
        Warehouse(
            id=r["id"], code=r["code"], name=r["name"],
            type=r["type"], address=r["address"] or "",
            notes=r["notes"] or "", is_active=r["is_active"],
        )
        for r in rows
    ]


def get_by_id(wh_id: int) -> Warehouse | None:
    conn = database.get_conn()
    r = conn.execute("SELECT * FROM warehouses WHERE id = ?", (wh_id,)).fetchone()
    if not r:
        return None
    return Warehouse(
        id=r["id"], code=r["code"], name=r["name"],
        type=r["type"], address=r["address"] or "",
        notes=r["notes"] or "", is_active=r["is_active"],
    )


def code_exists(code: str, exclude_id: int | None = None) -> bool:
    conn = database.get_conn()
    if exclude_id:
        row = conn.execute(
            "SELECT 1 FROM warehouses WHERE code=? AND id!=?", (code, exclude_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM warehouses WHERE code=?", (code,)
        ).fetchone()
    return row is not None


def insert(w: Warehouse) -> int:
    conn = database.get_conn()
    cur = conn.execute(
        "INSERT INTO warehouses (code, name, type, address, notes) VALUES (?,?,?,?,?)",
        (w.code.strip(), w.name.strip(), w.type, w.address.strip(), w.notes.strip()),
    )
    conn.commit()
    return cur.lastrowid


def update(w: Warehouse) -> None:
    conn = database.get_conn()
    conn.execute(
        "UPDATE warehouses SET code=?, name=?, type=?, address=?, notes=? WHERE id=?",
        (w.code.strip(), w.name.strip(), w.type, w.address.strip(), w.notes.strip(), w.id),
    )
    conn.commit()


def soft_delete(wh_id: int) -> None:
    """Ẩn kho (không xóa cứng để giữ lịch sử giao dịch)."""
    conn = database.get_conn()
    conn.execute("UPDATE warehouses SET is_active=0 WHERE id=?", (wh_id,))
    conn.commit()


def get_stats() -> dict:
    conn = database.get_conn()
    kho_tong = conn.execute(
        "SELECT COUNT(*) FROM warehouses WHERE type='TONG' AND is_active=1"
    ).fetchone()[0]
    don_vi = conn.execute(
        "SELECT COUNT(*) FROM warehouses WHERE type='DON_VI' AND is_active=1"
    ).fetchone()[0]
    h4_qty = conn.execute(
        "SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE quality_level='H4'"
    ).fetchone()[0]
    item_types = conn.execute(
        "SELECT COUNT(DISTINCT item_type_id) FROM inventory WHERE quantity > 0"
    ).fetchone()[0]
    return {
        "kho_tong": kho_tong,
        "don_vi": don_vi,
        "h4_pending": h4_qty,
        "item_types": item_types,
    }
