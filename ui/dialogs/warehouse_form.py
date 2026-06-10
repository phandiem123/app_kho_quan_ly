from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QTextEdit,
    QPushButton, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from database.warehouses import Warehouse, code_exists, insert, update

FONT = "Segoe UI"

_TYPE_LABELS = {"TONG": "Kho Tổng", "DON_VI": "Đơn Vị"}
_LABEL_TYPES = {v: k for k, v in _TYPE_LABELS.items()}


class WarehouseFormDialog(QDialog):
    """Dialog Thêm hoặc Sửa kho/đơn vị."""

    def __init__(self, parent=None, warehouse: Warehouse | None = None,
                 default_type: str | None = None):
        super().__init__(parent)
        self._editing = warehouse
        title = "Sửa Kho" if warehouse else "Thêm Kho"
        self.setWindowTitle(title)
        self.setFixedWidth(480)
        self.setModal(True)
        self.setStyleSheet("background: white;")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        # Header
        hdr = QLabel(title)
        hdr.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #111; margin-bottom: 20px;")
        root.addWidget(hdr)

        # Form
        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def lbl(text):
            l = QLabel(text)
            l.setFont(QFont(FONT, 12))
            l.setStyleSheet("color: #555;")
            return l

        def field(placeholder=""):
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            e.setFont(QFont(FONT, 12))
            e.setFixedHeight(36)
            e.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    padding: 0 10px;
                    background: white;
                }
                QLineEdit:focus { border-color: #888; }
            """)
            return e

        self.f_code = field("VD: D6, KT01")
        self.f_name = field("Tên đầy đủ của kho")

        self.f_type = QComboBox()
        self.f_type.addItems(list(_TYPE_LABELS.values()))
        self.f_type.setFont(QFont(FONT, 12))
        self.f_type.setFixedHeight(36)
        self.f_type.setStyleSheet("""
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 0 10px;
                background: white;
            }
            QComboBox:focus { border-color: #888; }
            QComboBox::drop-down { border: none; }
        """)

        self.f_address = field("Địa chỉ")

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Ghi chú (tuỳ chọn)")
        self.f_notes.setFont(QFont(FONT, 12))
        self.f_notes.setFixedHeight(72)
        self.f_notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 6px 10px;
                background: white;
            }
            QTextEdit:focus { border-color: #888; }
        """)

        form.addRow(lbl("Mã Kho *"), self.f_code)
        form.addRow(lbl("Tên Kho *"), self.f_name)
        form.addRow(lbl("Địa Chỉ"), self.f_address)
        form.addRow(lbl("Ghi Chú"), self.f_notes)
        root.addLayout(form)

        # Pre-select type when adding from a specific tab
        if not warehouse and default_type and default_type in _TYPE_LABELS:
            self.f_type.setCurrentText(_TYPE_LABELS[default_type])

        # Fill existing data when editing
        if warehouse:
            self.f_code.setText(warehouse.code)
            self.f_name.setText(warehouse.name)
            self.f_address.setText(warehouse.address)
            self.f_notes.setPlainText(warehouse.notes)

        root.addSpacing(24)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #eee;")
        root.addWidget(line)
        root.addSpacing(16)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Huỷ")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setFont(QFont(FONT, 12))
        btn_cancel.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 0 20px;
                background: white;
                color: #555;
            }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Lưu")
        btn_save.setFixedHeight(36)
        btn_save.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_save.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 0 24px;
                background: #111;
                color: white;
            }
            QPushButton:hover { background: #333; }
        """)
        btn_save.clicked.connect(self._save)

        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(8)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _save(self):
        code = self.f_code.text().strip()
        name = self.f_name.text().strip()
        wh_type = _LABEL_TYPES[self.f_type.currentText()]
        address = self.f_address.text().strip()
        notes = self.f_notes.toPlainText().strip()

        if not code:
            self._err("Vui lòng nhập Mã Kho.")
            return
        if not name:
            self._err("Vui lòng nhập Tên Kho.")
            return

        exclude_id = self._editing.id if self._editing else None
        if code_exists(code, exclude_id):
            self._err(f"Mã Kho '{code}' đã tồn tại.")
            return

        wh = Warehouse(
            id=self._editing.id if self._editing else None,
            code=code, name=name, type=wh_type,
            address=address, notes=notes,
        )
        if self._editing:
            update(wh)
        else:
            insert(wh)

        self.accept()

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)
