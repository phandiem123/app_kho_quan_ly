from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit,
    QPushButton, QComboBox, QMessageBox, QFrame, QWidget, QDateEdit,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from database.item_types import get_all as item_get_all
from database.warehouses import get_all as wh_get_all
from database.xuat_kho import Issue, IssueLine, insert, update, ref_exists, get_lines

FONT = "Segoe UI"

_FIELD = """
    QLineEdit, QComboBox, QTextEdit, QDateEdit {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 10px; background: white; font-size: 12px;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QDateEdit:focus { border-color: #888; }
    QComboBox::drop-down { border: none; width: 24px; }
    QDateEdit::drop-down  { border: none; width: 24px; }
"""
_SPIN = """
    QSpinBox, QDoubleSpinBox {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 8px; background: white; font-size: 12px;
    }
    QSpinBox:focus, QDoubleSpinBox:focus { border-color: #888; }
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 18px; }
"""

_TITLES = {
    "to_unit":     "Xuất Kho Đi Đơn Vị",
    "shared_loan": "Xuất Hàng Dùng Chung (Cho Mượn)",
}


class IssueLineRow(QWidget):
    removed = pyqtSignal(object)
    value_changed = pyqtSignal()

    def __init__(self, item_types, show_price: bool = True, parent=None):
        super().__init__(parent)
        self._show_price = show_price
        self.setStyleSheet("background: transparent;")

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(6)

        self.combo = QComboBox()
        self.combo.setFixedHeight(34)
        self.combo.setMinimumWidth(190)
        self.combo.setStyleSheet(_FIELD)
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
        self.spin_qty.setStyleSheet(_SPIN)

        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0, 999_999_999_999)
        self.spin_price.setDecimals(0)
        self.spin_price.setFixedWidth(120)
        self.spin_price.setFixedHeight(34)
        self.spin_price.setStyleSheet(_SPIN)
        self.spin_price.setVisible(show_price)

        self.lbl_total = QLabel("—")
        self.lbl_total.setFixedWidth(120)
        self.lbl_total.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.lbl_total.setFont(QFont(FONT, 11, QFont.Weight.Medium))
        self.lbl_total.setStyleSheet("color: #333; background: transparent;")
        self.lbl_total.setVisible(show_price)

        self.edit_notes = QLineEdit()
        self.edit_notes.setPlaceholderText("Ghi chú")
        self.edit_notes.setFixedHeight(34)
        self.edit_notes.setStyleSheet(_FIELD)

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
        if show_price:
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
        if hasattr(it, "unit_price") and it.unit_price and self.spin_price.isVisible():
            self.spin_price.setValue(it.unit_price)
        self._recalc()

    def _recalc(self):
        total = self.spin_qty.value() * self.spin_price.value()
        self.lbl_total.setText(f"{total:,.0f} đ" if total else "—")
        self.value_changed.emit()

    def get_data(self) -> IssueLine | None:
        it = self.combo.currentData()
        if not it:
            return None
        return IssueLine(
            item_type_id=it.id,
            item_code=it.code,
            item_name=it.name,
            unit_of_measure=it.unit_of_measure,
            quantity=self.spin_qty.value(),
            unit_price=self.spin_price.value(),
            notes=self.edit_notes.text().strip(),
        )

    def fill(self, line: IssueLine):
        for i in range(self.combo.count()):
            it = self.combo.itemData(i)
            if it and it.id == line.item_type_id:
                self.combo.setCurrentIndex(i)
                break
        self.spin_qty.setValue(line.quantity)
        self.spin_price.setValue(line.unit_price)
        self.edit_notes.setText(line.notes)


