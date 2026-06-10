from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor
from ui.topbar import TopBar

FONT = "Segoe UI"


class KhoTable(QTableWidget):
    COLUMNS = ["STT", "Tên Kho", "Mã Kho", "Địa Chỉ", "Ghi Chú", ""]

    def __init__(self):
        super().__init__(0, len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet("""
            QTableWidget {
                border: none;
                background: white;
                outline: 0;
            }
            QHeaderView::section {
                background: white;
                color: #aaa;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #efefef;
                padding: 8px 12px;
                font-weight: normal;
            }
            QTableWidget::item {
                padding: 0 12px;
                border-bottom: 1px solid #f5f5f5;
                color: #1a1a1a;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background: #f5f7fa;
                color: #1a1a1a;
            }
        """)

        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)       # STT
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)      # Tên Kho
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)        # Mã Kho
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)      # Địa Chỉ
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)      # Ghi Chú
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)        # actions
        self.setColumnWidth(0, 60)
        self.setColumnWidth(2, 110)
        self.setColumnWidth(5, 52)

    def add_row(self, stt: int, ten_kho: str, ma_kho: str, dia_chi: str, ghi_chu: str):
        r = self.rowCount()
        self.insertRow(r)
        self.setRowHeight(r, 52)

        for col, val in enumerate([str(stt), ten_kho, ma_kho, dia_chi, ghi_chu]):
            item = QTableWidgetItem(val)
            item.setFont(QFont(FONT, 12))
            if col == 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(r, col, item)

        dots = QPushButton("···")
        dots.setFlat(True)
        dots.setFont(QFont(FONT, 15))
        dots.setStyleSheet("color: #bbb; border: none; background: transparent; letter-spacing: 1px;")
        dots.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCellWidget(r, 5, dots)


class DanhSachKhoPage(QWidget):
    TABS = ["Kho", "Đơn Vị", "Hàng Hoá"]

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: white;")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Top bar with tabs
        self.topbar = TopBar(self.TABS, active_tab=0)
        v.addWidget(self.topbar)

        # Content
        body = QWidget()
        body.setStyleSheet("background: white;")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(28, 22, 28, 22)
        bv.setSpacing(14)

        title = QLabel("Danh Sách Kho")
        title.setFont(QFont(FONT, 15))
        title.setStyleSheet("color: #bbb;")
        bv.addWidget(title)

        self.table = KhoTable()
        bv.addWidget(self.table)

        v.addWidget(body)

        # Load sample data
        self._load_sample()

    def _load_sample(self):
        self.table.add_row(1, "Kho D6", "D6", "100 Nguyễn Phước Lan, ...", "Ghi chú")
