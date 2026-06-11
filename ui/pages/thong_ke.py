"""Trang Thống Kê Tồn Kho – dùng chung cho Kho, Đơn Vị, Hàng Dùng Chung."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor
import datetime
import database

FONT = "Segoe UI"

_TABLE_STYLE = """
    QTableWidget { border: none; background: white; outline: 0; gridline-color: transparent; }
    QHeaderView::section {
        background: white; color: #111; font-size: 12px;
        border: none; border-bottom: 1px solid #efefef;
        padding: 8px 12px; font-weight: normal;
    }
    QTableWidget::item {
        padding: 0 12px; border: none;
        color: #111; font-size: 13px;
    }
    QTableWidget::item:selected { background: #f5f7fa; color: #111; }
"""

_BADGE = {
    "H1": ("H1", "#1a7a4a", "#e6f4ed"),
    "H2": ("H2", "#1565c0", "#e3f0fb"),
    "H3": ("H3", "#e65100", "#fff3e0"),
    "H4": ("H4", "#c0392b", "#fdecea"),
}


# ── Summary cards ─────────────────────────────────────────────────────────────

class _SummaryCard(QFrame):
    def __init__(self, label: str, value: str, sub: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame { background: white; border: 1px solid #e8e8e8; border-radius: 10px; }
            QLabel { border: none; }
        """)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(4)

        lbl = QLabel(label)
        lbl.setFont(QFont(FONT, 11))
        lbl.setStyleSheet("color: #111;")
        v.addWidget(lbl)

        val = QLabel(value)
        val.setFont(QFont(FONT, 22, QFont.Weight.Bold))
        val.setStyleSheet("color: #111;")
        v.addWidget(val)

        if sub:
            s = QLabel(sub)
            s.setFont(QFont(FONT, 10))
            s.setStyleSheet("color: #aaa;")
            v.addWidget(s)

        self._val = val
        self._sub_lbl = QLabel(sub) if sub else None

    def set_value(self, value: str, sub: str = ""):
        self._val.setText(value)
        if self._sub_lbl:
            self._sub_lbl.setText(sub)


# ── Main page ─────────────────────────────────────────────────────────────────

