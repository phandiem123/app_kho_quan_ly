from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

FONT = "Segoe UI"


class TabBar(QWidget):
    tab_changed = pyqtSignal(int)

    def __init__(self, tabs: list[str], active: int = 0):
        super().__init__()
        self.setFixedHeight(36)
        self.setStyleSheet("background: #f0f0f0; border-radius: 9px;")

        h = QHBoxLayout(self)
        h.setContentsMargins(3, 3, 3, 3)
        h.setSpacing(2)

        self._buttons: list[QPushButton] = []

        for i, text in enumerate(tabs):
            btn = QPushButton(text)
            btn.setFont(QFont(FONT, 12))
            btn.setFixedHeight(30)
            btn.setCheckable(True)
            btn.setChecked(i == active)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._apply_style(btn, i == active)
            h.addWidget(btn)
            self._buttons.append(btn)

            idx = i
            btn.clicked.connect(lambda _, i=idx: self._select(i))

    def _apply_style(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    border: none; border-radius: 7px; padding: 0 18px;
                    font-size: 13px; font-weight: 600;
                    background: #111; color: white;
                }
                QPushButton:hover { background: #222; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    border: none; border-radius: 7px; padding: 0 18px;
                    font-size: 13px; font-weight: normal;
                    background: transparent; color: #666;
                }
                QPushButton:hover { background: #e3e3e3; color: #111; }
            """)

    def _select(self, index: int):
        for i, btn in enumerate(self._buttons):
            self._apply_style(btn, i == index)
        self.tab_changed.emit(index)


class TopBar(QWidget):
    def __init__(self, tabs: list[str], active_tab: int = 0):
        super().__init__()
        self.setFixedHeight(56)
        self.setStyleSheet(
            "background: white; border-bottom: 1px solid #f0f0f0;"
        )

        h = QHBoxLayout(self)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(12)

        self.tab_bar = TabBar(tabs, active_tab)
        h.addWidget(self.tab_bar)
        h.addStretch()

        # Search
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm kiếm")
        self.search.setFixedSize(380, 34)
        self.search.setFont(QFont(FONT, 12))
        self.search.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 0 12px 0 32px;
                background: #fafafa;
                color: #333;
            }
            QLineEdit:focus {
                border-color: #bbb;
                background: white;
            }
        """)
        h.addWidget(self.search)

        # # Bell
        # bell = QPushButton("🔔")
        # bell.setFlat(True)
        # bell.setFixedSize(36, 36)
        # bell.setFont(QFont(FONT, 15))
        # bell.setStyleSheet("background: transparent; border: none;")
        # bell.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # h.addWidget(bell)
