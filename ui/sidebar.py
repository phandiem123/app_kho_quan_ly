from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
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

        from PyQt6.QtWidgets import QHBoxLayout
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(10)

        if icon:
            ico = QLabel(icon)
            ico.setFixedWidth(22)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setFont(QFont(FONT, 13))
            ico.setStyleSheet("color: #444;")
            row.addWidget(ico)

        lbl = QLabel(text)
        lbl.setFont(QFont(FONT, 12))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #1a1a1a;")
        row.addWidget(lbl, 1)

        self._refresh()

    def _refresh(self):
        bg = "#efefef" if self._active else "transparent"
        self.setStyleSheet(f"NavItem {{ background: {bg}; border-radius: 8px; }}")

    def set_active(self, v: bool):
        self._active = v
        self._refresh()

    def mousePressEvent(self, e):
        self.clicked.emit(self._key)

    def enterEvent(self, e):
        if not self._active:
            self.setStyleSheet("NavItem { background: #f7f7f7; border-radius: 8px; }")

    def leaveEvent(self, e):
        self._refresh()


class SectionHeader(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.setFont(QFont(FONT, 10, QFont.Weight.Bold))
        self.setStyleSheet("color: #111; padding: 14px 12px 4px 12px;")


class Sidebar(QWidget):
    nav_changed = pyqtSignal(str)

    _NAV_ITEMS: list[tuple[str, str, str]] = [
        # (icon, label, key)
        ("", "Trang Chủ", "trang_chu"),
    ]

    def __init__(self):
        super().__init__()
        self.setFixedWidth(SIDEBAR_W)
        self.setStyleSheet("background: white;")
        self._items: dict[str, NavItem] = {}
        self._active_key = "trang_chu"

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 0, 8, 8)
        v.setSpacing(1)

        # Logo
        logo = QLabel("DCCD")
        logo.setFont(QFont(FONT, 30, QFont.Weight.Black))
        logo.setStyleSheet("color: #111; padding: 22px 12px 14px 12px;")
        v.addWidget(logo)

        # Trang Chủ
        self._add_item(v, "", "Trang Chủ", "trang_chu", active=True)

        # ── Thống Kê Tồn Kho ──
        v.addWidget(SectionHeader("Thống Kê Tồn Kho"))
        self._add_item(v, "⌂", "Kho", "kho")
        self._add_item(v, "◎", "Đơn Vị", "don_vi")

        # ── Phiếu Kho ──
        v.addWidget(SectionHeader("Phiếu Kho"))
        self._add_item(v, "↙", "Phiếu Nhập Kho", "nhap_kho")
        self._add_item(v, "↗", "Phiếu Xuất Kho", "xuat_kho")
        self._add_item(v, "⇄", "Phiếu Luân Chuyển Đơn Vị", "luan_chuyen")

        # ── Thanh Xử Lý ──
        v.addWidget(SectionHeader("Thanh Xử Lý"))
        self._add_item(v, "⌂", "Thanh Xử Lý Tại Kho", "txl_kho")
        self._add_item(v, "◎", "Thanh Xử Lý Tại Đơn Vị", "txl_don_vi")
        self._add_item(v, "◈", "Thanh Xử Lý Hàng Dùng Chung", "txl_chung")

        v.addStretch()

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
