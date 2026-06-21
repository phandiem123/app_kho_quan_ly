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
        "ALTER TABLE transactions ADD COLUMN loan_transaction_id INTEGER REFERENCES transactions(id)",
    ]:
        try:
            _conn.execute(sql)
        except Exception:
            pass
    _conn.commit()
    _migrate_nhap_dc_tu_kho()


def _migrate_nhap_dc_tu_kho():
    """Add NHAP_DC_TU_KHO to transactions.type CHECK constraint for existing databases."""
    row = _conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    if not row or 'NHAP_DC_TU_KHO' in (row[0] or ''):
        return  # Already has it or table doesn't exist

    _conn.execute("PRAGMA foreign_keys = OFF")
    _conn.execute("""
        CREATE TABLE transactions_new (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            type                TEXT NOT NULL CHECK (type IN (
                                    'NHAP_KHO', 'XUAT_KHO',
                                    'NHAP_DC_TU_KHO',
                                    'LUAN_CHUYEN_KHO', 'LUAN_CHUYEN_DV',
                                    'NANG_MUC', 'CHUYEN_H4',
                                    'MUON', 'TRA',
                                    'THANH_XU_LY'
                                )),
            reference_number    TEXT,
            from_warehouse_id   INTEGER REFERENCES warehouses(id),
            to_warehouse_id     INTEGER REFERENCES warehouses(id),
            transaction_date    TEXT NOT NULL,
            notes               TEXT,
            created_by          TEXT,
            created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            supplier            TEXT,
            transporter         TEXT,
            loan_transaction_id INTEGER REFERENCES transactions_new(id)
        )
    """)
    _conn.execute("""
        INSERT INTO transactions_new
            (id, type, reference_number, from_warehouse_id, to_warehouse_id,
             transaction_date, notes, created_by, created_at,
             supplier, transporter, loan_transaction_id)
        SELECT id, type, reference_number, from_warehouse_id, to_warehouse_id,
               transaction_date, notes, created_by, created_at,
               supplier, transporter, loan_transaction_id
        FROM transactions
    """)
    _conn.execute("DROP TABLE transactions")
    _conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_date    ON transactions(transaction_date)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_type    ON transactions(type)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_from_wh ON transactions(from_warehouse_id)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_to_wh   ON transactions(to_warehouse_id)")
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.commit()


def close():
    global _conn
    if _conn:
        _conn.close()
        _conn = None
