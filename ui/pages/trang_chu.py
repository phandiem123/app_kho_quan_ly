import database
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QCursor, QAction
from ui.dialogs.warehouse_form import WarehouseFormDialog
from ui.dialogs.item_type_form import ItemTypeFormDialog
from ui.topbar import TopBar
from database.warehouses import Warehouse, get_all as wh_get_all, soft_delete as wh_soft_delete
from database.item_types import ItemType, get_all as item_get_all, soft_delete as item_soft_delete

FONT = "Segoe UI"
_TYPE_LABEL = {"TONG": "Kho Tổng", "DON_VI": "Đơn Vị"}

_TABLE_STYLE = """
    QTableWidget { border: none; background: white; outline: 0; }
    QHeaderView::section {
        background: white; color: #111; font-size: 12px;
        border: none; border-bottom: 1px solid #efefef;
        padding: 8px 12px; font-weight: normal;
    }
    QTableWidget::item {
        padding: 0 12px; border-bottom: 1px solid #f5f5f5;
        color: #1a1a1a; font-size: 13px;
    }
    QTableWidget::item:selected { background: #f5f7fa; color: #1a1a1a; }
"""


# ── Stat Card ─────────────────────────────────────────────────────────────────
class StatCard(QWidget):
    def __init__(self, icon: str, title: str, value: str, color: str = "#111"):
        super().__init__()
        self.setStyleSheet(
            "StatCard { background: white; border: 1px solid #efefef; border-radius: 12px; }"
        )
        self.setFixedHeight(82)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(4)

        # Icon + number on same row
        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)
        ico = QLabel(icon)
        ico.setFont(QFont(FONT, 15))
        ico.setStyleSheet("border: none;")
        top.addWidget(ico)
        val_lbl = QLabel(str(value))
        val_lbl.setFont(QFont(FONT, 22, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {color}; border: none;")
        top.addWidget(val_lbl)
        top.addStretch()
        v.addLayout(top)

        ttl_lbl = QLabel(title)
        ttl_lbl.setFont(QFont(FONT, 10))
        ttl_lbl.setStyleSheet("color: #888; border: none;")
        v.addWidget(ttl_lbl)


# ── Compact read-only table ────────────────────────────────────────────────────
class _CompactTable(QTableWidget):
    def __init__(self, cols: list[str]):
        super().__init__(0, len(cols))
        self.setHorizontalHeaderLabels(cols)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(_TABLE_STYLE)
        self.setMaximumHeight(210)

    def _cell(self, text: str, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
              color: str | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFont(QFont(FONT, 12))
        item.setTextAlignment(align)
        if color:
            from PyQt6.QtGui import QColor
            item.setForeground(QColor(color))
        return item

    def load_empty(self, message: str = "Không có dữ liệu"):
        self.setRowCount(1)
        self.setRowHeight(0, 44)
        empty = QTableWidgetItem(message)
        empty.setFont(QFont(FONT, 12))
        empty.setForeground(Qt.GlobalColor.gray)
        empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(0, 0, empty)
        self.setSpan(0, 0, 1, self.columnCount())


# ── Generic "···" action button ───────────────────────────────────────────────
class DotsButton(QPushButton):
    def __init__(self, data, on_view, on_edit, on_delete):
        super().__init__("···")
        self._data = data
        self._on_view = on_view
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setFlat(True)
        self.setFont(QFont(FONT, 15))
        self.setFixedSize(40, 40)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("""
            QPushButton {
                color: #bbb; border: none; background: transparent;
                letter-spacing: 2px; border-radius: 6px;
            }
            QPushButton:hover { background: #f0f0f0; color: #555; }
        """)

    def enterEvent(self, event):
        self._show_menu()
        super().enterEvent(event)

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white; border: 1px solid #e5e5e5;
                border-radius: 8px; padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px; font-size: 13px;
                border-radius: 6px; color: #1a1a1a;
            }
            QMenu::item:selected { background: #f5f5f5; }
            QMenu::separator { height: 1px; background: #efefef; margin: 2px 8px; }
        """)
        act_edit = QAction("Sửa", self)
        act_edit.triggered.connect(lambda: self._on_edit(self._data))
        act_del = QAction("Xóa", self)
        act_del.triggered.connect(lambda: self._on_delete(self._data))
        menu.addAction(act_edit)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))


# ── Bảng Kho / Đơn Vị ────────────────────────────────────────────────────────
class KhoTable(QTableWidget):
    COLS = ["STT", "Tên Kho", "Loại", "Địa Chỉ", "Ghi Chú", ""]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(_TABLE_STYLE)
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 56)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(5, 52)

    def set_type_col_visible(self, visible: bool):
        self.setColumnHidden(2, not visible)

    def load(self, warehouses: list[Warehouse], on_edit=None, on_delete=None):
        self.setRowCount(0)
        for i, wh in enumerate(warehouses):
            r = self.rowCount()
            self.insertRow(r)
            self.setRowHeight(r, 52)
            cells = [str(i + 1), wh.name,
                     _TYPE_LABEL.get(wh.type, wh.type), wh.address or "", wh.notes or ""]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setFont(QFont(FONT, 12))
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, col, item)
            if on_edit or on_delete:
                btn = DotsButton(wh, None, on_edit, on_delete)
                self.setCellWidget(r, 5, btn)


# ── Bảng Hàng Hoá ─────────────────────────────────────────────────────────────
class HangHoaTable(QTableWidget):
    COLS = ["STT", "Tên Hàng", "Đơn Vị Tính", "Niên Hạn (năm)", "Đơn Giá", "Ghi Chú", ""]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(_TABLE_STYLE)
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 56)
        self.setColumnWidth(2, 120)
        self.setColumnWidth(3, 130)
        self.setColumnWidth(4, 120)
        self.setColumnWidth(6, 52)

    def load(self, items: list[ItemType], on_edit=None, on_delete=None):
        self.setRowCount(0)
        for i, it in enumerate(items):
            r = self.rowCount()
            self.insertRow(r)
            self.setRowHeight(r, 52)
            months = it.total_lifespan_months
            years_str = f"{months // 12}" if months % 12 == 0 else f"{months / 12:.1f}"
            price_str = f"{it.unit_price:,.0f}" if it.unit_price else "—"
            cells = [str(i + 1), it.name,
                     it.unit_of_measure, years_str, price_str, it.notes or ""]
            for col, val in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 12))
                if col in (0, 3, 4):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, col, cell)
            if on_edit or on_delete:
                btn = DotsButton(it, None, on_edit, on_delete)
                self.setCellWidget(r, 6, btn)


# ── Helper: info section frame ─────────────────────────────────────────────────
def _info_frame(title: str, count_lbl: QLabel, table: _CompactTable) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet("""
        QFrame { background: white; border: 1px solid #efefef; border-radius: 12px; }
    """)
    v = QVBoxLayout(frame)
    v.setContentsMargins(18, 14, 18, 14)
    v.setSpacing(10)
    hdr = QHBoxLayout()
    lbl = QLabel(title)
    lbl.setFont(QFont(FONT, 12, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #111; border: none;")
    hdr.addWidget(lbl)
    hdr.addStretch()
    count_lbl.setFont(QFont(FONT, 11))
    count_lbl.setStyleSheet("color: #888; border: none;")
    hdr.addWidget(count_lbl)
    v.addLayout(hdr)
    v.addWidget(table)
    return frame


# ── Trang Chủ ─────────────────────────────────────────────────────────────────
class TrangChuPage(QWidget):
    TABS = ["Thống Kê Nhanh", "Kho", "Đơn Vị", "Hàng Hoá"]

    def __init__(self):
        super().__init__()
        self.setStyleSheet("TrangChuPage { background: #fafafa; }")
        self._active_type = "STATS"
        self._cache: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 32)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        greet = QLabel("Trang Chủ")
        greet.setFont(QFont(FONT, 22, QFont.Weight.Bold))
        greet.setStyleSheet("color: #111;")
        root.addWidget(greet)

        sub = QLabel("Tổng quan hệ thống quản lý kho hàng DCCD")
        sub.setFont(QFont(FONT, 12))
        sub.setStyleSheet("color: #888; margin-top: 4px;")
        root.addWidget(sub)

        root.addSpacing(24)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #eee;")
        root.addWidget(sep)
        root.addSpacing(20)

        # ── TopBar ────────────────────────────────────────────────────────────
        self.topbar = TopBar(self.TABS, active_tab=0)
        self.topbar.tab_bar.tab_changed.connect(self._on_tab)
        self.topbar.search.textChanged.connect(self._on_search)
        self.topbar.search.setVisible(False)   # hidden on stats tab
        root.addWidget(self.topbar)
        root.addSpacing(20)

        # ── Stats panel (tab 0) ───────────────────────────────────────────────
        self._stats_panel = QWidget()
        self._stats_panel.setStyleSheet("background: transparent;")
        sv = QVBoxLayout(self._stats_panel)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        self._alert_row = QHBoxLayout()
        self._alert_row.setSpacing(12)
        sv.addLayout(self._alert_row)
        sv.addSpacing(16)

        lists_row = QHBoxLayout()
        lists_row.setSpacing(20)

        self._lbl_borrow_count = QLabel()
        self._borrow_table = _CompactTable(["Tên Đơn Vị", "SL Đang Mượn"])
        bh = self._borrow_table.horizontalHeader()
        bh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        bh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._borrow_table.setColumnWidth(1, 110)
        lists_row.addWidget(
            _info_frame("Đơn Vị Chưa Trả Hàng Dùng Chung",
                        self._lbl_borrow_count, self._borrow_table), 1
        )

        self._lbl_h4_count = QLabel()
        self._h4_table = _CompactTable(["Tên Hàng", "ĐVT", "Số Lượng"])
        hh = self._h4_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._h4_table.setColumnWidth(1, 64)
        self._h4_table.setColumnWidth(2, 90)
        lists_row.addWidget(
            _info_frame("Hàng H4 Tại Kho",
                        self._lbl_h4_count, self._h4_table), 1
        )

        sv.addLayout(lists_row)
        root.addWidget(self._stats_panel)

        # ── CRUD panel (tabs 1-3) ─────────────────────────────────────────────
        self._crud_panel = QWidget()
        self._crud_panel.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(self._crud_panel)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)

        title_row = QHBoxLayout()
        self._section_title = QLabel("Danh Sách Kho")
        self._section_title.setFont(QFont(FONT, 15))
        self._section_title.setStyleSheet("color: #111;")
        title_row.addWidget(self._section_title)
        title_row.addStretch()

        self._btn_add = QPushButton("+ Thêm Kho")
        self._btn_add.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        self._btn_add.setFixedHeight(36)
        self._btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_add.setStyleSheet("""
            QPushButton {
                background: #111; color: white; border: none;
                border-radius: 8px; padding: 0 20px;
            }
            QPushButton:hover { background: #333; }
        """)
        self._btn_add.clicked.connect(self._on_add)
        title_row.addWidget(self._btn_add)
        cv.addLayout(title_row)
        cv.addSpacing(12)

        self.table = KhoTable()
        cv.addWidget(self.table)

        self.item_table = HangHoaTable()
        self.item_table.setVisible(False)
        cv.addWidget(self.item_table)

        self._crud_panel.setVisible(False)
        root.addWidget(self._crud_panel)

        self.refresh()

    # ── Data loading ──────────────────────────────────────────────────────────

    def refresh(self):
        conn = database.get_conn()

        # ── Alert cards ────────────────────────────────────────────────
        while self._alert_row.count():
            item = self._alert_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dc_qty = conn.execute("""
            SELECT COALESCE(SUM(tl.quantity), 0) AS qty
            FROM shared_borrows sb
            JOIN transaction_lines tl ON tl.transaction_id = sb.transaction_id
            WHERE sb.status = 'DANG_MUON'
        """).fetchone()["qty"] or 0

        h4_returned = conn.execute("""
            SELECT COALESCE(SUM(tl.quantity), 0) AS qty
            FROM transactions tx
            JOIN transaction_lines tl ON tl.transaction_id = tx.id
            WHERE tx.type = 'NHAP_KHO'
              AND tx.from_warehouse_id IS NOT NULL
              AND tl.quality_level_to = 'H4'
              AND tx.transaction_date >= date('now', '-30 days')
        """).fetchone()["qty"] or 0

        txl_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM transactions WHERE type = 'THANH_XU_LY'"
        ).fetchone()["cnt"] or 0

        for icon, title, value, color in [
            ("🔄", "Hàng DC Đang Cho Mượn",    dc_qty,      "#e65100" if dc_qty > 0 else "#111"),
            ("↩",  "H4 Từ ĐV Trả Về (30 Ngày)", h4_returned, "#111"),
            ("📋", "Phiếu TXL",                  txl_count,   "#d32f2f" if txl_count > 0 else "#111"),
        ]:
            self._alert_row.addWidget(StatCard(icon, title, value, color))
        self._alert_row.addStretch()

        # ── Bảng: Đơn Vị Chưa Trả Hàng DC ───────────────────────────────────
        borrow_rows = conn.execute("""
            SELECT w.code, w.name,
                   COALESCE(SUM(tl.quantity), 0) AS total_qty
            FROM shared_borrows sb
            JOIN warehouses w ON w.id = sb.borrowing_warehouse_id
            JOIN transaction_lines tl ON tl.transaction_id = sb.transaction_id
            WHERE sb.status = 'DANG_MUON'
            GROUP BY w.id
            ORDER BY w.name
        """).fetchall()

        self._borrow_table.clearSpans()
        self._borrow_table.setRowCount(0)
        if borrow_rows:
            self._lbl_borrow_count.setText(f"{len(borrow_rows)} đơn vị")
            for r in borrow_rows:
                row = self._borrow_table.rowCount()
                self._borrow_table.insertRow(row)
                self._borrow_table.setRowHeight(row, 44)
                for col, val in enumerate([r["name"], str(r["total_qty"])]):
                    align = (Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                             if col == 1 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    item = QTableWidgetItem(val)
                    item.setFont(QFont(FONT, 12))
                    item.setTextAlignment(align)
                    self._borrow_table.setItem(row, col, item)
        else:
            self._lbl_borrow_count.setText("Tất cả đã trả ✓")
            self._borrow_table.load_empty("Không có đơn vị nào đang mượn")

        # ── Bảng: H4 Tại Kho ─────────────────────────────────────────────────
        h4_rows = conn.execute("""
            SELECT t.code, t.name, t.unit_of_measure,
                   SUM(i.quantity) AS qty
            FROM inventory i
            JOIN warehouses w ON w.id = i.warehouse_id
            JOIN item_types t  ON t.id = i.item_type_id
            WHERE w.type = 'TONG' AND i.quality_level = 'H4'
              AND i.is_shared = 0 AND i.quantity > 0
            GROUP BY t.id
            ORDER BY t.name
        """).fetchall()

        self._h4_table.clearSpans()
        self._h4_table.setRowCount(0)
        if h4_rows:
            total_h4 = sum(r["qty"] for r in h4_rows)
            self._lbl_h4_count.setText(f"{total_h4} chiếc")
            self._lbl_h4_count.setStyleSheet("color: #d32f2f; border: none;")
            for r in h4_rows:
                row = self._h4_table.rowCount()
                self._h4_table.insertRow(row)
                self._h4_table.setRowHeight(row, 44)
                for col, val in enumerate([r["name"],
                                           r["unit_of_measure"], str(r["qty"])]):
                    align = (Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                             if col in (1, 2) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    item = QTableWidgetItem(val)
                    item.setFont(QFont(FONT, 12))
                    item.setTextAlignment(align)
                    self._h4_table.setItem(row, col, item)
        else:
            self._lbl_h4_count.setText("Không có")
            self._lbl_h4_count.setStyleSheet("color: #888; border: none;")
            self._h4_table.load_empty("Không có hàng H4 tại kho")

        if self._active_type != "STATS":
            self._reload_cache()

    def _reload_cache(self):
        if self._active_type == "STATS":
            return
        if self._active_type in ("TONG", "DON_VI"):
            self._cache = wh_get_all(wh_type=self._active_type)
        else:
            self._cache = item_get_all()
        self._apply_filter()

    def _apply_filter(self):
        if self._active_type == "STATS":
            return
        query = self.topbar.search.text().strip().lower()
        if self._active_type in ("TONG", "DON_VI"):
            data = [w for w in self._cache
                    if not query
                    or query in w.name.lower()
                    or query in w.code.lower()
                    or query in (w.address or "").lower()]
            self.table.set_type_col_visible(False)
            self.table.load(data, on_edit=self._edit_warehouse, on_delete=self._delete_warehouse)
            self.table.setVisible(True)
            self.item_table.setVisible(False)
        else:
            data = [i for i in self._cache
                    if not query
                    or query in i.name.lower()
                    or query in i.code.lower()
                    or query in i.unit_of_measure.lower()]
            self.item_table.load(data, on_edit=self._edit_item, on_delete=self._delete_item)
            self.item_table.setVisible(True)
            self.table.setVisible(False)

    def _on_search(self, _: str):
        self._apply_filter()

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _on_tab(self, idx: int):
        self.topbar.search.clear()
        is_stats = (idx == 0)
        self._stats_panel.setVisible(is_stats)
        self._crud_panel.setVisible(not is_stats)
        self.topbar.search.setVisible(not is_stats)

        if idx == 0:
            self._active_type = "STATS"
        elif idx == 1:
            self._active_type = "TONG"
            self._section_title.setText("Danh Sách Kho")
            self._btn_add.setText("+ Thêm Kho")
            self._reload_cache()
        elif idx == 2:
            self._active_type = "DON_VI"
            self._section_title.setText("Danh Sách Đơn Vị")
            self._btn_add.setText("+ Thêm Đơn Vị")
            self._reload_cache()
        else:
            self._active_type = "HANG_HOA"
            self._section_title.setText("Danh Sách Hàng Hoá")
            self._btn_add.setText("+ Thêm Hàng Hoá")
            self._reload_cache()

    # ── Add dispatcher ────────────────────────────────────────────────────────

    def _on_add(self):
        if self._active_type in ("TONG", "DON_VI"):
            self._add_warehouse()
        else:
            self._add_item()

    # ── Warehouse CRUD ────────────────────────────────────────────────────────

    def _add_warehouse(self):
        dlg = WarehouseFormDialog(self, default_type=self._active_type)
        if dlg.exec():
            self.refresh()

    def _edit_warehouse(self, wh: Warehouse):
        dlg = WarehouseFormDialog(self, warehouse=wh)
        if dlg.exec():
            self.refresh()

    def _delete_warehouse(self, wh: Warehouse):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa <b>{wh.name}</b>?<br>"
            f"Dữ liệu lịch sử vẫn được giữ lại.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            wh_soft_delete(wh.id)
            self.refresh()

    def _view_warehouse(self, wh: Warehouse):
        QMessageBox.information(
            self, "Chi Tiết Kho",
            f"<b>Tên:</b> {wh.name}<br>"
            f"<b>Mã:</b> {wh.code}<br>"
            f"<b>Loại:</b> {_TYPE_LABEL.get(wh.type, wh.type)}<br>"
            f"<b>Địa chỉ:</b> {wh.address or '—'}<br>"
            f"<b>Ghi chú:</b> {wh.notes or '—'}",
        )

    # ── Item CRUD ─────────────────────────────────────────────────────────────

    def _add_item(self):
        dlg = ItemTypeFormDialog(self)
        if dlg.exec():
            self.refresh()

    def _edit_item(self, it: ItemType):
        dlg = ItemTypeFormDialog(self, item=it)
        if dlg.exec():
            self.refresh()

    def _delete_item(self, it: ItemType):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa hàng hoá <b>{it.name}</b>?<br>"
            f"Dữ liệu lịch sử vẫn được giữ lại.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            item_soft_delete(it.id)
            self.refresh()

    def _view_item(self, it: ItemType):
        QMessageBox.information(
            self, "Chi Tiết Hàng Hoá",
            f"<b>Tên:</b> {it.name}<br>"
            f"<b>Mã:</b> {it.code}<br>"
            f"<b>Đơn vị tính:</b> {it.unit_of_measure}<br>"
            f"<b>Niên hạn tổng:</b> {it.total_lifespan_months} tháng<br>"
            f"<b>Ghi chú:</b> {it.notes or '—'}",
        )
