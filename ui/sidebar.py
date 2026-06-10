from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

FONT = "Segoe UI"
SIDEBAR_W = 264


class NavItem(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, icon: str, text: str, key: str = "", active: bool = False):
        super().__init__()
        self._active = active
        self._key = key
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(10)

        if icon:
            ico = QLabel(icon)
            ico.setFixedWidth(22)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setFont(QFont(FONT, 13))
            row.addWidget(ico)

        lbl = QLabel(text)
        lbl.setFont(QFont(FONT, 12))
        lbl.setWordWrap(True)
        row.addWidget(lbl, 1)

        self._refresh()

    def _refresh(self):
        if self._active:
            self.setStyleSheet("""
                NavItem { background: #111; border-radius: 8px; }
                NavItem QLabel { color: white; }
            """)
        else:
            self.setStyleSheet("""
                NavItem { background: transparent; border-radius: 8px; }
                NavItem QLabel { color: #1a1a1a; }
            """)

    def set_active(self, v: bool):
        self._active = v
        self._refresh()

    def mousePressEvent(self, e):
        self.clicked.emit(self._key)

    def enterEvent(self, e):
        if not self._active:
            self.setStyleSheet("""
                NavItem { background: #f0f0f0; border-radius: 8px; }
                NavItem QLabel { color: #1a1a1a; }
            """)

    def leaveEvent(self, e):
        self._refresh()


class SectionHeader(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.setFont(QFont(FONT, 10, QFont.Weight.Bold))
        self.setStyleSheet("color: #999; padding: 14px 12px 4px 12px;")


class Sidebar(QWidget):
    nav_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(SIDEBAR_W)
        self.setStyleSheet("Sidebar { background: white; }")
        self._items: dict[str, NavItem] = {}
        self._active_key = "trang_chu"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Logo — always visible, not scrollable
        logo = QLabel("DCCD")
        logo.setFont(QFont(FONT, 30, QFont.Weight.Black))
        logo.setStyleSheet("color: #111; padding: 22px 12px 14px 12px; background: white;")
        outer.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #f0f0f0; border: none;")
        outer.addWidget(sep)

        # Scrollable nav area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                width: 4px; background: transparent;
                margin: 0; border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #ddd; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: white;")
        v = QVBoxLayout(nav_widget)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(1)

        self._add_item(v, "", "Trang Chủ", "trang_chu", active=True)

        v.addWidget(SectionHeader("Thống Kê Tồn Kho"))
        self._add_item(v, "⌂", "Kho", "kho")
        self._add_item(v, "◎", "Đơn Vị", "don_vi")

        v.addWidget(SectionHeader("Phiếu Kho"))
        self._add_item(v, "↙", "Nhập Kho", "nhap_kho")
        self._add_item(v, "↗", "Xuất Kho", "xuat_kho")
        self._add_item(v, "⇄", "Luân Chuyển", "luan_chuyen")

        v.addWidget(SectionHeader("Thanh Xử Lý"))
        self._add_item(v, "⌂", "Tại Kho", "txl_kho")
        self._add_item(v, "◎", "Tại Đơn Vị", "txl_don_vi")
        self._add_item(v, "◈", "Hàng Dùng Chung", "txl_chung")

        v.addStretch()
        scroll.setWidget(nav_widget)
        outer.addWidget(scroll, 1)

    def _add_item(self, layout: QVBoxLayout, icon: str, text: str, key: str, active: bool = False):
        item = NavItem(icon, text, key, active)
        item.clicked.connect(self._on_nav)
        layout.addWidget(item)
        self._items[key] = item

    def _on_nav(self, key: str):
        if self._active_key and self._active_key in self._items:
            self._items[self._active_key].set_active(False)
        self._active_key = key
        if key in self._items:
            self._items[key].set_active(True)
        self.nav_changed.emit(key)
