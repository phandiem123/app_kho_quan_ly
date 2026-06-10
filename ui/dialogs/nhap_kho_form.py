from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit,
    QPushButton, QComboBox, QMessageBox, QFrame, QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from database.item_types import get_all as item_get_all
from database.warehouses import get_all as wh_get_all
from database.receipts import (
    Receipt, ReceiptLine, insert, update, ref_exists, get_lines,
)

FONT = "Segoe UI"

_FIELD_STYLE = """
    QLineEdit, QComboBox, QTextEdit, QDateEdit {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 10px; background: white; font-size: 12px;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border-color: #888; }
    QComboBox::drop-down { border: none; width: 24px; }
"""

_SPIN_STYLE = """
    QSpinBox, QDoubleSpinBox {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 8px; background: white; font-size: 12px;
    }
    QSpinBox:focus, QDoubleSpinBox:focus { border-color: #888; }
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 18px; }
"""


class LineItemRow(QWidget):
    removed = pyqtSignal(object)

    def __init__(self, item_types, parent=None):
        super().__init__(parent)
        self._item_types = item_types
        self.setStyleSheet("background: transparent;")

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(6)

        self.combo = QComboBox()
        self.combo.setFixedHeight(34)
        self.combo.setMinimumWidth(190)
        self.combo.setStyleSheet(_FIELD_STYLE)
        for it in item_types:
            self.combo.addItem(f"{it.code} – {it.name}", it)

        self.lbl_unit = QLabel("—")
        self.lbl_unit.setFixedWidth(56)
        self.lbl_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_unit.setFont(QFont(FONT, 11))
        self.lbl_unit.setStyleSheet(
            "color: #555; background: #f5f5f5; border-radius: 5px; padding: 2px 4px;"
        )

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 9_999_999)
        self.spin_qty.setValue(1)
        self.spin_qty.setFixedWidth(80)
        self.spin_qty.setFixedHeight(34)
        self.spin_qty.setStyleSheet(_SPIN_STYLE)

        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0, 999_999_999_999)
        self.spin_price.setDecimals(0)
        self.spin_price.setFixedWidth(120)
        self.spin_price.setFixedHeight(34)
        self.spin_price.setStyleSheet(_SPIN_STYLE)

        self.lbl_total = QLabel("—")
        self.lbl_total.setFixedWidth(120)
        self.lbl_total.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.lbl_total.setFont(QFont(FONT, 11, QFont.Weight.Medium))
        self.lbl_total.setStyleSheet("color: #333; background: transparent;")

        self.edit_notes = QLineEdit()
        self.edit_notes.setPlaceholderText("Ghi chú")
        self.edit_notes.setFixedHeight(34)
        self.edit_notes.setStyleSheet(_FIELD_STYLE)

        btn_del = QPushButton("×")
        btn_del.setFixedSize(32, 32)
        btn_del.setFont(QFont(FONT, 16))
        btn_del.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_del.setStyleSheet("""
            QPushButton { border: none; border-radius: 6px;
                background: #fff0f0; color: #c00; }
            QPushButton:hover { background: #ffd0d0; }
        """)
        btn_del.clicked.connect(lambda: self.removed.emit(self))

        h.addWidget(self.combo, 2)
        h.addWidget(self.lbl_unit)
        h.addWidget(self.spin_qty)
        h.addWidget(self.spin_price)
        h.addWidget(self.lbl_total)
        h.addWidget(self.edit_notes, 1)
        h.addWidget(btn_del)

        self.combo.currentIndexChanged.connect(self._on_item_changed)
        self.spin_qty.valueChanged.connect(self._recalc)
        self.spin_price.valueChanged.connect(self._recalc)

        if item_types:
            self._on_item_changed(0)

    def _on_item_changed(self, _):
        it = self.combo.currentData()
        self.lbl_unit.setText(it.unit_of_measure if it else "—")
        self._recalc()

    def _recalc(self):
        total = self.spin_qty.value() * self.spin_price.value()
        self.lbl_total.setText(f"{total:,.0f} đ" if total else "—")

    def get_data(self):
        it = self.combo.currentData()
        if not it:
            return None
        return ReceiptLine(
            item_type_id=it.id,
            item_code=it.code,
            item_name=it.name,
            unit_of_measure=it.unit_of_measure,
            quantity=self.spin_qty.value(),
            unit_price=self.spin_price.value(),
            notes=self.edit_notes.text().strip(),
        )

    def fill(self, line: ReceiptLine):
        for i in range(self.combo.count()):
            it = self.combo.itemData(i)
            if it and it.id == line.item_type_id:
                self.combo.setCurrentIndex(i)
                break
        self.spin_qty.setValue(line.quantity)
        self.spin_price.setValue(line.unit_price)
        self.edit_notes.setText(line.notes)


