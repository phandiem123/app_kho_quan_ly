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
from database.warehouses import Warehouse, get_all as wh_get_all, get_stats, soft_delete as wh_soft_delete
from database.item_types import ItemType, get_all as item_get_all, soft_delete as item_soft_delete

FONT = "Segoe UI"
_TYPE_LABEL = {"TONG": "Kho Tổng", "DON_VI": "Đơn Vị"}

_TABLE_STYLE = """
    QTableWidget { border: none; background: white; outline: 0; }
    QHeaderView::section {
        background: white; color: #aaa; font-size: 12px;
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
        self.setStyleSheet("""
            StatCard {
                background: white;
                border: 1px solid #efefef;
                border-radius: 12px;
            }
        """)
        self.setMinimumHeight(120)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(8)
        row = QHBoxLayout()
        ico = QLabel(icon)
        ico.setFont(QFont(FONT, 20))
        ico.setStyleSheet("border: none;")
        row.addWidget(ico)
        row.addStretch()
        v.addLayout(row)
        val_lbl = QLabel(str(value))
        val_lbl.setFont(QFont(FONT, 28, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {color}; border: none;")
        v.addWidget(val_lbl)
        ttl_lbl = QLabel(title)
        ttl_lbl.setFont(QFont(FONT, 11))
        ttl_lbl.setStyleSheet("color: #999; border: none;")
        v.addWidget(ttl_lbl)


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
        # act_view = QAction("Xem Chi Tiết", self)
        # act_view.triggered.connect(lambda: self._on_view(self._data))
        act_edit = QAction("Sửa", self)
        act_edit.triggered.connect(lambda: self._on_edit(self._data))
        act_del = QAction("Xóa", self)
        act_del.triggered.connect(lambda: self._on_delete(self._data))
        # menu.addAction(act_view)
        menu.addAction(act_edit)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))


# ── Bảng Kho / Đơn Vị ────────────────────────────────────────────────────────
class KhoTable(QTableWidget):
    COLS = ["STT", "Tên Kho", "Mã Kho", "Loại", "Địa Chỉ", "Ghi Chú"]

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
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 56)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 100)

    def load(self, warehouses: list[Warehouse]):
        self.setRowCount(0)
        for i, wh in enumerate(warehouses):
            r = self.rowCount()
            self.insertRow(r)
            self.setRowHeight(r, 52)
            cells = [str(i + 1), wh.name, wh.code,
                     _TYPE_LABEL.get(wh.type, wh.type), wh.address, wh.notes]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setFont(QFont(FONT, 12))
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, col, item)


# ── Bảng Hàng Hoá ─────────────────────────────────────────────────────────────
class HangHoaTable(QTableWidget):
    COLS = ["STT", "Tên Hàng", "Mã Hàng", "Đơn Vị Tính", "Niên Hạn (năm)", "Ghi Chú"]

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
        self.setColumnWidth(0, 56)
        self.setColumnWidth(2, 110)
        self.setColumnWidth(3, 120)
        self.setColumnWidth(4, 130)

    def load(self, items: list[ItemType]):
        self.setRowCount(0)
        for i, it in enumerate(items):
            r = self.rowCount()
            self.insertRow(r)
            self.setRowHeight(r, 52)
            months = it.total_lifespan_months
            years_str = f"{months // 12}" if months % 12 == 0 else f"{months / 12:.1f}"
            cells = [str(i + 1), it.name, it.code,
                     it.unit_of_measure, years_str, it.notes]
            for col, val in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 12))
                if col in (0, 4):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, col, cell)


# ── Trang Chủ ─────────────────────────────────────────────────────────────────
class TrangChuPage(QWidget):
    TABS = ["Kho", "Đơn Vị", "Hàng Hoá"]

    def __init__(self):
        super().__init__()
        self.setStyleSheet("TrangChuPage { background: #fafafa; }")
        self._active_type = "TONG"   # "TONG" | "DON_VI" | "HANG_HOA"
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
        sub.setStyleSheet("color: #999; margin-top: 4px;")
        root.addWidget(sub)

        root.addSpacing(28)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #eee;")
        root.addWidget(sep)
        root.addSpacing(28)

        # ── Stat cards ────────────────────────────────────────────────────────
        sec = QLabel("Thống kê nhanh")
        sec.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        sec.setStyleSheet("color: #555;")
        root.addWidget(sec)
        root.addSpacing(14)

        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(16)
        root.addLayout(self._cards_row)

        root.addSpacing(32)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #eee;")
        root.addWidget(sep2)
        root.addSpacing(22)

        # ── TopBar (tabs + search) ────────────────────────────────────────────
        self.topbar = TopBar(self.TABS, active_tab=0)
        self.topbar.tab_bar.tab_changed.connect(self._on_tab)
        self.topbar.search.textChanged.connect(self._on_search)
        root.addWidget(self.topbar)
        root.addSpacing(22)

        # ── Section title + add button ────────────────────────────────────────
        title_row = QHBoxLayout()
        self._section_title = QLabel("Danh Sách Kho")
        self._section_title.setFont(QFont(FONT, 15))
        self._section_title.setStyleSheet("color: #bbb;")
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
        root.addLayout(title_row)
        root.addSpacing(12)

        # ── Tables (toggle visibility by tab) ────────────────────────────────
        self.table = KhoTable()
        root.addWidget(self.table)

        self.item_table = HangHoaTable()
        self.item_table.setVisible(False)
        root.addWidget(self.item_table)

        self.refresh()

    # ── Data loading ──────────────────────────────────────────────────────────

    def refresh(self):
        # Stat cards
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        stats = get_stats()
        for icon, title, value, color in [
            ("🏠", "Kho Tổng",               stats["kho_tong"],   "#111"),
            ("📦", "Đơn Vị",                  stats["don_vi"],     "#111"),
            ("🔖", "Loại mặt hàng đang lưu", stats["item_types"], "#111"),
            ("⚠️", "H4 chờ thanh xử lý",     stats["h4_pending"], "#d32f2f"),
        ]:
            self._cards_row.addWidget(StatCard(icon, title, value, color))

        self._reload_cache()

    def _reload_cache(self):
        if self._active_type in ("TONG", "DON_VI"):
            self._cache = wh_get_all(wh_type=self._active_type)
        else:
            self._cache = item_get_all()
        self._apply_filter()

    def _apply_filter(self):
        query = self.topbar.search.text().strip().lower()
        if self._active_type in ("TONG", "DON_VI"):
            data = [w for w in self._cache
                    if not query
                    or query in w.name.lower()
                    or query in w.code.lower()
                    or query in (w.address or "").lower()]
            self.table.load(data)
            self.table.setVisible(True)
            self.item_table.setVisible(False)
        else:
            data = [i for i in self._cache
                    if not query
                    or query in i.name.lower()
                    or query in i.code.lower()
                    or query in i.unit_of_measure.lower()]
            self.item_table.load(data)
            self.item_table.setVisible(True)
            self.table.setVisible(False)

    def _on_search(self, _: str):
        self._apply_filter()

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _on_tab(self, idx: int):
        self.topbar.search.clear()
        if idx == 0:
            self._active_type = "TONG"
            self._section_title.setText("Danh Sách Kho")
            self._btn_add.setText("+ Thêm Kho")
        elif idx == 1:
            self._active_type = "DON_VI"
            self._section_title.setText("Danh Sách Đơn Vị")
            self._btn_add.setText("+ Thêm Đơn Vị")
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
