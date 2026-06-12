from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QTextEdit,
    QPushButton, QComboBox, QCompleter, QMessageBox, QFrame, QWidget, QDateEdit,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from database.item_types import get_all as item_get_all
from database.warehouses import get_all as wh_get_all
from database.luan_chuyen import Transfer, TransferLine, insert, update, ref_exists, get_lines

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
    QSpinBox {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 8px; background: white; font-size: 12px;
    }
    QSpinBox:focus { border-color: #888; }
    QSpinBox::up-button, QSpinBox::down-button { width: 18px; }
"""

_TITLES = {
    "kho_kho": "Luân Chuyển Giữa Các Kho",
    "dv_dv":   "Luân Chuyển Giữa Các Đơn Vị",
}

_QL_OPTIONS = {
    "kho_kho": [("H1", "H1")],
    "dv_dv":   [("H2", "H2"), ("H3", "H3"), ("H4", "H4")],
}


class TransferLineRow(QWidget):
    removed = pyqtSignal(object)

    def __init__(self, item_types, subtype: str = "kho_kho", parent=None):
        super().__init__(parent)
        self._subtype = subtype
        self._show_ql = (subtype == "dv_dv")
        self.setStyleSheet("background: transparent;")

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(6)

        self.combo = QComboBox()
        self.combo.setFixedHeight(34)
        self.combo.setMinimumWidth(190)
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setStyleSheet(_FIELD)
        for it in item_types:
            self.combo.addItem(it.name, it)
        self.combo.setCurrentIndex(-1)
        self.combo.lineEdit().setPlaceholderText("Tìm mặt hàng...")
        self.combo.lineEdit().setReadOnly(False)
        completer = self.combo.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self.lbl_unit = QLabel("—")
        self.lbl_unit.setFixedWidth(56)
        self.lbl_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_unit.setFont(QFont(FONT, 11))
        self.lbl_unit.setStyleSheet(
            "color: #555; background: #f5f5f5; border-radius: 5px; padding: 2px 4px;"
        )

        if self._show_ql:
            self.combo_ql = QComboBox()
            self.combo_ql.setFixedHeight(34)
            self.combo_ql.setFixedWidth(72)
            self.combo_ql.setStyleSheet(_FIELD)
            for label, val in _QL_OPTIONS[subtype]:
                self.combo_ql.addItem(label, val)

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 9_999_999)
        self.spin_qty.setValue(1)
        self.spin_qty.setFixedWidth(80)
        self.spin_qty.setFixedHeight(34)
        self.spin_qty.setStyleSheet(_SPIN)

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
        if self._show_ql:
            h.addWidget(self.combo_ql)
        h.addWidget(self.spin_qty)
        h.addWidget(self.edit_notes, 1)
        h.addWidget(btn_del)

        self.combo.currentIndexChanged.connect(self._on_item_changed)

    def _on_item_changed(self, _):
        it = self.combo.currentData()
        self.lbl_unit.setText(it.unit_of_measure if it else "—")

    def get_data(self) -> TransferLine | None:
        it = self.combo.currentData()
        if not it:
            return None
        ql = self.combo_ql.currentData() if self._show_ql else "H1"
        return TransferLine(
            item_type_id=it.id,
            item_code=it.code,
            item_name=it.name,
            unit_of_measure=it.unit_of_measure,
            quantity=self.spin_qty.value(),
            quality_level=ql,
            notes=self.edit_notes.text().strip(),
        )

    def fill(self, line: TransferLine):
        for i in range(self.combo.count()):
            it = self.combo.itemData(i)
            if it and it.id == line.item_type_id:
                self.combo.setCurrentIndex(i)
                break
        if self._show_ql:
            for i in range(self.combo_ql.count()):
                if self.combo_ql.itemData(i) == line.quality_level:
                    self.combo_ql.setCurrentIndex(i)
                    break
        self.spin_qty.setValue(line.quantity)
        self.edit_notes.setText(line.notes)


class LuanChuyenFormDialog(QDialog):
    def __init__(self, parent=None, transfer: Transfer | None = None,
                 subtype: str = "kho_kho"):
        super().__init__(parent)
        self._editing = transfer
        self._subtype = transfer.subtype if transfer else subtype
        self._item_types = item_get_all()
        warehouses = wh_get_all()
        self._tong   = [w for w in warehouses if w.type == "TONG"]
        self._don_vi = [w for w in warehouses if w.type == "DON_VI"]

        title = _TITLES[self._subtype]
        if transfer:
            title = "Sửa – " + title
        self.setWindowTitle(title)
        self.setMinimumSize(900, 620)
        self.resize(980, 700)
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
                c.addItem(w.name, w.id)
            return c

        whs = self._don_vi if self._subtype == "dv_dv" else self._tong
        from_lbl = "Đơn Vị Nguồn *" if self._subtype == "dv_dv" else "Kho Nguồn *"
        to_lbl   = "Đơn Vị Đích *"  if self._subtype == "dv_dv" else "Kho Đích *"

        self.f_ref        = fld("VD: LC-001", 260)
        self.f_from_wh    = combo_wh(whs)
        self.f_to_wh      = combo_wh(whs)
        self.f_person     = fld("Tên người lập phiếu")
        self.f_transport  = fld("Phương tiện / đơn vị vận chuyển")
        self.f_deliverer  = fld("Tên người giao hàng")

        self.f_date = QDateEdit(QDate.currentDate())
        self.f_date.setDisplayFormat("dd/MM/yyyy")
        self.f_date.setCalendarPopup(True)
        self.f_date.setFixedHeight(36)
        self.f_date.setMaximumWidth(180)
        self.f_date.setFont(QFont(FONT, 12))
        self.f_date.setStyleSheet(_FIELD)

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Nội dung luân chuyển (tuỳ chọn)")
        self.f_notes.setFont(QFont(FONT, 12))
        self.f_notes.setFixedHeight(56)
        self.f_notes.setStyleSheet(_FIELD)

        row1 = QHBoxLayout()
        row1.setSpacing(24)

        col_a = QFormLayout()
        col_a.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_a.setSpacing(10)
        col_a.addRow(lbl("Số Phiếu *"), self.f_ref)
        col_a.addRow(lbl(from_lbl), self.f_from_wh)

        col_b = QFormLayout()
        col_b.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_b.setSpacing(10)
        col_b.addRow(lbl(to_lbl), self.f_to_wh)
        col_b.addRow(lbl("Người Lập"), self.f_person)

        col_c = QFormLayout()
        col_c.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_c.setSpacing(10)
        col_c.addRow(lbl("Ngày Luân Chuyển *"), self.f_date)
        col_c.addRow(lbl("Vận Chuyển"), self.f_transport)
        col_c.addRow(lbl("Người Giao"), self.f_deliverer)

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

        sec = QLabel("Danh Sách Hàng Luân Chuyển")
        sec.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        sec.setStyleSheet("color: #333;")
        root.addWidget(sec)
        root.addSpacing(6)

        hdr_w = QWidget()
        hdr_w.setStyleSheet("background: #f8f8f8; border-radius: 6px;")
        ch = QHBoxLayout(hdr_w)
        ch.setContentsMargins(6, 5, 6, 5)
        ch.setSpacing(6)
        col_defs = [("Mặt Hàng", 2, None), ("ĐVT", 0, 56)]
        if self._subtype == "dv_dv":
            col_defs.append(("Mức", 0, 72))
        col_defs += [("Số lượng", 0, 80), ("Ghi chú", 1, None), ("", 0, 32)]
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
        scroll.setMinimumHeight(200)
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

        if transfer:
            self._fill(transfer)
        else:
            self._add_line()

    def _add_line(self, line: TransferLine | None = None):
        row = TransferLineRow(self._item_types, subtype=self._subtype, parent=self)
        if line:
            row.fill(line)
        row.removed.connect(self._remove_line)
        count = self._rows_layout.count()
        self._rows_layout.insertWidget(count - 1, row)

    def _remove_line(self, row):
        self._rows_layout.removeWidget(row)
        row.deleteLater()

    def _fill(self, transfer: Transfer):
        self.f_ref.setText(transfer.reference_number)
        _set_combo_by_data(self.f_from_wh, transfer.from_warehouse_id)
        _set_combo_by_data(self.f_to_wh, transfer.to_warehouse_id)
        self.f_person.setText(transfer.created_by)
        self.f_transport.setText(transfer.transporter)
        self.f_deliverer.setText(transfer.deliverer)
        d = QDate.fromString(transfer.transaction_date, "yyyy-MM-dd")
        if d.isValid():
            self.f_date.setDate(d)
        self.f_notes.setPlainText(transfer.notes)
        for line in get_lines(transfer.id):
            self._add_line(line)

    def _save(self):
        ref = self.f_ref.text().strip()
        if not ref:
            return self._err("Vui lòng nhập Số Phiếu.")
        from_wh_id = self.f_from_wh.currentData()
        if not from_wh_id:
            label = "Đơn Vị Nguồn" if self._subtype == "dv_dv" else "Kho Nguồn"
            return self._err(f"Vui lòng chọn {label}.")
        to_wh_id = self.f_to_wh.currentData()
        if not to_wh_id:
            label = "Đơn Vị Đích" if self._subtype == "dv_dv" else "Kho Đích"
            return self._err(f"Vui lòng chọn {label}.")
        if from_wh_id == to_wh_id:
            return self._err("Nguồn và đích không được trùng nhau.")

        lines: list[TransferLine] = []
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, TransferLineRow):
                d = w.get_data()
                if d:
                    lines.append(d)
        if not lines:
            return self._err("Vui lòng thêm ít nhất một mặt hàng.")

        exclude = self._editing.id if self._editing else None
        if ref_exists(ref, exclude):
            return self._err(f"Số Phiếu '{ref}' đã tồn tại.")

        transfer = Transfer(
            id=self._editing.id if self._editing else None,
            reference_number=ref,
            from_warehouse_id=from_wh_id,
            from_warehouse_name="",
            to_warehouse_id=to_wh_id,
            to_warehouse_name="",
            transaction_date=self.f_date.date().toString("yyyy-MM-dd"),
            tx_type="LUAN_CHUYEN_DV" if self._subtype == "dv_dv" else "LUAN_CHUYEN_KHO",
            created_by=self.f_person.text().strip(),
            transporter=self.f_transport.text().strip(),
            deliverer=self.f_deliverer.text().strip(),
            notes=self.f_notes.toPlainText().strip(),
            lines=lines,
        )

        if self._editing:
            update(transfer)
        else:
            insert(transfer)
        self.accept()

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)


def _set_combo_by_data(combo: QComboBox, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