class ThongKePage(QWidget):
    """
    mode = 'kho'        → Thống kê tại Kho Tổng (H1, H4)
    mode = 'don_vi'     → Thống kê tại Đơn Vị (H1–H4)
    mode = 'shared'     → Thống kê Hàng Dùng Chung
    """

    def __init__(self, mode: str):
        super().__init__()
        self._mode = mode
        self.setStyleSheet("ThongKePage { background: #fafafa; }")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 24)
        root.setSpacing(16)

        # ── Title + filter row ─────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel(self._page_title())
        title.setFont(QFont(FONT, 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #111;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Tìm kho / mặt hàng...")
        self._search.setFixedSize(260, 34)
        self._search.setFont(QFont(FONT, 12))
        self._search.setStyleSheet("""
            QLineEdit { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 0 12px; background: white; color: #111; }
            QLineEdit:focus { border-color: #bbb; }
        """)
        self._search.textChanged.connect(self._apply_filter)
        title_row.addWidget(self._search)

        self._wh_combo = QComboBox()
        self._wh_combo.setFixedHeight(34)
        self._wh_combo.setFont(QFont(FONT, 12))
        self._wh_combo.setMinimumWidth(180)
        self._wh_combo.setStyleSheet("""
            QComboBox { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 0 32px 0 12px; background: white; color: #111; }
            QComboBox::drop-down { subcontrol-origin: padding;
                subcontrol-position: center right; width: 28px;
                border-left: 1px solid #e0e0e0;
                border-top-right-radius: 8px; border-bottom-right-radius: 8px;
                background: white; }
            QComboBox::down-arrow { width: 10px; height: 10px; image: none;
                border-top: 5px solid #111;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent; }
            QComboBox QAbstractItemView { border: 1px solid #e0e0e0;
                border-radius: 6px; background: white; color: #111;
                selection-background-color: #f0f0f0; }
        """)
        self._wh_combo.addItem("Tất cả kho", None)
        self._wh_combo.currentIndexChanged.connect(self._apply_filter)
        title_row.addWidget(self._wh_combo)
        root.addLayout(title_row)

        # ── Summary cards ──────────────────────────────────────────────────
        card_row = QHBoxLayout()
        card_row.setSpacing(16)
        self._cards: dict[str, _SummaryCard] = {}
        for key, label in self._card_defs():
            card = _SummaryCard(label, "—")
            self._cards[key] = card
            card_row.addWidget(card)
        card_row.addStretch()
        root.addLayout(card_row)

        # ── Table card ─────────────────────────────────────────────────────
        tbl_card = QFrame()
        tbl_card.setStyleSheet(
            "QFrame { background: white; border-radius: 12px; border: 1px solid #efefef; }"
        )
        tbl_v = QVBoxLayout(tbl_card)
        tbl_v.setContentsMargins(0, 0, 0, 0)

        cols = self._table_columns()
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setStyleSheet(_TABLE_STYLE)
        self._setup_col_widths()
        tbl_v.addWidget(self._table)
        root.addWidget(tbl_card, 1)

        self.refresh()

    # ── Config per mode ───────────────────────────────────────────────────────

    def _page_title(self) -> str:
        return {
            "kho": "Tồn Kho – Tất Cả Kho",
            "don_vi": "Tồn Kho – Đơn Vị",
            "shared": "Tồn Kho – Hàng Dùng Chung",
        }[self._mode]

    def _card_defs(self) -> list[tuple[str, str]]:
        if self._mode == "kho":
            return [("total", "Tổng tồn"), ("h1", "H1"), ("h2", "H2"),
                    ("h3", "H3"), ("h4", "H4 (Chờ TXL)")]
        if self._mode == "don_vi":
            return [("total", "Tổng tồn"), ("h1", "H1"), ("h2", "H2"),
                    ("h3", "H3"), ("h4", "H4")]
        return [("total", "Tổng tồn"), ("borrowed", "Đang mượn"), ("available", "Sẵn sàng")]

    def _table_columns(self) -> list[str]:
        if self._mode == "kho":
            return ["STT", "Loại", "Kho / Đơn Vị", "Mã Hàng", "Tên Hàng",
                    "ĐVT", "H1", "H2", "H3", "H4", "Tổng"]
        if self._mode == "don_vi":
            return ["STT", "Đơn Vị", "Mã Hàng", "Tên Hàng", "ĐVT",
                    "H1", "H2", "H3", "H4", "Tổng", "Ngày Nhận ĐV"]
        return ["STT", "Kho", "Mã Hàng", "Tên Hàng", "ĐVT",
                "Tổng", "Đang Mượn", "Sẵn Sàng"]

    def _setup_col_widths(self):
        h = self._table.horizontalHeader()
        if self._mode == "kho":
            specs = [
                (QHeaderView.ResizeMode.Fixed, 52),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 56),
                (QHeaderView.ResizeMode.Fixed, 64),
                (QHeaderView.ResizeMode.Fixed, 64),
                (QHeaderView.ResizeMode.Fixed, 64),
                (QHeaderView.ResizeMode.Fixed, 64),
                (QHeaderView.ResizeMode.Fixed, 72),
            ]
        elif self._mode == "don_vi":
            specs = [
                (QHeaderView.ResizeMode.Fixed, 52),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 110),
            ]
        else:
            specs = [
                (QHeaderView.ResizeMode.Fixed, 52),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 88),
                (QHeaderView.ResizeMode.Fixed, 88),
            ]
        for i, (mode, w) in enumerate(specs):
            h.setSectionResizeMode(i, mode)
            if w:
                self._table.setColumnWidth(i, w)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        self._reload_warehouses()
        self._reload_data()

    def _reload_warehouses(self):
        current = self._wh_combo.currentData()
        self._wh_combo.blockSignals(True)
        self._wh_combo.clear()
        self._wh_combo.addItem("Tất cả", None)
        conn = database.get_conn()
        if self._mode == "kho":
            rows = conn.execute(
                "SELECT id, name, code, type FROM warehouses WHERE is_active=1 ORDER BY type, name"
            ).fetchall()
            for r in rows:
                prefix = "Kho" if r["type"] == "TONG" else "ĐV"
                self._wh_combo.addItem(f"[{prefix}] {r['code']} – {r['name']}", r["id"])
        else:
            wh_type = {"don_vi": "DON_VI", "shared": "TONG"}[self._mode]
            rows = conn.execute(
                "SELECT id, name, code FROM warehouses WHERE type=? AND is_active=1 ORDER BY name",
                (wh_type,)
            ).fetchall()
            for r in rows:
                self._wh_combo.addItem(f"{r['code']} – {r['name']}", r["id"])
        for i in range(self._wh_combo.count()):
            if self._wh_combo.itemData(i) == current:
                self._wh_combo.setCurrentIndex(i)
                break
        self._wh_combo.blockSignals(False)

    def _reload_data(self):
        conn = database.get_conn()
        wh_id = self._wh_combo.currentData()
        params: list = []

        if self._mode == "kho":
            base = """
                SELECT w.type AS wh_type, w.code AS wh_code, w.name AS wh_name,
                       t.code AS item_code, t.name AS item_name,
                       t.unit_of_measure,
                       SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END) AS h1,
                       SUM(CASE WHEN i.quality_level='H2' THEN i.quantity ELSE 0 END) AS h2,
                       SUM(CASE WHEN i.quality_level='H3' THEN i.quantity ELSE 0 END) AS h3,
                       SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END) AS h4,
                       SUM(i.quantity) AS total
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t  ON t.id = i.item_type_id
                WHERE i.is_shared = 0
            """
            if wh_id:
                base += " AND w.id = ?"
                params.append(wh_id)
            base += " GROUP BY w.id, t.id HAVING total > 0 ORDER BY w.type, w.name, t.name"
            rows = conn.execute(base, params).fetchall()
            self._raw = rows

            self._cards["total"].set_value(str(sum(r["total"] for r in rows)))
            self._cards["h1"].set_value(str(sum(r["h1"] for r in rows)))
            self._cards["h2"].set_value(str(sum(r["h2"] for r in rows)))
            self._cards["h3"].set_value(str(sum(r["h3"] for r in rows)))
            self._cards["h4"].set_value(str(sum(r["h4"] for r in rows)))

        elif self._mode == "don_vi":
            base = """
                SELECT w.code AS wh_code, w.name AS wh_name,
                       t.code AS item_code, t.name AS item_name,
                       t.unit_of_measure,
                       SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END) AS h1,
                       SUM(CASE WHEN i.quality_level='H2' THEN i.quantity ELSE 0 END) AS h2,
                       SUM(CASE WHEN i.quality_level='H3' THEN i.quantity ELSE 0 END) AS h3,
                       SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END) AS h4,
                       SUM(i.quantity) AS total,
                       MIN(i.received_at_unit_date) AS first_received
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t  ON t.id = i.item_type_id
                WHERE w.type = 'DON_VI' AND i.is_shared = 0
            """
            if wh_id:
                base += " AND w.id = ?"
                params.append(wh_id)
            base += " GROUP BY w.id, t.id HAVING total > 0 ORDER BY w.name, t.name"
            rows = conn.execute(base, params).fetchall()
            self._raw = rows

            total = sum(r["total"] for r in rows)
            self._cards["total"].set_value(str(total))
            self._cards["h1"].set_value(str(sum(r["h1"] for r in rows)))
            self._cards["h2"].set_value(str(sum(r["h2"] for r in rows)))
            self._cards["h3"].set_value(str(sum(r["h3"] for r in rows)))
            self._cards["h4"].set_value(str(sum(r["h4"] for r in rows)))

        else:  # shared
            base = """
                SELECT w.code AS wh_code, w.name AS wh_name,
                       t.code AS item_code, t.name AS item_name,
                       t.unit_of_measure,
                       SUM(i.quantity) AS total_qty,
                       COALESCE((
                           SELECT SUM(sb.quantity)
                           FROM shared_borrows sb
                           JOIN inventory si ON si.id = sb.inventory_id
                           WHERE si.item_type_id = t.id
                             AND si.warehouse_id = w.id
                             AND sb.status = 'DANG_MUON'
                       ), 0) AS borrowed
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t  ON t.id = i.item_type_id
                WHERE i.is_shared = 1
            """
            if wh_id:
                base += " AND w.id = ?"
                params.append(wh_id)
            base += " GROUP BY w.id, t.id HAVING total_qty > 0 ORDER BY w.name, t.name"
            rows = conn.execute(base, params).fetchall()
            self._raw = rows

            total = sum(r["total_qty"] for r in rows)
            borrowed = sum(r["borrowed"] for r in rows)
            self._cards["total"].set_value(str(total))
            self._cards["borrowed"].set_value(str(borrowed))
            self._cards["available"].set_value(str(total - borrowed))

        self._apply_filter()

    def _apply_filter(self):
        q = self._search.text().strip().lower()
        rows = self._raw if hasattr(self, "_raw") else []
        if q:
            rows = [r for r in rows
                    if q in r["item_name"].lower()
                    or q in r["item_code"].lower()
                    or q in r["wh_name"].lower()
                    or q in r["wh_code"].lower()]
        self._load_table(rows)

    def _load_table(self, rows):
        self._table.setRowCount(0)
        for i, r in enumerate(rows):
            ri = self._table.rowCount()
            self._table.insertRow(ri)
            self._table.setRowHeight(ri, 52)

            if self._mode == "kho":
                type_label = "Kho" if r["wh_type"] == "TONG" else "Đơn Vị"
                cells = [
                    (str(i + 1), True),
                    (type_label, True),
                    (r["wh_name"], False),
                    (r["item_code"], False),
                    (r["item_name"], False),
                    (r["unit_of_measure"], True),
                    (str(r["h1"]) if r["h1"] else "—", True),
                    (str(r["h2"]) if r["h2"] else "—", True),
                    (str(r["h3"]) if r["h3"] else "—", True),
                    (str(r["h4"]) if r["h4"] else "—", True),
                    (str(r["total"]), True),
                ]
            elif self._mode == "don_vi":
                cells = [
                    (str(i + 1), True),
                    (r["wh_name"], False),
                    (r["item_code"], False),
                    (r["item_name"], False),
                    (r["unit_of_measure"], True),
                    (str(r["h1"]) if r["h1"] else "—", True),
                    (str(r["h2"]) if r["h2"] else "—", True),
                    (str(r["h3"]) if r["h3"] else "—", True),
                    (str(r["h4"]) if r["h4"] else "—", True),
                    (str(r["total"]), True),
                    (r["first_received"] or "—", True),
                ]
            else:
                avail = r["total_qty"] - r["borrowed"]
                cells = [
                    (str(i + 1), True),
                    (r["wh_name"], False),
                    (r["item_code"], False),
                    (r["item_name"], False),
                    (r["unit_of_measure"], True),
                    (str(r["total_qty"]), True),
                    (str(r["borrowed"]) if r["borrowed"] else "—", True),
                    (str(avail) if avail else "—", True),
                ]

            for c, (val, center) in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 12))
                if center:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # highlight H4 column
                if ((self._mode == "kho" and c == 9) or
                        (self._mode == "don_vi" and c == 8)):
                    if val not in ("—", "0"):
                        cell.setForeground(Qt.GlobalColor.red)
                self._table.setItem(ri, c, cell)