class NhapKhoFormDialog(QDialog):
    def __init__(self, parent=None, receipt: Receipt | None = None):
        super().__init__(parent)
        self._editing = receipt
        self._item_types = item_get_all()
        self._warehouses = [w for w in wh_get_all() if w.type == "TONG"]

        title = "Sửa Phiếu Nhập" if receipt else "Tạo Phiếu Nhập Kho"
        self.setWindowTitle(title)
        self.setMinimumWidth(820)
        self.setModal(True)
        self.setStyleSheet("background: white;")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        hdr = QLabel(title)
        hdr.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #111; margin-bottom: 20px;")
        root.addWidget(hdr)

        # ── Header fields ──────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            l = QLabel(t)
            l.setFont(QFont(FONT, 12))
            l.setStyleSheet("color: #555;")
            return l

        def field(ph=""):
            e = QLineEdit()
            e.setPlaceholderText(ph)
            e.setFont(QFont(FONT, 12))
            e.setFixedHeight(36)
            e.setStyleSheet(_FIELD_STYLE)
            return e

        self.f_ref = field("VD: NK-2025-001")
        self.f_ref.setMaximumWidth(280)

        self.f_wh = QComboBox()
        self.f_wh.setFont(QFont(FONT, 12))
        self.f_wh.setFixedHeight(36)
        self.f_wh.setMaximumWidth(280)
        self.f_wh.setStyleSheet(_FIELD_STYLE)
        self.f_wh.addItem("— Chọn Kho —", None)
        for w in self._warehouses:
            self.f_wh.addItem(f"{w.code} – {w.name}", w.id)

        self.f_supplier = field("Đơn vị / công ty cung cấp")
        self.f_person = field("Tên người giao hàng")

        from PyQt6.QtWidgets import QDateEdit
        self.f_date = QDateEdit(QDate.currentDate())
        self.f_date.setDisplayFormat("dd/MM/yyyy")
        self.f_date.setCalendarPopup(True)
        self.f_date.setFixedHeight(36)
        self.f_date.setMaximumWidth(180)
        self.f_date.setFont(QFont(FONT, 12))
        self.f_date.setStyleSheet(_FIELD_STYLE)

        self.f_transport = field("Đơn vị / phương tiện vận chuyển")

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Nội dung nhập kho (tuỳ chọn)")
        self.f_notes.setFont(QFont(FONT, 12))
        self.f_notes.setFixedHeight(60)
        self.f_notes.setStyleSheet(_FIELD_STYLE)

        row1 = QHBoxLayout()
        row1.setSpacing(24)
        r1_a = QFormLayout(); r1_a.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        r1_a.addRow(lbl("Số Phiếu *"), self.f_ref)
        r1_a.addRow(lbl("Kho Nhập *"), self.f_wh)
        r1_b = QFormLayout(); r1_b.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        r1_b.addRow(lbl("Đơn Vị Giao"), self.f_supplier)
        r1_b.addRow(lbl("Người Giao"), self.f_person)
        r1_c = QFormLayout(); r1_c.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        r1_c.addRow(lbl("Ngày Nhập *"), self.f_date)
        r1_c.addRow(lbl("Vận Chuyển"), self.f_transport)
        row1.addLayout(r1_a, 1)
        row1.addLayout(r1_b, 1)
        row1.addLayout(r1_c, 1)
        root.addLayout(row1)
        root.addSpacing(8)

        notes_row = QFormLayout()
        notes_row.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        notes_row.addRow(lbl("Nội dung"), self.f_notes)
        root.addLayout(notes_row)
        root.addSpacing(20)

        # ── Line items ─────────────────────────────────────────────────────────
        sec_lbl = QLabel("Danh Sách Hàng Nhập")
        sec_lbl.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        sec_lbl.setStyleSheet("color: #333;")
        root.addWidget(sec_lbl)
        root.addSpacing(6)

        # Column header
        col_hdr = QWidget()
        col_hdr.setStyleSheet("background: #f8f8f8; border-radius: 6px;")
        ch = QHBoxLayout(col_hdr)
        ch.setContentsMargins(6, 6, 6, 6)
        ch.setSpacing(6)
        for txt, stretch, w in [
            ("Mặt Hàng", 2, None), ("ĐVT", 0, 56), ("Số lượng", 0, 80),
            ("Đơn Giá", 0, 120), ("Thành Tiền", 0, 120), ("Ghi chú", 1, None), ("", 0, 32),
        ]:
            l = QLabel(txt)
            l.setFont(QFont(FONT, 10))
            l.setStyleSheet("color: #999;")
            if w:
                l.setFixedWidth(w)
                ch.addWidget(l)
            else:
                ch.addWidget(l, stretch)
        root.addWidget(col_hdr)

        # Scrollable rows
        self._rows_container = QWidget()
        self._rows_container.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._rows_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setMaximumHeight(260)
        scroll.setMinimumHeight(80)
        root.addWidget(scroll)

        btn_add_line = QPushButton("+ Thêm dòng hàng")
        btn_add_line.setFont(QFont(FONT, 11))
        btn_add_line.setFixedHeight(32)
        btn_add_line.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add_line.setStyleSheet("""
            QPushButton { border: 1px dashed #bbb; border-radius: 6px;
                background: white; color: #555; }
            QPushButton:hover { border-color: #888; color: #111; background: #f8f8f8; }
        """)
        btn_add_line.clicked.connect(lambda: self._add_line())
        root.addWidget(btn_add_line)

        root.addSpacing(20)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #eee;")
        root.addWidget(line)
        root.addSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Huỷ")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setFont(QFont(FONT, 12))
        btn_cancel.setStyleSheet("""
            QPushButton { border: 1px solid #ddd; border-radius: 6px;
                padding: 0 20px; background: white; color: #555; }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Lưu")
        btn_save.setFixedHeight(36)
        btn_save.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_save.setStyleSheet("""
            QPushButton { border: none; border-radius: 6px;
                padding: 0 28px; background: #111; color: white; }
            QPushButton:hover { background: #333; }
        """)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(8)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

        if receipt:
            self._fill(receipt)
        else:
            self._add_line()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _add_line(self, line: ReceiptLine | None = None):
        row = LineItemRow(self._item_types, self)
        if line:
            row.fill(line)
        row.removed.connect(self._remove_line)
        count = self._rows_layout.count()
        self._rows_layout.insertWidget(count - 1, row)

    def _remove_line(self, row: LineItemRow):
        self._rows_layout.removeWidget(row)
        row.deleteLater()

    def _fill(self, receipt: Receipt):
        self.f_ref.setText(receipt.reference_number)
        for i in range(self.f_wh.count()):
            if self.f_wh.itemData(i) == receipt.to_warehouse_id:
                self.f_wh.setCurrentIndex(i)
                break
        self.f_supplier.setText(receipt.supplier)
        self.f_person.setText(receipt.created_by)
        from PyQt6.QtCore import QDate
        d = QDate.fromString(receipt.transaction_date, "yyyy-MM-dd")
        if d.isValid():
            self.f_date.setDate(d)
        self.f_transport.setText(receipt.transporter)
        self.f_notes.setPlainText(receipt.notes)
        for line in get_lines(receipt.id):
            self._add_line(line)

    def _save(self):
        ref = self.f_ref.text().strip()
        if not ref:
            self._err("Vui lòng nhập Số Phiếu.")
            return
        wh_id = self.f_wh.currentData()
        if not wh_id:
            self._err("Vui lòng chọn Kho Nhập.")
            return
        lines: list[ReceiptLine] = []
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, LineItemRow):
                d = w.get_data()
                if d:
                    lines.append(d)
        if not lines:
            self._err("Vui lòng thêm ít nhất một mặt hàng.")
            return
        exclude = self._editing.id if self._editing else None
        if ref_exists(ref, exclude):
            self._err(f"Số Phiếu '{ref}' đã tồn tại.")
            return

        receipt = Receipt(
            id=self._editing.id if self._editing else None,
            reference_number=ref,
            to_warehouse_id=wh_id,
            to_warehouse_name="",
            transaction_date=self.f_date.date().toString("yyyy-MM-dd"),
            supplier=self.f_supplier.text().strip(),
            created_by=self.f_person.text().strip(),
            transporter=self.f_transport.text().strip(),
            notes=self.f_notes.toPlainText().strip(),
            lines=lines,
        )
        if self._editing:
            update(receipt)
        else:
            insert(receipt)
        self.accept()

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)
