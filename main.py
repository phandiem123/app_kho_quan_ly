#!/usr/bin/env python3
"""DCCD - Hệ thống Quản lý Kho, Đơn vị & Niên hạn Hàng hóa"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QFrame, QStackedWidget,
)
from PyQt6.QtGui import QFont
from ui.sidebar import Sidebar
from ui.pages.danh_sach_kho import DanhSachKhoPage

FONT = "Segoe UI"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DCCD")
        self.resize(1280, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background: white;")

        central = QWidget()
        self.setCentralWidget(central)

        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav)
        h.addWidget(self.sidebar)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #efefef; border: none;")
        h.addWidget(sep)

        # Page stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: white;")
        h.addWidget(self.stack)

        # Register pages
        self._pages: dict[str, int] = {}
        self._add_page("kho", DanhSachKhoPage())
        self.stack.setCurrentIndex(0)

    def _add_page(self, key: str, widget: QWidget):
        idx = self.stack.addWidget(widget)
        self._pages[key] = idx

    def _on_nav(self, key: str):
        if key in self._pages:
            self.stack.setCurrentIndex(self._pages[key])


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont(FONT, 12))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
