"""Trang Thống Kê Tồn Kho – dùng chung cho Kho, Đơn Vị, Hàng Dùng Chung."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor
import database

FONT = "Segoe UI"

_TABLE_STYLE = """
    QTableWidget { border: none; background: white; outline: 0; gridline-color: transparent; }
    QHeaderView::section {
        background: white; color: #aaa; font-size: 12px;
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
        lbl.setStyleSheet("color: #888;")
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
            "kho": "Tồn Kho – Kho Tổng",
            "don_vi": "Tồn Kho – Đơn Vị",
            "shared": "Tồn Kho – Hàng Dùng Chung",
        }[self._mode]

    def _card_defs(self) -> list[tuple[str, str]]:
        if self._mode == "kho":
            return [("total", "Tổng tồn"), ("h1", "H1 (Mới)"), ("h4", "H4 (Chờ TXL)")]
        if self._mode == "don_vi":
            return [("total", "Tổng tồn"), ("h1", "H1"), ("h2", "H2"),
                    ("h3", "H3"), ("h4", "H4")]
        return [("total", "Tổng tồn"), ("borrowed", "Đang mượn"), ("available", "Sẵn sàng")]

    def _table_columns(self) -> list[str]:
        if self._mode == "kho":
            return ["STT", "Kho", "Mã Hàng", "Tên Hàng", "ĐVT", "H1", "H4", "Tổng"]
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
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 100),
                (QHeaderView.ResizeMode.Stretch, None),
                (QHeaderView.ResizeMode.Fixed, 60),
                (QHeaderView.ResizeMode.Fixed, 72),
                (QHeaderView.ResizeMode.Fixed, 72),
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
        wh_type = {"kho": "TONG", "don_vi": "DON_VI", "shared": "TONG"}[self._mode]
        rows = conn.execute(
            "SELECT id, name, code FROM warehouses WHERE type=? AND is_active=1 ORDER BY name",
            (wh_type,)
        ).fetchall()
        for r in rows:
            self._wh_combo.addItem(f"{r['code']} – {r['name']}", r["id"])
        # restore selection
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
                SELECT w.code AS wh_code, w.name AS wh_name,
                       t.code AS item_code, t.name AS item_name,
                       t.unit_of_measure,
                       SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END) AS h1,
                       SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END) AS h4,
                       SUM(i.quantity) AS total
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t  ON t.id = i.item_type_id
                WHERE w.type = 'TONG' AND i.is_shared = 0
            """
            if wh_id:
                base += " AND w.id = ?"
                params.append(wh_id)
            base += " GROUP BY w.id, t.id HAVING total > 0 ORDER BY w.name, t.name"
            rows = conn.execute(base, params).fetchall()
            self._raw = rows

            total = sum(r["total"] for r in rows)
            h1 = sum(r["h1"] for r in rows)
            h4 = sum(r["h4"] for r in rows)
            self._cards["total"].set_value(str(total))
            self._cards["h1"].set_value(str(h1))
            self._cards["h4"].set_value(str(h4))

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
                cells = [
                    (str(i + 1), True),
                    (r["wh_name"], False),
                    (r["item_code"], False),
                    (r["item_name"], False),
                    (r["unit_of_measure"], True),
                    (str(r["h1"]) if r["h1"] else "—", True),
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
                if ((self._mode == "kho" and c == 6) or
                        (self._mode == "don_vi" and c == 8)):
                    if val not in ("—", "0"):
                        cell.setForeground(Qt.GlobalColor.red)
                self._table.setItem(ri, c, cell)


# ── Thin wrappers ─────────────────────────────────────────────────────────────

class ThongKeKhoPage(ThongKePage):
    def __init__(self):
        super().__init__("kho")


class ThongKeDonViPage(ThongKePage):
    def __init__(self):
        super().__init__("don_vi")


class ThongKeSharedPage(ThongKePage):
    def __init__(self):
        super().__init__("shared")
