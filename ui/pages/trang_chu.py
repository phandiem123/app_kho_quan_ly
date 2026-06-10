from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QCursor, QAction
from ui.dialogs.warehouse_form import WarehouseFormDialog
from database.warehouses import Warehouse, get_all, get_stats, soft_delete
from ui.topbar import TopBar

FONT = "Segoe UI"
_TYPE_LABEL = {"TONG": "Kho Tổng", "DON_VI": "Đơn Vị"}

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


class DotsButton(QPushButton):
    def __init__(self, wh: Warehouse, on_view, on_edit, on_delete):
        super().__init__("···")
        self._wh = wh
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
        act_view = QAction("Xem Chi Tiết", self)
        act_view.triggered.connect(lambda: self._on_view(self._wh))
        act_edit = QAction("Sửa", self)
        act_edit.triggered.connect(lambda: self._on_edit(self._wh))
        act_del = QAction("Xóa", self)
        act_del.triggered.connect(lambda: self._on_delete(self._wh))
        menu.addAction(act_view)
        menu.addAction(act_edit)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))


class KhoTable(QTableWidget):
    COLS = ["STT", "Tên Kho", "Mã Kho", "Loại", "Địa Chỉ", "Ghi Chú", ""]

    def __init__(self, on_view, on_edit, on_delete):
        super().__init__(0, len(self.COLS))
        self._on_view = on_view
        self._on_edit = on_edit
        self._on_delete = on_delete

        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("""
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
        """)

        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 56)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(6, 52)

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
            dots = DotsButton(wh, self._on_view, self._on_edit, self._on_delete)
            self.setCellWidget(r, 6, dots)


class TrangChuPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: #fafafa;")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 32)
        root.setSpacing(0)

        # Header
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

        # Stat cards section
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

        self.TABS = ["Kho", "Đơn Vị", "Hàng Hoá"]
        self.topbar = TopBar(self.TABS, active_tab=0)

        # Danh sách kho section
        title_row = QHBoxLayout()
        kho_title = QLabel("Danh Sách Kho")
        kho_title.setFont(QFont(FONT, 15))
        kho_title.setStyleSheet("color: #bbb;")
        title_row.addWidget(kho_title)
        title_row.addStretch()

        btn_add = QPushButton("+ Thêm Kho")
        btn_add.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_add.setFixedHeight(36)
        btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add.setStyleSheet("""
            QPushButton {
                background: #111; color: white; border: none;
                border-radius: 8px; padding: 0 20px;
            }
            QPushButton:hover { background: #333; }
        """)
        btn_add.clicked.connect(self._add_warehouse)
        title_row.addWidget(btn_add)
        root.addLayout(title_row)

        root.addSpacing(12)

        self.table = KhoTable(
            on_view=self._view_warehouse,
            on_edit=self._edit_warehouse,
            on_delete=self._delete_warehouse,
        )
        root.addWidget(self.table)

        self.refresh()

    def refresh(self):
        # Reload stat cards
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

        # Reload warehouse table
        self.table.load(get_all())

    def _add_warehouse(self):
        dlg = WarehouseFormDialog(self)
        if dlg.exec():
            self.refresh()

    def _edit_warehouse(self, wh: Warehouse):
        dlg = WarehouseFormDialog(self, warehouse=wh)
        if dlg.exec():
            self.refresh()

    def _delete_warehouse(self, wh: Warehouse):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa kho <b>{wh.name}</b>?<br>"
            f"Kho sẽ bị ẩn nhưng dữ liệu lịch sử vẫn được giữ lại.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            soft_delete(wh.id)
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
