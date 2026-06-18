#!/usr/bin/env python3
"""DCCD - Hệ thống Quản lý Kho, Đơn vị & Niên hạn Hàng hóa"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QFrame, QStackedWidget, QScrollArea,
    QProxyStyle, QStyle,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import database
from ui.sidebar import Sidebar
from ui.pages.trang_chu import TrangChuPage

FONT = "Segoe UI"


class _FastTipStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 200
        return super().styleHint(hint, option, widget, returnData)


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
        self._add_page("trang_chu", TrangChuPage())

        # Mặc định hiển thị Trang Chủ
        self.stack.setCurrentIndex(self._pages["trang_chu"])

    def _add_page(self, key: str, widget: QWidget):
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        idx = self.stack.addWidget(scroll)
        self._pages[key] = idx

    # Factory dict: key → callable trả về QWidget, import xảy ra lúc gọi
    _LAZY: "dict[str, Callable[[], QWidget]]" = {}

    def _on_nav(self, key: str):
        if key not in self._pages:
            factory = self._LAZY.get(key)
            if factory is None:
                return
            self._add_page(key, factory())
        scroll = self.stack.widget(self._pages[key])
        # _add_page wraps every page in a QScrollArea — get the actual inner widget
        page = scroll.widget() if hasattr(scroll, "widget") else scroll
        if hasattr(page, "refresh"):
            page.refresh()
        self.stack.setCurrentIndex(self._pages[key])


def _register_lazy_pages():
    from ui.pages.nhap_kho import NhapKhoPage
    from ui.pages.xuat_kho import XuatKhoPage
    from ui.pages.luan_chuyen import LuanChuyenPage
    from ui.pages.export_import import ExportImportPage
    from ui.pages.txl import TxlKhoPage, TxlDonViPage
    from ui.pages.thong_ke import ThongKeKhoPage, ThongKeDonViPage, ThongKeSharedPage
    MainWindow._LAZY["kho"] = ThongKeKhoPage
    MainWindow._LAZY["don_vi"] = ThongKeDonViPage
    MainWindow._LAZY["txl_chung"] = ThongKeSharedPage
    MainWindow._LAZY["nhap_kho"] = NhapKhoPage
    MainWindow._LAZY["xuat_kho"] = XuatKhoPage
    MainWindow._LAZY["luan_chuyen"] = LuanChuyenPage
    MainWindow._LAZY["export_import"] = ExportImportPage
    MainWindow._LAZY["txl_kho"] = TxlKhoPage
    MainWindow._LAZY["txl_don_vi"] = TxlDonViPage
    from ui.pages.bieu_do import BieuDoPage
    MainWindow._LAZY["bieu_do"] = BieuDoPage


_register_lazy_pages()


def main():
    # Khởi tạo DB ngay khi app start
    database.get_conn()

    app = QApplication(sys.argv)
    app.setStyle(_FastTipStyle("Fusion"))
    app.setFont(QFont(FONT, 12))
    app.setStyleSheet("""
        QToolTip {
            background: white;
            color: #111;
            border: 1px solid #ddd;
            border-radius: 12px;
            padding: 14px 18px;
            font-family: "Segoe UI";
            font-size: 13px;
        }
    """)

    window = MainWindow()
    window.show()

    ret = app.exec()
    database.close()
    sys.exit(ret)


if __name__ == "__main__":
    main()
