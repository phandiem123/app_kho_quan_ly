#!/usr/bin/env python3
"""DCCD - Hệ thống Quản lý Kho, Đơn vị & Niên hạn Hàng hóa"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QFrame, QStackedWidget,
)
from PyQt6.QtGui import QFont
import database
from ui.sidebar import Sidebar
from ui.pages.trang_chu import TrangChuPage
from ui.pages.danh_sach_kho import DanhSachKhoPage

FONT = "Segoe UI"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DCCD")
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)
        self.setStyleSheet("background: white;")

        central = QWidget()
        self.setCentralWidget(central)

        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── Sidebar cố định, không co giãn ───────────────────────────────────
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav)
        h.addWidget(self.sidebar)
        h.setStretchFactor(self.sidebar, 0)   # sidebar không stretch

        # Đường kẻ dọc phân cách
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #efefef; border: none;")
        h.addWidget(sep)

        # ── Vùng nội dung (stack các trang) ──────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: white;")
        h.addWidget(self.stack)
        h.setStretchFactor(self.stack, 1)     # content chiếm hết phần còn lại

        # Đăng ký trang
        self._pages: dict[str, int] = {}
        self._trang_chu = TrangChuPage()
        self._kho_page  = DanhSachKhoPage()

        self._add_page("trang_chu", self._trang_chu)
        self._add_page("kho",       self._kho_page)

        # Mặc định hiển thị Trang Chủ
        self.stack.setCurrentIndex(self._pages["trang_chu"])

    def _add_page(self, key: str, widget: QWidget):
        idx = self.stack.addWidget(widget)
        self._pages[key] = idx

    def _on_nav(self, key: str):
        if key not in self._pages:
            return
        # Refresh trang trước khi hiển thị
        page = self.stack.widget(self._pages[key])
        if hasattr(page, "refresh"):
            page.refresh()
        self.stack.setCurrentIndex(self._pages[key])


def main():
    # Khởi tạo DB ngay khi app start
    database.get_conn()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont(FONT, 12))

    window = MainWindow()
    window.show()

    ret = app.exec()
    database.close()
    sys.exit(ret)


if __name__ == "__main__":
    main()
