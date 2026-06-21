-- ============================================================
-- DCCD - Schema Database
-- SQLite, UTF-8
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- 1. DANH MỤC KHO / ĐƠN VỊ
--    type: 'TONG' = Kho Tổng (chỉ H1, H4)
--          'DON_VI' = Kho Đơn Vị (H1 → H4)
-- ============================================================
CREATE TABLE IF NOT EXISTS warehouses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,          -- Mã kho, vd: "D6", "DV01"
    name        TEXT NOT NULL,                 -- Tên kho
    type        TEXT NOT NULL                  -- 'TONG' | 'DON_VI'
                    CHECK (type IN ('TONG', 'DON_VI')),
    address     TEXT,
    notes       TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,    -- 0 = đã giải thể
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- 2. DANH MỤC MẶT HÀNG
--    total_lifespan_months: niên hạn tổng (H3 → H4 khi đạt mốc này)
-- ============================================================
CREATE TABLE IF NOT EXISTS item_types (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    code                    TEXT NOT NULL UNIQUE,   -- Mã mặt hàng
    name                    TEXT NOT NULL,           -- Tên mặt hàng
    unit_of_measure         TEXT NOT NULL,           -- Đơn vị tính: cái, bộ, chiếc...
    total_lifespan_months   INTEGER NOT NULL,        -- Niên hạn tổng (tháng)
    notes                   TEXT,
    is_active               INTEGER NOT NULL DEFAULT 1
);

