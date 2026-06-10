from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QCursor, QAction
from ui.topbar import TopBar
from ui.dialogs.warehouse_form import WarehouseFormDialog
from database.warehouses import Warehouse, get_all, soft_delete

FONT = "Segoe UI"
_TYPE_LABEL = {"TONG": "Kho Tổng", "DON_VI": "Đơn Vị"}


# ── Nút "···" với dropdown xuất hiện khi hover ────────────────────────────────
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
                color: #bbb;
                border: none;
                background: transparent;
                letter-spacing: 2px;
                border-radius: 6px;
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
                background: white;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                font-size: 13px;
                border-radius: 6px;
                color: #1a1a1a;
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

        pos = self.mapToGlobal(QPoint(0, self.height()))
        menu.exec(pos)


# ── Bảng danh sách kho ────────────────────────────────────────────────────────
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
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)   # STT
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Tên Kho
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)   # Mã Kho
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)   # Loại
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Địa Chỉ
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Ghi Chú
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)   # actions
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

            cells = [
                str(i + 1),
                wh.name,
                wh.code,
                _TYPE_LABEL.get(wh.type, wh.type),
                wh.address,
                wh.notes,
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setFont(QFont(FONT, 12))
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, col, item)

            dots = DotsButton(wh, self._on_view, self._on_edit, self._on_delete)
            self.setCellWidget(r, 6, dots)


# ── Trang Danh Sách Kho ───────────────────────────────────────────────────────
class DanhSachKhoPage(QWidget):
    TABS = ["Kho", "Đơn Vị", "Hàng Hoá"]

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: white;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = TopBar(self.TABS, active_tab=0)
        root.addWidget(self.topbar)

        # Body
        body = QWidget()
        body.setStyleSheet("background: white;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(28, 22, 28, 22)
        bv.setSpacing(16)

        # Title row: "Danh Sách Kho" + nút Thêm Kho
        title_row = QHBoxLayout()

        title = QLabel("Danh Sách Kho")
        title.setFont(QFont(FONT, 15))
        title.setStyleSheet("color: #bbb;")
        title_row.addWidget(title)
        title_row.addStretch()

        btn_add = QPushButton("+ Thêm Kho")
        btn_add.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_add.setFixedHeight(36)
        btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add.setStyleSheet("""
            QPushButton {
                background: #111;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:hover { background: #333; }
        """)
        btn_add.clicked.connect(self._add_warehouse)
        title_row.addWidget(btn_add)

        bv.addLayout(title_row)

        self.table = KhoTable(
            on_view=self._view_warehouse,
            on_edit=self._edit_warehouse,
            on_delete=self._delete_warehouse,
        )
        bv.addWidget(self.table)
        root.addWidget(body)

        self.refresh()

    # ── Actions ───────────────────────────────────────────────────────────────
    def refresh(self):
        warehouses = get_all()
        self.table.load(warehouses)

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