class XuatKhoFormDialog(QDialog):
    def __init__(self, parent=None, issue: Issue | None = None, subtype: str = "to_unit"):
        super().__init__(parent)
        self._editing  = issue
        self._subtype  = issue.subtype if issue else subtype
        self._item_types = item_get_all()
        warehouses       = wh_get_all()
        self._tong   = [w for w in warehouses if w.type == "TONG"]
        self._don_vi = [w for w in warehouses if w.type == "DON_VI"]
        self._all_wh = warehouses

        title = _TITLES[self._subtype]
        if issue:
            title = "Sửa – " + title
        self.setWindowTitle(title)
        self.setMinimumSize(1000, 700)
        self.resize(1060, 780)
        self.setModal(True)
        self.setStyleSheet("background: white;")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        hdr = QLabel(title)
        hdr.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #111; margin-bottom: 20px;")
        root.addWidget(hdr)

        def lbl(t):
            l = QLabel(t)
            l.setFont(QFont(FONT, 12))
            l.setStyleSheet("color: #555;")
            return l

        def fld(ph="", w=None):
            e = QLineEdit()
            e.setPlaceholderText(ph)
            e.setFont(QFont(FONT, 12))
            e.setFixedHeight(36)
            if w:
                e.setMaximumWidth(w)
            e.setStyleSheet(_FIELD)
            return e

        def combo_wh(whs):
            c = QComboBox()
            c.setFont(QFont(FONT, 12))
            c.setFixedHeight(36)
            c.setMaximumWidth(280)
            c.setStyleSheet(_FIELD)
            c.addItem("— Chọn —", None)
            for w in whs:
                c.addItem(f"{w.code} – {w.name}", w.id)
            return c

        self.f_ref       = fld("VD: XK-001", 260)
        self.f_from_wh   = combo_wh(self._tong)
        self.f_to_wh     = combo_wh(self._don_vi)
        self.f_recipient = fld("Tên đơn vị / người nhận (nếu không có trong hệ thống)")
        self.f_person    = fld("Tên người lập phiếu")
        self.f_transport = fld("Phương tiện / đơn vị vận chuyển")

        self.f_date = QDateEdit(QDate.currentDate())
        self.f_date.setDisplayFormat("dd/MM/yyyy")
        self.f_date.setCalendarPopup(True)
        self.f_date.setFixedHeight(36)
        self.f_date.setMaximumWidth(180)
        self.f_date.setFont(QFont(FONT, 12))
        self.f_date.setStyleSheet(_FIELD)

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Nội dung xuất kho (tuỳ chọn)")
        self.f_notes.setFont(QFont(FONT, 12))
        self.f_notes.setFixedHeight(56)
        self.f_notes.setStyleSheet(_FIELD)

        row1 = QHBoxLayout()
        row1.setSpacing(24)

        col_a = QFormLayout()
        col_a.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_a.setSpacing(10)
        col_a.addRow(lbl("Số Phiếu *"), self.f_ref)
        col_a.addRow(lbl("Kho Xuất *"), self.f_from_wh)

        col_b = QFormLayout()
        col_b.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_b.setSpacing(10)
        if self._subtype == "to_unit":
            col_b.addRow(lbl("Đơn Vị Nhận"), self.f_to_wh)
            col_b.addRow(lbl("Người Nhận"),  self.f_person)
        else:
            col_b.addRow(lbl("Đơn Vị Mượn"), self.f_to_wh)
            col_b.addRow(lbl("Người Mượn"),   self.f_person)

        col_c = QFormLayout()
        col_c.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_c.setSpacing(10)
        date_lbl = "Ngày Xuất *" if self._subtype == "to_unit" else "Ngày Mượn *"
        col_c.addRow(lbl(date_lbl), self.f_date)
        if self._subtype == "to_unit":
            col_c.addRow(lbl("Vận Chuyển"), self.f_transport)

        row1.addLayout(col_a, 1)
        row1.addLayout(col_b, 1)
        row1.addLayout(col_c, 1)
        root.addLayout(row1)
        root.addSpacing(8)

        notes_row = QFormLayout()
        notes_row.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        notes_row.addRow(lbl("Nội dung"), self.f_notes)
        root.addLayout(notes_row)
        root.addSpacing(20)

        sec = QLabel("Danh Sách Hàng Xuất")
        sec.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        sec.setStyleSheet("color: #333;")
        root.addWidget(sec)
        root.addSpacing(6)

        show_price = (self._subtype == "to_unit")

        hdr_w = QWidget()
        hdr_w.setStyleSheet("background: #f8f8f8; border-radius: 6px;")
        ch = QHBoxLayout(hdr_w)
        ch.setContentsMargins(6, 5, 6, 5)
        ch.setSpacing(6)
        col_defs = [("Mặt Hàng", 2, None), ("ĐVT", 0, 56), ("Số lượng", 0, 80)]
        if show_price:
            col_defs += [("Đơn Giá", 0, 120), ("Thành Tiền", 0, 120)]
        col_defs += [("Ghi chú", 1, None), ("", 0, 32)]
        for txt, stretch, w in col_defs:
            l = QLabel(txt)
            l.setFont(QFont(FONT, 10))
            l.setStyleSheet("color: #999;")
            if w:
                l.setFixedWidth(w)
                ch.addWidget(l)
            else:
                ch.addWidget(l, stretch)
        root.addWidget(hdr_w)

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
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setMinimumHeight(240)
        root.addWidget(scroll, 1)

        btn_add = QPushButton("+ Thêm dòng hàng")
        btn_add.setFont(QFont(FONT, 11))
        btn_add.setFixedHeight(32)
        btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add.setStyleSheet("""
            QPushButton { border: 1px dashed #bbb; border-radius: 6px;
                background: white; color: #555; }
            QPushButton:hover { border-color: #888; color: #111; background: #f8f8f8; }
        """)
        btn_add.clicked.connect(lambda: self._add_line())
        root.addWidget(btn_add)

        if show_price:
            tr = QHBoxLayout()
            tr.addStretch()
            tc = QLabel("Tổng tiền:")
            tc.setFont(QFont(FONT, 12))
            tc.setStyleSheet("color: #555;")
            self._form_total_lbl = QLabel("0 đ")
            self._form_total_lbl.setFont(QFont(FONT, 13, QFont.Weight.Bold))
            self._form_total_lbl.setStyleSheet("color: #111;")
            tr.addWidget(tc)
            tr.addSpacing(8)
            tr.addWidget(self._form_total_lbl)
            root.addLayout(tr)

        root.addSpacing(20)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #eee;")
        root.addWidget(sep)
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

        self._show_price = show_price

        if issue:
            self._fill(issue)
        else:
            self._add_line()

    def _add_line(self, line: IssueLine | None = None):
        row = IssueLineRow(self._item_types, show_price=self._show_price, parent=self)
        if line:
            row.fill(line)
        row.removed.connect(self._remove_line)
        if self._show_price:
            row.value_changed.connect(self._update_total)
        count = self._rows_layout.count()
        self._rows_layout.insertWidget(count - 1, row)
        if self._show_price:
            self._update_total()

    def _remove_line(self, row):
        self._rows_layout.removeWidget(row)
        row.deleteLater()
        if self._show_price:
            self._update_total()

    def _update_total(self):
        total = 0
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                d = w.get_data()
                if d:
                    total += d.quantity * d.unit_price
        self._form_total_lbl.setText(f"{total:,.0f} đ")

    def _fill(self, issue: Issue):
        self.f_ref.setText(issue.reference_number)
        _set_combo_by_data(self.f_from_wh, issue.from_warehouse_id)
        _set_combo_by_data(self.f_to_wh, issue.to_warehouse_id)
        self.f_person.setText(issue.created_by)
        self.f_transport.setText(issue.transporter)
        d = QDate.fromString(issue.transaction_date, "yyyy-MM-dd")
        if d.isValid():
            self.f_date.setDate(d)
        self.f_notes.setPlainText(issue.notes)
        for line in get_lines(issue.id):
            self._add_line(line)

    def _save(self):
        ref = self.f_ref.text().strip()
        if not ref:
            return self._err("Vui lòng nhập Số Phiếu.")
        from_wh_id = self.f_from_wh.currentData()
        if not from_wh_id:
            return self._err("Vui lòng chọn Kho Xuất.")
        to_wh_id = self.f_to_wh.currentData()

        lines: list[IssueLine] = []
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                d = w.get_data()
                if d:
                    lines.append(d)
        if not lines:
            return self._err("Vui lòng thêm ít nhất một mặt hàng.")

        exclude = self._editing.id if self._editing else None
        if ref_exists(ref, exclude):
            return self._err(f"Số Phiếu '{ref}' đã tồn tại.")

        issue = Issue(
            id=self._editing.id if self._editing else None,
            reference_number=ref,
            from_warehouse_id=from_wh_id,
            from_warehouse_name="",
            to_warehouse_id=to_wh_id,
            to_warehouse_name="",
            transaction_date=self.f_date.date().toString("yyyy-MM-dd"),
            tx_type="XUAT_KHO" if self._subtype == "to_unit" else "MUON",
            recipient=self.f_recipient.text().strip(),
            created_by=self.f_person.text().strip(),
            transporter=self.f_transport.text().strip(),
            notes=self.f_notes.toPlainText().strip(),
            lines=lines,
        )

        if self._editing:
            update(issue)
        else:
            insert(issue)
        self.accept()

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)


def _set_combo_by_data(combo: QComboBox, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