-- ============================================================
-- 3. TỒN KHO (Inventory)
--
--    Mỗi dòng = một lô hàng cụ thể tại một kho/đơn vị.
--    Lô được tách biệt nếu khác ngày nhập đơn vị (vì niên hạn
--    tính độc lập theo từng lô).
--
--    received_at_unit_date:
--      - NULL nếu hàng đang tại Kho Tổng (chưa tính niên hạn)
--      - Có giá trị khi hàng đã về Đơn Vị (mốc tính H1→H2→H3→H4)
--
--    is_shared: hàng dùng chung (chỉ cho mượn, phải trả về Kho)
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id            INTEGER NOT NULL REFERENCES warehouses(id),
    item_type_id            INTEGER NOT NULL REFERENCES item_types(id),
    quality_level           TEXT NOT NULL
                                CHECK (quality_level IN ('H1','H2','H3','H4')),
    quantity                INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    received_at_unit_date   TEXT,       -- NULL = tại Kho Tổng, chưa tính niên hạn
    manufacture_date        TEXT,       -- Ngày sản xuất (tính niên hạn tổng)
    lot_number              TEXT,       -- Số lô / batch
    is_shared               INTEGER NOT NULL DEFAULT 0,  -- 1 = hàng dùng chung
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_inventory_warehouse  ON inventory(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_inventory_item_type  ON inventory(item_type_id);
CREATE INDEX IF NOT EXISTS idx_inventory_quality    ON inventory(quality_level);

-- ============================================================
-- 4. PHIẾU GIAO DỊCH (Transaction header)
--
--    Các loại phiếu:
--      NHAP_KHO         : Nhập hàng vào Kho Tổng
--      XUAT_KHO         : Xuất từ Kho Tổng → Đơn Vị
--      LUAN_CHUYEN_KHO  : Luân chuyển giữa Kho Tổng ↔ Kho Tổng (chỉ H1)
--      LUAN_CHUYEN_DV   : Luân chuyển giữa Đơn Vị ↔ Đơn Vị (H2/H3/H4)
--      NANG_MUC         : Tự động/thủ công nâng H1→H2, H2→H3, H3→H4
--      CHUYEN_H4        : Chuyển thủ công sang H4 (hư hỏng)
--      MUON             : Đơn vị mượn hàng dùng chung
--      TRA              : Trả hàng dùng chung về Kho
--      THANH_XU_LY      : Thanh xử lý H4 (xuất khỏi hệ thống)
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    type                TEXT NOT NULL CHECK (type IN (
                            'NHAP_KHO', 'XUAT_KHO',
                            'NHAP_DC_TU_KHO',
                            'LUAN_CHUYEN_KHO', 'LUAN_CHUYEN_DV',
                            'NANG_MUC', 'CHUYEN_H4',
                            'MUON', 'TRA',
                            'THANH_XU_LY'
                        )),
    reference_number    TEXT,           -- Số phiếu
    from_warehouse_id   INTEGER REFERENCES warehouses(id),
    to_warehouse_id     INTEGER REFERENCES warehouses(id),
    transaction_date    TEXT NOT NULL,  -- Ngày lập phiếu
    notes               TEXT,
    created_by          TEXT,           -- Tên người lập phiếu
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_tx_date          ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_tx_type          ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_tx_from_wh       ON transactions(from_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_tx_to_wh         ON transactions(to_warehouse_id);

-- ============================================================
-- 5. CHI TIẾT PHIẾU GIAO DỊCH (Transaction lines)
--
--    quality_level_from: mức trước khi giao dịch (NULL nếu nhập mới)
--    quality_level_to  : mức sau khi giao dịch
--    received_at_unit_date: ngày nhập đơn vị — kế thừa khi luân chuyển,
--                           gán mới khi xuất kho → đơn vị
-- ============================================================
CREATE TABLE IF NOT EXISTS transaction_lines (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id          INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    inventory_id            INTEGER REFERENCES inventory(id),   -- lô nguồn (nullable khi nhập mới)
    item_type_id            INTEGER NOT NULL REFERENCES item_types(id),
    quality_level_from      TEXT CHECK (quality_level_from IN ('H1','H2','H3','H4')),
    quality_level_to        TEXT NOT NULL CHECK (quality_level_to IN ('H1','H2','H3','H4')),
    quantity                INTEGER NOT NULL CHECK (quantity > 0),
    received_at_unit_date   TEXT,   -- mốc niên hạn, kế thừa hoặc gán mới
    manufacture_date        TEXT,
    lot_number              TEXT,
    notes                   TEXT
);

CREATE INDEX IF NOT EXISTS idx_txline_tx        ON transaction_lines(transaction_id);
CREATE INDEX IF NOT EXISTS idx_txline_item      ON transaction_lines(item_type_id);

-- ============================================================
-- 6. LỊCH SỬ MƯỢN HÀNG DÙNG CHUNG
-- ============================================================
CREATE TABLE IF NOT EXISTS shared_borrows (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id            INTEGER NOT NULL REFERENCES inventory(id),
    transaction_id          INTEGER REFERENCES transactions(id),    -- phiếu MUON
    borrowing_warehouse_id  INTEGER NOT NULL REFERENCES warehouses(id),
    borrow_date             TEXT NOT NULL,
    expected_return_date    TEXT,
    actual_return_date      TEXT,
    status                  TEXT NOT NULL DEFAULT 'DANG_MUON'
                                CHECK (status IN ('DANG_MUON','DA_TRA','HU_HONG')),
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- 7. SNAPSHOT BÁO CÁO NĂM
--
--    Lưu số liệu tổng kết cuối mỗi năm cho từng (kho × mặt hàng).
--    Snapshot tự động tạo vào 31/12 hoặc khi người dùng chốt báo cáo.
--    Không xóa, không sửa — chỉ append để giữ lịch sử.
-- ============================================================
CREATE TABLE IF NOT EXISTS annual_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    year                INTEGER NOT NULL,           -- Năm báo cáo
    warehouse_id        INTEGER NOT NULL REFERENCES warehouses(id),
    item_type_id        INTEGER NOT NULL REFERENCES item_types(id),

    -- Tồn kho tại thời điểm snapshot (cuối năm)
    h1_qty              INTEGER NOT NULL DEFAULT 0,
    h2_qty              INTEGER NOT NULL DEFAULT 0,
    h3_qty              INTEGER NOT NULL DEFAULT 0,
    h4_qty              INTEGER NOT NULL DEFAULT 0,

    -- Biến động trong năm
    imported_qty        INTEGER NOT NULL DEFAULT 0, -- Nhập trong năm
    exported_qty        INTEGER NOT NULL DEFAULT 0, -- Xuất trong năm
    upgraded_qty        INTEGER NOT NULL DEFAULT 0, -- Đã nâng mức (H1→H2→H3→H4)
    disposed_qty        INTEGER NOT NULL DEFAULT 0, -- Đã thanh xử lý

    snapshot_date       TEXT NOT NULL,              -- Ngày chốt snapshot
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    UNIQUE (year, warehouse_id, item_type_id)        -- Mỗi (năm, kho, mặt hàng) chỉ 1 dòng
);

CREATE INDEX IF NOT EXISTS idx_snapshot_year    ON annual_snapshots(year);
CREATE INDEX IF NOT EXISTS idx_snapshot_wh      ON annual_snapshots(warehouse_id);

-- ============================================================
-- 8. VIEW: Thâm niên hàng tại Đơn Vị
--    Tính số tháng hàng đã lưu tại đơn vị tính từ received_at_unit_date
-- ============================================================
CREATE VIEW IF NOT EXISTS v_inventory_seniority AS
SELECT
    i.id,
    w.code          AS warehouse_code,
    w.name          AS warehouse_name,
    w.type          AS warehouse_type,
    t.code          AS item_code,
    t.name          AS item_name,
    t.unit_of_measure,
    t.total_lifespan_months,
    i.quality_level,
    i.quantity,
    i.lot_number,
    i.received_at_unit_date,
    i.manufacture_date,
    i.is_shared,
    -- Số tháng đã lưu tại đơn vị (NULL nếu tại Kho Tổng)
    CASE
        WHEN i.received_at_unit_date IS NOT NULL
        THEN CAST(
            (julianday(date('now', 'localtime')) - julianday(i.received_at_unit_date))
            / 30.44 AS INTEGER)
        ELSE NULL
    END AS months_at_unit,
    -- Số tháng còn lại trước khi hết niên hạn
    CASE
        WHEN i.received_at_unit_date IS NOT NULL AND i.manufacture_date IS NOT NULL
        THEN (t.total_lifespan_months -
              CAST((julianday(date('now','localtime')) - julianday(i.manufacture_date))
                   / 30.44 AS INTEGER))
        ELSE NULL
    END AS months_remaining,
    -- Cờ cảnh báo: còn <= 6 tháng trước khi lên H4
    CASE
        WHEN i.quality_level = 'H3'
         AND i.received_at_unit_date IS NOT NULL
         AND i.manufacture_date IS NOT NULL
         AND (t.total_lifespan_months -
              CAST((julianday(date('now','localtime')) - julianday(i.manufacture_date))
                   / 30.44 AS INTEGER)) <= 6
        THEN 1 ELSE 0
    END AS expiry_warning
FROM inventory i
JOIN warehouses w  ON w.id = i.warehouse_id
JOIN item_types t  ON t.id = i.item_type_id
WHERE i.quantity > 0;