# ── Thin wrappers ─────────────────────────────────────────────────────────────

class ThongKeDonViPage(ThongKePage):
    def __init__(self):
        super().__init__("don_vi")


class ThongKeSharedPage(ThongKePage):
    def __init__(self):
        super().__init__("shared")


# ── Per-warehouse tab page ────────────────────────────────────────────────────

class ThongKeKhoPage(QWidget):
    """Tồn kho theo từng kho/đơn vị — mỗi kho là một tab riêng."""

    _COLS = ["STT", "Mã Hàng", "Tên Hàng", "ĐVT", "Niên Hạn (Năm)", "Đơn Giá",
             "H1", "H2", "H3", "H4", "Tổng"]
    _COLS_SEARCH = ["STT", "Kho", "Mã Hàng", "Tên Hàng", "ĐVT", "Niên Hạn (Năm)", "Đơn Giá",
                    "H1", "H2", "H3", "H4", "Tổng"]

    def __init__(self):
        super().__init__()
        self.setStyleSheet("ThongKeKhoPage { background: #fafafa; }")
        self._wh_list: list = []
        self._active_wh_id: int | None = None
        self._raw: list = []
        self._year_map: dict = {}
        self._search_raw: list = []
        self._search_year_map: dict = {}
        self._was_searching: bool = False
        self._tab_btns: dict[int, QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 24)
        root.setSpacing(0)

        top = QHBoxLayout()
        title = QLabel("Tồn Kho – Tất Cả Kho")
        title.setFont(QFont(FONT, 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #111;")
        top.addWidget(title)
        top.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Tìm kiếm toàn kho")
        self._search.setFixedSize(260, 34)
        self._search.setFont(QFont(FONT, 12))
        self._search.setStyleSheet("""
            QLineEdit { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 0 12px; background: white; color: #111; }
            QLineEdit:focus { border-color: #bbb; }
        """)
        self._search.textChanged.connect(self._apply_filter)
        top.addWidget(self._search)
        root.addLayout(top)
        root.addSpacing(16)

        # ── Tab bar — hidden while searching ──────────────────────────────
        self._tab_row = QWidget()
        self._tab_row.setStyleSheet("background: transparent;")
        tab_row_v = QVBoxLayout(self._tab_row)
        tab_row_v.setContentsMargins(0, 0, 0, 16)
        tab_row_v.setSpacing(0)

        tab_frame = QFrame()
        tab_frame.setFixedHeight(44)
        tab_frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        tab_h = QHBoxLayout(tab_frame)
        tab_h.setContentsMargins(0, 4, 0, 4)
        tab_h.setSpacing(6)
        self._tab_layout = tab_h
        self._tab_layout.addStretch()
        tab_row_v.addWidget(tab_frame)
        root.addWidget(self._tab_row)

        # ── Summary cards ──────────────────────────────────────────────────
        card_h = QHBoxLayout()
        card_h.setSpacing(12)
        self._cards: dict[str, _SummaryCard] = {}
        for key, label in [("total", "Tổng"), ("h1", "H1"), ("h2", "H2"),
                            ("h3", "H3"), ("h4", "H4 (Chờ TXL)")]:
            c = _SummaryCard(label, "—")
            self._cards[key] = c
            card_h.addWidget(c)
        card_h.addStretch()

        _search_style = """
            QLineEdit { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 0 12px; background: white; color: #111; }
            QLineEdit:focus { border-color: #bbb; }
        """
        self._local_search = QLineEdit()
        self._local_search.setPlaceholderText("Tìm trong kho này...")
        self._local_search.setFixedSize(220, 34)
        self._local_search.setFont(QFont(FONT, 12))
        self._local_search.setStyleSheet(_search_style)
        self._local_search.textChanged.connect(self._apply_local_filter)
        card_h.addWidget(self._local_search)

        root.addLayout(card_h)
        root.addSpacing(16)

        # ── Table ──────────────────────────────────────────────────────────
        tbl_card = QFrame()
        tbl_card.setStyleSheet(
            "QFrame { background: white; border-radius: 12px; border: 1px solid #efefef; }"
        )
        tbl_v = QVBoxLayout(tbl_card)
        tbl_v.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setStyleSheet(_TABLE_STYLE)

        tbl_v.addWidget(self._table)
        root.addWidget(tbl_card, 1)

        self.refresh()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _rebuild_tabs(self):
        for btn in list(self._tab_btns.values()):
            self._tab_layout.removeWidget(btn)
            btn.deleteLater()
        self._tab_btns.clear()

        for r in self._wh_list:
            btn = QPushButton(r["code"])
            btn.setFont(QFont(FONT, 11))
            btn.setFixedHeight(32)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._tab_btns[r["id"]] = btn
            wid = r["id"]
            btn.clicked.connect(lambda _, w=wid: self._on_tab(w))
            self._tab_layout.insertWidget(self._tab_layout.count() - 1, btn)

        self._apply_tab_style()

    def _on_tab(self, wh_id: int):
        self._active_wh_id = wh_id
        self._apply_tab_style()
        self._search.clear()
        self._reload_data()

    def _apply_tab_style(self):
        for wid, btn in self._tab_btns.items():
            if wid == self._active_wh_id:
                btn.setStyleSheet("""
                    QPushButton { border: none; border-radius: 7px; padding: 0 14px;
                        background: #111; color: white; font-size: 11px; font-weight: 600; }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton { border: 1px solid #e0e0e0; border-radius: 7px; padding: 0 14px;
                        background: white; color: #111; font-size: 11px; }
                    QPushButton:hover { background: #f5f5f5; color: #111; }
                """)

    def _configure_table(self, search_mode: bool):
        cols = self._COLS_SEARCH if search_mode else self._COLS
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        h = self._table.horizontalHeader()
        specs = (
            [
                (QHeaderView.ResizeMode.Fixed, 52),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 56),
                (QHeaderView.ResizeMode.Fixed, 110),
                (QHeaderView.ResizeMode.Fixed, 120),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 80),
            ] if search_mode else [
                (QHeaderView.ResizeMode.Fixed, 52),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 56),
                (QHeaderView.ResizeMode.Fixed, 110),
                (QHeaderView.ResizeMode.Fixed, 120),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 80),
            ]
        )
        for i, (mode, w) in enumerate(specs):
            h.setSectionResizeMode(i, mode)
            if w:
                self._table.setColumnWidth(i, w)

    # ── Data ──────────────────────────────────────────────────────────────────

    def switch_to(self, wh_id: int):
        self._active_wh_id = wh_id
        self.refresh()

    def refresh(self):
        self._search_raw = []
        self._was_searching = False
        self._tab_row.setVisible(True)
        self._configure_table(search_mode=False)
        conn = database.get_conn()
        rows = conn.execute(
            "SELECT id, code, name, type FROM warehouses WHERE is_active=1 AND type='TONG' ORDER BY name"
        ).fetchall()
        self._wh_list = rows
        known_ids = {r["id"] for r in rows}
        if self._active_wh_id not in known_ids:
            self._active_wh_id = rows[0]["id"] if rows else None
        self._rebuild_tabs()
        self._reload_data()

    def _reload_data(self):
        if self._active_wh_id is None:
            self._raw = []
            self._update_cards([])
            self._apply_filter()
            return
        conn = database.get_conn()
        rows = conn.execute("""
            SELECT t.id AS item_type_id,
                   t.code AS item_code, t.name AS item_name,
                   t.unit_of_measure,
                   SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END) AS h1,
                   SUM(CASE WHEN i.quality_level='H2' THEN i.quantity ELSE 0 END) AS h2,
                   SUM(CASE WHEN i.quality_level='H3' THEN i.quantity ELSE 0 END) AS h3,
                   SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END) AS h4,
                   SUM(i.quantity) AS total,
                   MAX(CASE
                       WHEN i.received_at_unit_date IS NOT NULL
                       THEN CAST(
                           (julianday(date('now','localtime'))
                            - julianday(i.received_at_unit_date)) / 30.44 AS INTEGER)
                       ELSE NULL
                   END) AS max_months,
                   (SELECT tl.unit_price
                    FROM transaction_lines tl
                    JOIN transactions tx ON tx.id = tl.transaction_id
                    WHERE tl.item_type_id = t.id
                      AND tx.to_warehouse_id = ?
                      AND COALESCE(tl.unit_price, 0) > 0
                    ORDER BY tx.transaction_date DESC, tl.id DESC
                    LIMIT 1) AS don_gia
            FROM inventory i
            JOIN item_types t ON t.id = i.item_type_id
            WHERE i.warehouse_id = ? AND i.is_shared = 0 AND i.quantity > 0
            GROUP BY t.id
            ORDER BY t.name
        """, (self._active_wh_id, self._active_wh_id)).fetchall()
        self._raw = rows

        year = str(datetime.date.today().year)
        wh_id = self._active_wh_id
        yr_rows = conn.execute("""
            SELECT sub.item_type_id, sub.ql,
                   SUM(sub.nhap) AS nhap, SUM(sub.xuat) AS xuat
            FROM (
                SELECT tl.item_type_id, tl.quality_level_to AS ql,
                       tl.quantity AS nhap, 0 AS xuat
                FROM transaction_lines tl
                JOIN transactions tx ON tx.id = tl.transaction_id
                WHERE tx.to_warehouse_id = ?
                  AND strftime('%Y', tx.transaction_date) = ?
                  AND tl.quality_level_to IS NOT NULL
                UNION ALL
                SELECT tl.item_type_id, tl.quality_level_from AS ql,
                       0 AS nhap, tl.quantity AS xuat
                FROM transaction_lines tl
                JOIN transactions tx ON tx.id = tl.transaction_id
                WHERE tx.from_warehouse_id = ?
                  AND strftime('%Y', tx.transaction_date) = ?
                  AND tl.quality_level_from IS NOT NULL
            ) sub
            GROUP BY sub.item_type_id, sub.ql
        """, (wh_id, year, wh_id, year)).fetchall()
        self._year_map = {
            (r["item_type_id"], r["ql"]): (r["nhap"], r["xuat"])
            for r in yr_rows
        }

        self._update_cards(rows)
        self._apply_filter()

    def _load_search_data(self):
        conn = database.get_conn()
        year = str(datetime.date.today().year)
        self._search_raw = conn.execute("""
            SELECT w.id AS wh_id, w.code AS wh_code, w.name AS wh_name,
                   t.id AS item_type_id,
                   t.code AS item_code, t.name AS item_name,
                   t.unit_of_measure,
                   SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END) AS h1,
                   SUM(CASE WHEN i.quality_level='H2' THEN i.quantity ELSE 0 END) AS h2,
                   SUM(CASE WHEN i.quality_level='H3' THEN i.quantity ELSE 0 END) AS h3,
                   SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END) AS h4,
                   SUM(i.quantity) AS total,
                   MAX(CASE
                       WHEN i.received_at_unit_date IS NOT NULL
                       THEN CAST(
                           (julianday(date('now','localtime'))
                            - julianday(i.received_at_unit_date)) / 30.44 AS INTEGER)
                       ELSE NULL
                   END) AS max_months,
                   (SELECT tl2.unit_price
                    FROM transaction_lines tl2
                    JOIN transactions tx2 ON tx2.id = tl2.transaction_id
                    WHERE tl2.item_type_id = t.id
                      AND tx2.to_warehouse_id = w.id
                      AND COALESCE(tl2.unit_price, 0) > 0
                    ORDER BY tx2.transaction_date DESC, tl2.id DESC
                    LIMIT 1) AS don_gia
            FROM inventory i
            JOIN warehouses w ON w.id = i.warehouse_id
            JOIN item_types t ON t.id = i.item_type_id
            WHERE i.is_shared = 0 AND i.quantity > 0
              AND w.type = 'TONG' AND w.is_active = 1
            GROUP BY w.id, t.id
            ORDER BY t.name, w.name
        """).fetchall()

        yr_rows = conn.execute("""
            SELECT sub.wh_id, sub.item_type_id, sub.ql,
                   SUM(sub.nhap) AS nhap, SUM(sub.xuat) AS xuat
            FROM (
                SELECT tx.to_warehouse_id AS wh_id,
                       tl.item_type_id, tl.quality_level_to AS ql,
                       tl.quantity AS nhap, 0 AS xuat
                FROM transaction_lines tl
                JOIN transactions tx ON tx.id = tl.transaction_id
                JOIN warehouses w ON w.id = tx.to_warehouse_id
                WHERE w.type = 'TONG' AND w.is_active = 1
                  AND strftime('%Y', tx.transaction_date) = ?
                  AND tl.quality_level_to IS NOT NULL
                UNION ALL
                SELECT tx.from_warehouse_id AS wh_id,
                       tl.item_type_id, tl.quality_level_from AS ql,
                       0 AS nhap, tl.quantity AS xuat
                FROM transaction_lines tl
                JOIN transactions tx ON tx.id = tl.transaction_id
                JOIN warehouses w ON w.id = tx.from_warehouse_id
                WHERE w.type = 'TONG' AND w.is_active = 1
                  AND strftime('%Y', tx.transaction_date) = ?
                  AND tl.quality_level_from IS NOT NULL
            ) sub
            GROUP BY sub.wh_id, sub.item_type_id, sub.ql
        """, (year, year)).fetchall()
        self._search_year_map = {
            (r["wh_id"], r["item_type_id"], r["ql"]): (r["nhap"], r["xuat"])
            for r in yr_rows
        }

    def _update_cards(self, rows):
        self._cards["total"].set_value(str(sum(r["total"] for r in rows)))
        for ql in ("h1", "h2", "h3", "h4"):
            self._cards[ql].set_value(str(sum(r[ql] for r in rows)))

    def _apply_filter(self):
        q = self._search.text().strip().lower()
        is_searching = bool(q)

        if is_searching and not self._was_searching:
            self._load_search_data()
            self._configure_table(search_mode=True)
            self._tab_row.setVisible(False)
            self._local_search.setVisible(False)
            self._local_search.clear()
        elif not is_searching and self._was_searching:
            self._configure_table(search_mode=False)
            self._tab_row.setVisible(True)
            self._local_search.setVisible(True)

        self._was_searching = is_searching

        if is_searching:
            rows = [r for r in self._search_raw
                    if q in r["item_name"].lower() or q in r["item_code"].lower()
                    or q in r["wh_name"].lower() or q in r["wh_code"].lower()]
            self._load_table(rows, search_mode=True)
        else:
            self._apply_local_filter()

    def _apply_local_filter(self):
        q = self._local_search.text().strip().lower()
        rows = self._raw if not q else [
            r for r in self._raw
            if q in r["item_name"].lower() or q in r["item_code"].lower()
        ]
        self._load_table(rows, search_mode=False)

    def _load_table(self, rows, search_mode: bool = False):
        self._table.setRowCount(0)
        for i, r in enumerate(rows):
            ri = self._table.rowCount()
            self._table.insertRow(ri)
            self._table.setRowHeight(ri, 48)

            mm = r["max_months"]
            nien_han = f"{mm // 12} năm" if mm is not None else "—"
            nien_han_red = mm is not None and mm >= 24

            dg = r["don_gia"]
            don_gia = f"{int(dg):,}".replace(",", ".") if dg else "—"

            tid = r["item_type_id"]

            def _tip(ql: str, current: int) -> str:
                if search_mode:
                    nhap, xuat = self._search_year_map.get((r["wh_id"], tid, ql), (0, 0))
                else:
                    nhap, xuat = self._year_map.get((tid, ql), (0, 0))
                so_du = current - nhap + xuat

                def _row(label, val, last=False):
                    sep = "" if last else "border-bottom: 1px solid #ebebeb;"
                    return (
                        f'<tr>'
                        f'<td style="padding: 9px 28px 9px 0; color: #111; {sep}">{label}</td>'
                        f'<td style="padding: 9px 0; color: #111; font-weight: 600; text-align: right; {sep}">{val}</td>'
                        f'</tr>'
                    )

                return (
                    '<table style="font-family: \'Segoe UI\'; font-size: 13px;'
                    ' min-width: 230px; border-spacing: 0;">'
                    '<tr><td colspan="2" style="padding: 0 0 10px 0;">'
                    '<b style="font-size: 14px; color: #111;">Thông tin Chi tiết</b>'
                    '</td></tr>'
                    + _row("Số dư đầu năm", so_du)
                    + _row("Tổng nhập", nhap)
                    + _row("Tổng xuất", xuat)
                    + _row("Hiện tại", current, last=True)
                    + '</table>'
                )

            if search_mode:
                cells = [
                    (str(i + 1),           True,  False, None),
                    (r["wh_code"],         True,  False, None),
                    (r["item_code"],       False, False, None),
                    (r["item_name"],       False, False, None),
                    (r["unit_of_measure"], True,  False, None),
                    (nien_han,             True,  nien_han_red, None),
                    (don_gia,              True,  False, None),
                    (str(r["h1"]),         True,  False, _tip("H1", r["h1"])),
                    (str(r["h2"]),         True,  False, _tip("H2", r["h2"])),
                    (str(r["h3"]),         True,  False, _tip("H3", r["h3"])),
                    (str(r["h4"]),         True,  r["h4"] > 0, _tip("H4", r["h4"])),
                    (str(r["total"]),      True,  False, None),
                ]
            else:
                cells = [
                    (str(i + 1),           True,  False, None),
                    (r["item_code"],       False, False, None),
                    (r["item_name"],       False, False, None),
                    (r["unit_of_measure"], True,  False, None),
                    (nien_han,             True,  nien_han_red, None),
                    (don_gia,              True,  False, None),
                    (str(r["h1"]),         True,  False, _tip("H1", r["h1"])),
                    (str(r["h2"]),         True,  False, _tip("H2", r["h2"])),
                    (str(r["h3"]),         True,  False, _tip("H3", r["h3"])),
                    (str(r["h4"]),         True,  r["h4"] > 0, _tip("H4", r["h4"])),
                    (str(r["total"]),      True,  False, None),
                ]

            for c, (val, center, red, tip) in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 12))
                if center:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if red:
                    cell.setForeground(Qt.GlobalColor.red)
                if tip:
                    cell.setToolTip(tip)
                self._table.setItem(ri, c, cell)
