from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QTextEdit,
    QPushButton, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from database.item_types import ItemType, code_exists, insert, update

FONT = "Segoe UI"


class ItemTypeFormDialog(QDialog):
    def __init__(self, parent=None, item: ItemType | None = None):
        super().__init__(parent)
        self._editing = item
        title = "Sửa Hàng Hoá" if item else "Thêm Hàng Hoá"
        self.setWindowTitle(title)
        self.setFixedWidth(480)
        self.setModal(True)
        self.setStyleSheet("background: white;")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        hdr = QLabel(title)
        hdr.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #111; margin-bottom: 20px;")
        root.addWidget(hdr)

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
                    border: 1px solid #ddd; border-radius: 6px;
                    padding: 0 10px; background: white;
                }
                QLineEdit:focus { border-color: #888; }
            """)
            return e

        self.f_code = field("VD: AK47, PKN01")
        self.f_name = field("Tên đầy đủ của hàng hoá")
        self.f_unit = field("VD: cái, bộ, chiếc, hộp")

        self.f_lifespan = QSpinBox()
        self.f_lifespan.setRange(1, 50)
        self.f_lifespan.setValue(1)
        self.f_lifespan.setSuffix(" năm")
        self.f_lifespan.setFont(QFont(FONT, 12))
        self.f_lifespan.setFixedHeight(36)
        self.f_lifespan.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ddd; border-radius: 6px;
                padding: 0 10px; background: white;
            }
            QSpinBox:focus { border-color: #888; }
            QSpinBox::up-button, QSpinBox::down-button { width: 20px; }
        """)

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Ghi chú (tuỳ chọn)")
        self.f_notes.setFont(QFont(FONT, 12))
        self.f_notes.setFixedHeight(72)
        self.f_notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd; border-radius: 6px;
                padding: 6px 10px; background: white;
            }
            QTextEdit:focus { border-color: #888; }
        """)

        form.addRow(lbl("Mã Hàng *"), self.f_code)
        form.addRow(lbl("Tên Hàng *"), self.f_name)
        form.addRow(lbl("Đơn Vị Tính *"), self.f_unit)
        form.addRow(lbl("Niên Hạn (năm) *"), self.f_lifespan)
        form.addRow(lbl("Ghi Chú"), self.f_notes)
        root.addLayout(form)

        if item:
            self.f_code.setText(item.code)
            self.f_name.setText(item.name)
            self.f_unit.setText(item.unit_of_measure)
            self.f_lifespan.setValue(max(1, round(item.total_lifespan_months / 12)))
            self.f_notes.setPlainText(item.notes)

        root.addSpacing(24)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #eee;")
        root.addWidget(line)
        root.addSpacing(16)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Huỷ")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setFont(QFont(FONT, 12))
        btn_cancel.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd; border-radius: 6px;
                padding: 0 20px; background: white; color: #555;
            }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Lưu")
        btn_save.setFixedHeight(36)
        btn_save.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_save.setStyleSheet("""
            QPushButton {
                border: none; border-radius: 6px; padding: 0 24px;
                background: #111; color: white;
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
        unit = self.f_unit.text().strip()
        lifespan = self.f_lifespan.value() * 12  # convert years → months for storage
        notes = self.f_notes.toPlainText().strip()

        if not code:
            self._err("Vui lòng nhập Mã Hàng.")
            return
        if not name:
            self._err("Vui lòng nhập Tên Hàng.")
            return
        if not unit:
            self._err("Vui lòng nhập Đơn Vị Tính.")
            return

        exclude_id = self._editing.id if self._editing else None
        if code_exists(code, exclude_id):
            self._err(f"Mã Hàng '{code}' đã tồn tại.")
            return

        item = ItemType(
            id=self._editing.id if self._editing else None,
            code=code, name=name, unit_of_measure=unit,
            total_lifespan_months=lifespan, notes=notes,
        )
        if self._editing:
            update(item)
        else:
            insert(item)
        self.accept()

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)
