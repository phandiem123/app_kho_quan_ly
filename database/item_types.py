from __future__ import annotations
from dataclasses import dataclass
import unicodedata
import database


@dataclass
class ItemType:
    code: str
    name: str
    unit_of_measure: str
    total_lifespan_months: int
    notes: str = ""
    unit_price: float = 0.0
    is_active: int = 1
    id: int | None = None


def _az_key(name: str) -> str:
    nfd = unicodedata.normalize("NFD", str(name or "").lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def get_all(active_only: bool = True) -> list[ItemType]:
    conn = database.get_conn()
    where = "WHERE is_active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT * FROM item_types {where}"
    ).fetchall()
    items = [
        ItemType(
            id=r["id"], code=r["code"], name=r["name"],
            unit_of_measure=r["unit_of_measure"],
            total_lifespan_months=r["total_lifespan_months"],
            notes=r["notes"] or "",
            unit_price=float(r["unit_price"] or 0),
            is_active=r["is_active"],
        )
        for r in rows
    ]
    return sorted(items, key=lambda it: _az_key(it.name))


def code_exists(code: str, exclude_id: int | None = None) -> bool:
    conn = database.get_conn()
    if exclude_id:
        row = conn.execute(
            "SELECT 1 FROM item_types WHERE code=? AND id!=?", (code, exclude_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM item_types WHERE code=?", (code,)
        ).fetchone()
    return row is not None


def insert(item: ItemType) -> int:
    conn = database.get_conn()
    cur = conn.execute(
        "INSERT INTO item_types (code, name, unit_of_measure, total_lifespan_months, unit_price, notes)"
        " VALUES (?,?,?,?,?,?)",
        (item.code.strip(), item.name.strip(), item.unit_of_measure.strip(),
         item.total_lifespan_months, item.unit_price, item.notes.strip()),
    )
    conn.commit()
    return cur.lastrowid


def update(item: ItemType) -> None:
    conn = database.get_conn()
    conn.execute(
        "UPDATE item_types SET code=?, name=?, unit_of_measure=?,"
        " total_lifespan_months=?, unit_price=?, notes=? WHERE id=?",
        (item.code.strip(), item.name.strip(), item.unit_of_measure.strip(),
         item.total_lifespan_months, item.unit_price, item.notes.strip(), item.id),
    )
    conn.commit()


def soft_delete(item_id: int) -> None:
    conn = database.get_conn()
    conn.execute("UPDATE item_types SET is_active=0 WHERE id=?", (item_id,))
    conn.commit()
