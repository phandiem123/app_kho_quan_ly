from __future__ import annotations
from dataclasses import dataclass
import database


@dataclass
class ItemType:
    code: str
    name: str
    unit_of_measure: str
    total_lifespan_months: int
    notes: str = ""
    is_active: int = 1
    id: int | None = None


def get_all(active_only: bool = True) -> list[ItemType]:
    conn = database.get_conn()
    where = "WHERE is_active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT * FROM item_types {where} ORDER BY name"
    ).fetchall()
    return [
        ItemType(
            id=r["id"], code=r["code"], name=r["name"],
            unit_of_measure=r["unit_of_measure"],
            total_lifespan_months=r["total_lifespan_months"],
            notes=r["notes"] or "", is_active=r["is_active"],
        )
        for r in rows
    ]


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
        "INSERT INTO item_types (code, name, unit_of_measure, total_lifespan_months, notes)"
        " VALUES (?,?,?,?,?)",
        (item.code.strip(), item.name.strip(), item.unit_of_measure.strip(),
         item.total_lifespan_months, item.notes.strip()),
    )
    conn.commit()
    return cur.lastrowid


def update(item: ItemType) -> None:
    conn = database.get_conn()
    conn.execute(
        "UPDATE item_types SET code=?, name=?, unit_of_measure=?,"
        " total_lifespan_months=?, notes=? WHERE id=?",
        (item.code.strip(), item.name.strip(), item.unit_of_measure.strip(),
         item.total_lifespan_months, item.notes.strip(), item.id),
    )
    conn.commit()


def soft_delete(item_id: int) -> None:
    conn = database.get_conn()
    conn.execute("UPDATE item_types SET is_active=0 WHERE id=?", (item_id,))
    conn.commit()
