import sqlite3
import os
from pathlib import Path

_DB_PATH = Path(os.getenv("DCCD_DB_PATH", Path.home() / ".dccd" / "dccd.db"))
_SCHEMA   = Path(__file__).parent / "schema.sql"
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")
        _init_schema()
        _migrate()
    return _conn


def _init_schema():
    sql = _SCHEMA.read_text(encoding="utf-8")
    _conn.executescript(sql)
    _conn.commit()


def _migrate():
    for sql in [
        "ALTER TABLE transactions ADD COLUMN supplier TEXT",
        "ALTER TABLE transactions ADD COLUMN transporter TEXT",
        "ALTER TABLE transaction_lines ADD COLUMN unit_price REAL NOT NULL DEFAULT 0",
        "ALTER TABLE item_types ADD COLUMN unit_price REAL NOT NULL DEFAULT 0",
    ]:
        try:
            _conn.execute(sql)
        except Exception:
            pass
    _conn.commit()


def close():
    global _conn
    if _conn:
        _conn.close()
        _conn = None
