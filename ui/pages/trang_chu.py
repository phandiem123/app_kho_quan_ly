from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from database.warehouses import get_stats

FONT = "Segoe UI"


class StatCard(QWidget):
    def __init__(self, icon: str, title: str, value: str, color: str = "#111"):
        super().__init__()
        self.setStyleSheet(f"""
            StatCard {{
                background: white;
                border: 1px solid #efefef;
                border-radius: 12px;
            }}
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

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #eee;")
        root.addWidget(sep)

        root.addSpacing(28)

        # Section label
        sec = QLabel("Thống kê nhanh")
        sec.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        sec.setStyleSheet("color: #555;")
        root.addWidget(sec)

        root.addSpacing(14)

        # Stat cards
        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(16)
        root.addLayout(self._cards_row)

        root.addStretch()

        self.refresh()

    def refresh(self):
        # Clear old cards
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = get_stats()
        cards = [
            ("🏠", "Kho Tổng",               stats["kho_tong"],   "#111"),
            ("📦", "Đơn Vị",                  stats["don_vi"],     "#111"),
            ("🔖", "Loại mặt hàng đang lưu", stats["item_types"], "#111"),
            ("⚠️", "H4 chờ thanh xử lý",     stats["h4_pending"], "#d32f2f"),
        ]
        for icon, title, value, color in cards:
            self._cards_row.addWidget(StatCard(icon, title, value, color))
