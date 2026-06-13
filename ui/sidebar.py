import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QScrollArea, QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QCursor, QPixmap, QPainter, QPainterPath, QColor

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
                NavItem { background: #ebebeb; border-radius: 8px; }
                NavItem QLabel { color: #111; }
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


def _make_round_pixmap(path: str, size: int) -> QPixmap | None:
    if not os.path.exists(path):
        return None
    src = QPixmap(path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, src)
    p.end()
    return out


class _AvatarPopup(QWidget):
    """Floating popup shown on hover — large photo + name."""

    def __init__(self, img_path: str, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

        # Card container
        card = QWidget(self)
        card.setObjectName("card")
        card.setStyleSheet("""
            QWidget#card {
                background: white;
                border-radius: 14px;
                border: 1px solid #e8e8e8;
            }
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        card.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(card)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(16, 16, 16, 14)
        inner.setSpacing(10)
        inner.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Large round photo
        img_lbl = QLabel()
        img_lbl.setFixedSize(160, 160)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = _make_round_pixmap(img_path, 160)
        if pm:
            img_lbl.setPixmap(pm)
        else:
            img_lbl.setText("NHR")
            img_lbl.setStyleSheet(
                "background:#ddd; border-radius:80px; color:#555; font-size:18px;"
            )
        inner.addWidget(img_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        name_lbl = QLabel("Nguyễn Hữu Ry")
        name_lbl.setFont(QFont(FONT, 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #111; background: transparent;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        inner.addWidget(name_lbl)

        pw_lbl = QLabel("Powered by")
        pw_lbl.setFont(QFont(FONT, 10))
        pw_lbl.setStyleSheet("color: #aaa; background: transparent;")
        pw_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        inner.addWidget(pw_lbl)

        self.adjustSize()


class _PoweredByFooter(QWidget):
    """Footer bar that shows hover popup with large avatar."""

    def __init__(self, img_path: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: white;")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._img_path = img_path
        self._popup: _AvatarPopup | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 12)
        row.setSpacing(10)

        avatar_lbl = QLabel()
        avatar_lbl.setFixedSize(40, 40)
        pm = _make_round_pixmap(img_path, 40)
        if pm:
            avatar_lbl.setPixmap(pm)
        else:
            avatar_lbl.setText("NR")
            avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar_lbl.setStyleSheet(
                "background:#e0e0e0; border-radius:20px; color:#555; font-size:11px;"
            )
        row.addWidget(avatar_lbl)

        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        pw_lbl = QLabel("Powered by")
        pw_lbl.setFont(QFont(FONT, 9))
        pw_lbl.setStyleSheet("color: #999;")
        name_lbl = QLabel("Nguyễn Hữu Ry")
        name_lbl.setFont(QFont(FONT, 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #333;")
        txt_col.addWidget(pw_lbl)
        txt_col.addWidget(name_lbl)
        row.addLayout(txt_col, 1)

    def enterEvent(self, e):
        if self._popup is None:
            self._popup = _AvatarPopup(self._img_path)
        # Position popup above-left of footer, aligned to sidebar
        global_pos = self.mapToGlobal(QPoint(0, 0))
        pw = self._popup.sizeHint().width()
        ph = self._popup.sizeHint().height()
        self._popup.move(global_pos.x(), global_pos.y() - ph - 4)
        self._popup.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._popup:
            self._popup.hide()
        super().leaveEvent(e)


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
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: white;")
        v = QVBoxLayout(nav_widget)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(1)

        self._add_item(v, "", "Trang Chủ", "trang_chu", active=True)

        v.addWidget(SectionHeader("Biểu Đồ"))
        self._add_item(v, "◉", "Thống Kê Biểu Đồ", "bieu_do")

        v.addWidget(SectionHeader("Thống Kê Tồn Kho"))
        self._add_item(v, "⌂", "Kho", "kho")
        self._add_item(v, "◎", "Đơn Vị", "don_vi")
        self._add_item(v, "◈", "Hàng Dùng Chung", "txl_chung")

        v.addWidget(SectionHeader("Phiếu Kho"))
        self._add_item(v, "↙", "Nhập Kho", "nhap_kho")
        self._add_item(v, "↗", "Xuất Kho", "xuat_kho")
        self._add_item(v, "⇄", "Luân Chuyển", "luan_chuyen")

        v.addWidget(SectionHeader("Thanh Xử Lý"))
        self._add_item(v, "⌂", "Tại Kho", "txl_kho")
        self._add_item(v, "◎", "Tại Đơn Vị", "txl_don_vi")

        v.addWidget(SectionHeader("Dữ Liệu"))
        self._add_item(v, "⇅", "Nhập Dữ liệu/Xuất dữ liệu", "export_import")

        v.addStretch()
        scroll.setWidget(nav_widget)
        outer.addWidget(scroll, 1)

        # Footer — Powered by
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #f0f0f0; border: none;")
        outer.addWidget(sep2)

        _assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        _img_path = os.path.join(_assets, "avatar_nhr.jpg")
        outer.addWidget(_PoweredByFooter(_img_path))

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
