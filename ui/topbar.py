from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

FONT = "Segoe UI"


class TabBar(QWidget):
    tab_changed = pyqtSignal(int)

    def __init__(self, tabs: list[str], active: int = 0):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._buttons: list[QPushButton] = []
        n = len(tabs)

        for i, text in enumerate(tabs):
            btn = QPushButton(text)
            btn.setFont(QFont(FONT, 12))
            btn.setFixedHeight(32)
            btn.setCheckable(True)
            btn.setChecked(i == active)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

            if n == 1:
                radius = "border-radius: 6px;"
            elif i == 0:
                radius = "border-radius: 6px 0 0 6px;"
            elif i == n - 1:
                radius = "border-radius: 0 6px 6px 0; border-left: none;"
            else:
                radius = "border-radius: 0; border-left: none;"

            btn.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid #d0d0d0;
                    background: white;
                    padding: 0 18px;
                    color: #333;
                    {radius}
                }}
                QPushButton:checked {{
                    font-weight: 600;
                    color: #111;
                    background: white;
                }}
                QPushButton:hover:!checked {{
                    background: #f6f6f6;
                }}
            """)
            h.addWidget(btn)
            self._buttons.append(btn)

            idx = i
            btn.clicked.connect(lambda _checked, i=idx: self._select(i))

    def _select(self, index: int):
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
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

        # Bell
        bell.setFlat(True)
        bell.setFixedSize(36, 36)
        bell.setFont(QFont(FONT, 15))
        bell.setStyleSheet("background: transparent; border: none;")
        bell.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        h.addWidget(bell)
