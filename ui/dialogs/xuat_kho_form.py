from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QTextEdit,
    QPushButton, QComboBox, QCompleter, QMessageBox, QFrame, QWidget,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
import database
from database.item_types import get_all as item_get_all
from database.warehouses import get_all as wh_get_all
from database.xuat_kho import Issue, IssueLine, insert, update, ref_exists, get_lines

FONT = "Segoe UI"

_FIELD = """
    QLineEdit, QComboBox, QTextEdit {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 10px; background: white; font-size: 12px;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border-color: #888; }
    QComboBox::drop-down { border: none; width: 24px; }
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
    "to_unit":     "Xuất Kho Đi Đơn Vị",
    "shared_loan": "Xuất Hàng Dùng Chung (Cho Mượn)",
}


class _ComboItem:
    """Thin wrapper around ItemType that tags shared-pool (DC) entries."""
    __slots__ = ("it", "is_dc")
    def __init__(self, it, is_dc: bool = False):
        self.it = it
        self.is_dc = is_dc
    @property
    def id(self): return self.it.id
    @property
    def code(self): return self.it.code
    @property
    def name(self): return self.it.name
    @property
    def unit_of_measure(self): return self.it.unit_of_measure
    @property
    def unit_price(self): return self.it.unit_price
    @property
    def display_name(self):
        return f"{self.it.name} (DC)" if self.is_dc else self.it.name


class IssueLineRow(QWidget):
    removed = pyqtSignal(object)
    value_changed = pyqtSignal()
    item_changed = pyqtSignal()

    def __init__(self, item_types, show_price: bool = True,
                 show_quality: bool = False, stock_map: dict | None = None,
                 quality_levels: tuple = ("H1", "H2", "H3", "H4"),
                 parent=None):
        super().__init__(parent)
        self._item_types = item_types
        self._show_price = show_price
        self._show_quality = show_quality
        self._stock_map = stock_map or {}
        self._quality_levels = quality_levels
        self._unit_price = 0.0
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
            label = it.display_name if isinstance(it, _ComboItem) else it.name
            self.combo.addItem(label, it)
        self.combo.setCurrentIndex(-1)
        self.combo.lineEdit().setPlaceholderText("Tìm mặt hàng...")
        self.combo.lineEdit().setReadOnly(False)
        self._setup_search()

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

        self.lbl_stock = QLabel("—")
        self.lbl_stock.setFont(QFont(FONT, 10))
        self.lbl_stock.setFixedWidth(70)
        self.lbl_stock.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_stock.setStyleSheet("color: #999;")

        self.combo_quality = QComboBox()
        self.combo_quality.setFixedHeight(34)
        self.combo_quality.setFixedWidth(70)
        self.combo_quality.setFont(QFont(FONT, 12))
        for ql in quality_levels:
            self.combo_quality.addItem(ql)
        self.combo_quality.setStyleSheet("""
            QComboBox { border: 1px solid #ddd; border-radius: 6px;
                padding: 0 6px; background: white; font-size: 12px;
                font-weight: 600; color: #111; }
            QComboBox:focus { border-color: #888; }
            QComboBox::drop-down { border: none; width: 18px; }
        """)
        self.combo_quality.setVisible(show_quality)

        self.lbl_price = QLabel("—")
        self.lbl_price.setFixedWidth(130)
        self.lbl_price.setFixedHeight(34)
        self.lbl_price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_price.setFont(QFont(FONT, 11))
        self.lbl_price.setStyleSheet(
            "color: #555; background: #f5f5f5; border: 1px solid #e0e0e0;"
            " border-radius: 6px; padding: 0 8px;"
        )
        self.lbl_price.setVisible(show_price)

        self.lbl_total = QLabel("—")
        self.lbl_total.setFixedWidth(120)
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
        h.addWidget(self.lbl_stock)
        if show_quality:
            h.addWidget(self.combo_quality)
        if show_price:
            h.addWidget(self.lbl_price)
            h.addWidget(self.lbl_total)
        h.addWidget(self.edit_notes, 1)
        h.addWidget(btn_del)

        self.combo.currentIndexChanged.connect(self._on_item_changed)
        self.spin_qty.valueChanged.connect(self._recalc)
        if show_quality:
            self.combo_quality.currentIndexChanged.connect(self._on_ql_changed)

    def _setup_search(self):
        completer = self.combo.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def _on_item_changed(self, _):
        it = self.combo.currentData()
        self.lbl_unit.setText(it.unit_of_measure if it else "—")
        is_dc = isinstance(it, _ComboItem) and it.is_dc if it else False
        if self._show_quality:
            self.combo_quality.blockSignals(True)
            prev = self.combo_quality.currentText()
            self.combo_quality.clear()
            levels = ("H3", "H4") if is_dc else self._quality_levels
            for ql in levels:
                self.combo_quality.addItem(ql)
            idx = self.combo_quality.findText(prev)
            self.combo_quality.setCurrentIndex(idx if idx >= 0 else 0)
            self.combo_quality.blockSignals(False)
        if self._show_price and it and not is_dc:
            self._unit_price = it.unit_price or 0.0
            self.lbl_price.setText(f"{self._unit_price:,.0f} đ" if self._unit_price else "—")
        else:
            self._unit_price = 0.0
            self.lbl_price.setText("—")
        if self._show_price:
            self.lbl_price.setVisible(not is_dc)
            self.lbl_total.setVisible(not is_dc)
        self._update_max_qty()
        self._recalc()
        self.item_changed.emit()

    def _on_ql_changed(self, _):
        self._update_max_qty()

    def _update_max_qty(self):
        it = self.combo.currentData()
        if not it:
            self.spin_qty.setRange(1, 9_999_999)
            self.lbl_stock.setText("—")
            self.lbl_stock.setStyleSheet("color: #999;")
            return

        if self._show_quality:
            ql = self.combo_quality.currentText()
            is_dc = isinstance(it, _ComboItem) and it.is_dc
            if is_dc:
                stock = self._stock_map.get((it.id, ql, True), 0)
            else:
                stock = self._stock_map.get((it.id, ql), 0)
        else:
            stock = self._stock_map.get(it.id, 0)

        if stock > 0:
            current = self.spin_qty.value()
            self.spin_qty.setRange(1, stock)
            if current > stock:
                self.spin_qty.setValue(stock)
            self.lbl_stock.setText(f"còn {stock}")
            self.lbl_stock.setStyleSheet("color: #888;")
        else:
            self.spin_qty.setRange(0, 0)
            self.lbl_stock.setText("hết hàng")
            self.lbl_stock.setStyleSheet("color: #c00; font-weight: 600;")

    def update_stock_map(self, stock_map: dict):
        self._stock_map = stock_map
        self._update_max_qty()

    def set_item_types(self, item_types):
        current = self.combo.currentData()
        all_types = list(item_types)
        if current:
            cur_is_dc = isinstance(current, _ComboItem) and current.is_dc
            if not any(it.id == current.id and (isinstance(it, _ComboItem) and it.is_dc) == cur_is_dc
                       for it in all_types):
                all_types.append(current)
        self._item_types = all_types
        self.combo.blockSignals(True)
        self.combo.clear()
        for it in all_types:
            label = it.display_name if isinstance(it, _ComboItem) else it.name
            self.combo.addItem(label, it)
        if current:
            cur_is_dc = isinstance(current, _ComboItem) and current.is_dc
            for i in range(self.combo.count()):
                d = self.combo.itemData(i)
                if d and d.id == current.id and (isinstance(d, _ComboItem) and d.is_dc) == cur_is_dc:
                    self.combo.setCurrentIndex(i)
                    break
        else:
            self.combo.setCurrentIndex(-1)
        self.combo.blockSignals(False)
        self._setup_search()
        self._update_max_qty()

    def refresh_available(self, exclude_keys: set):
        """exclude_keys: set of (item_id, is_dc) tuples for rows already used."""
        current_it = self.combo.currentData()
        cur_is_dc = isinstance(current_it, _ComboItem) and current_it.is_dc if current_it else False
        current_key = (current_it.id, cur_is_dc) if current_it else None
        self.combo.blockSignals(True)
        self.combo.clear()
        for it in self._item_types:
            is_dc = isinstance(it, _ComboItem) and it.is_dc
            key = (it.id, is_dc)
            label = it.display_name if isinstance(it, _ComboItem) else it.name
            if key not in exclude_keys or key == current_key:
                self.combo.addItem(label, it)
        if current_key is not None:
            for i in range(self.combo.count()):
                d = self.combo.itemData(i)
                if d:
                    d_is_dc = isinstance(d, _ComboItem) and d.is_dc
                    if d.id == current_key[0] and d_is_dc == current_key[1]:
                        self.combo.setCurrentIndex(i)
                        break
        else:
            self.combo.setCurrentIndex(-1)
        self.combo.blockSignals(False)
        self._setup_search()

    def _recalc(self):
        total = self.spin_qty.value() * self._unit_price
        self.lbl_total.setText(f"{total:,.0f} đ" if total else "—")
        self.value_changed.emit()

    def get_data(self) -> IssueLine | None:
        it = self.combo.currentData()
        if not it:
            return None
        is_dc = isinstance(it, _ComboItem) and it.is_dc
        return IssueLine(
            item_type_id=it.id,
            item_code=it.code,
            item_name=it.name,
            unit_of_measure=it.unit_of_measure,
            quantity=self.spin_qty.value(),
            unit_price=self._unit_price,
            quality_level=self.combo_quality.currentText() if self._show_quality else "H1",
            notes=self.edit_notes.text().strip(),
            is_shared=is_dc,
        )

    def fill(self, line: IssueLine):
        target_is_dc = getattr(line, "is_shared", False)
        for i in range(self.combo.count()):
            it = self.combo.itemData(i)
            if it and it.id == line.item_type_id:
                it_is_dc = isinstance(it, _ComboItem) and it.is_dc
                if it_is_dc == target_is_dc:
                    self.combo.setCurrentIndex(i)
                    break
        # When editing, allow restoring the original quantity even if > current stock
        if line.quantity > self.spin_qty.maximum():
            self.spin_qty.setMaximum(line.quantity)
        self.spin_qty.setValue(line.quantity)
        if self._show_price:
            self._unit_price = line.unit_price or 0.0
            self.lbl_price.setText(f"{self._unit_price:,.0f} đ" if self._unit_price else "—")
        if self._show_quality:
            idx = self.combo_quality.findText(line.quality_level or "H1")
            if idx >= 0:
                self.combo_quality.setCurrentIndex(idx)
        self.edit_notes.setText(line.notes)


class XuatKhoFormDialog(QDialog):
    def __init__(self, parent=None, issue: Issue | None = None, subtype: str = "to_unit"):
        super().__init__(parent)
        self._editing = issue
        self._subtype = issue.subtype if issue else subtype
        self._item_types = item_get_all()
        warehouses = wh_get_all()
        self._tong = [w for w in warehouses if w.type == "TONG"]
        self._don_vi = [w for w in warehouses if w.type == "DON_VI"]
        self._stock_map: dict = {}

        show_price = (self._subtype == "to_unit")
        show_quality = True
        self._show_price = show_price
        self._show_quality = show_quality
        self._quality_levels = ("H1", "H2", "H3", "H4") if self._subtype == "to_unit" else ("H3",)
        self._shared_dest = "unit"
        self._regular_item_types: list = []   # hàng thường có tồn tại kho được chọn
        self._shared_item_types: list = []
        self._dc_item_types: list = []
        self._pending_dc_lines: list = []
        self._btn_unit_dest = self._btn_event_dest = None
        self._lbl_unit_dest = self._lbl_event_dest = None

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
                c.addItem(w.name, w.id)
            return c

        self.f_ref = fld("VD: XK-001", 260)
        self.f_from_wh = combo_wh(self._tong)
        self.f_to_wh = combo_wh(self._don_vi)
        self.f_person = fld("Tên đơn vị / người nhận")
        self.f_transport = fld("Phương tiện / đơn vị vận chuyển")
        self.f_event_name = fld("Tên sự kiện / đơn vị nhận")

        today = QDate.currentDate()
        self.f_date = QLineEdit(today.toString("dd/MM/yyyy"))
        self.f_date.setPlaceholderText("00/00/0000")
        self.f_date.setMaxLength(10)
        self.f_date.setFixedHeight(36)
        self.f_date.setFixedWidth(140)
        self.f_date.setFont(QFont(FONT, 12))
        self.f_date.setStyleSheet(_FIELD)
        self.f_date.textEdited.connect(self._fmt_date)

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
            col_b.addRow(lbl("Người Nhận"), self.f_person)
        else:
            tgl_w = QWidget()
            tgl_w.setFixedHeight(32)
            tgl_w.setStyleSheet("background: #f0f0f0; border-radius: 8px;")
            tgl_h = QHBoxLayout(tgl_w)
            tgl_h.setContentsMargins(3, 3, 3, 3)
            tgl_h.setSpacing(2)
            self._btn_unit_dest = QPushButton("Đơn Vị Mượn")
            self._btn_event_dest = QPushButton("Sự Kiện")
            for _b in (self._btn_unit_dest, self._btn_event_dest):
                _b.setFont(QFont(FONT, 11))
                _b.setFixedHeight(26)
                _b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                tgl_h.addWidget(_b)
            self._btn_unit_dest.clicked.connect(lambda: self._set_shared_dest("unit"))
            self._btn_event_dest.clicked.connect(lambda: self._set_shared_dest("event"))
            col_b.addRow(lbl("Xuất Đến *"), tgl_w)
            self._lbl_unit_dest = lbl("Đơn Vị Mượn")
            self._lbl_event_dest = lbl("Tên Sự Kiện")
            col_b.addRow(self._lbl_unit_dest, self.f_to_wh)
            col_b.addRow(self._lbl_event_dest, self.f_event_name)
            self.f_event_name.setVisible(False)
            self._lbl_event_dest.setVisible(False)
            self._update_dest_toggle_style()
            col_b.addRow(lbl("Người Mượn"), self.f_person)

        col_c = QFormLayout()
        col_c.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_c.setSpacing(10)
        date_lbl = "Ngày Xuất *" if self._subtype == "to_unit" else "Ngày Mượn *"
        col_c.addRow(lbl(date_lbl), self.f_date)
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

        # Column header strip
        hdr_w = QWidget()
        hdr_w.setStyleSheet("background: #f8f8f8; border-radius: 6px;")
        ch = QHBoxLayout(hdr_w)
        ch.setContentsMargins(6, 5, 6, 5)
        ch.setSpacing(6)
        col_defs = [("Mặt Hàng", 2, None), ("ĐVT", 0, 56), ("Số lượng", 0, 80), ("Còn lại", 0, 70)]
        if show_quality:
            col_defs += [("CL", 0, 70)]
        if show_price:
            col_defs += [("Đơn Giá", 0, 130), ("Thành Tiền", 0, 120)]
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

        # Rows container in scroll area
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

        self.f_from_wh.currentIndexChanged.connect(self._on_warehouse_changed)

        if issue:
            self._fill(issue)
        else:
            self._reload_stock_map()
            self._add_line()

    # ── Date auto-format ──────────────────────────────────────────────────────

    def _fmt_date(self, text: str):
        digits = "".join(c for c in text if c.isdigit())[:8]
        out = digits[:2]
        if len(digits) > 2:
            out += "/" + digits[2:4]
        if len(digits) > 4:
            out += "/" + digits[4:8]
        self.f_date.blockSignals(True)
        self.f_date.setText(out)
        self.f_date.blockSignals(False)
        self.f_date.setCursorPosition(len(out))

    # ── Stock ─────────────────────────────────────────────────────────────────

    def _on_warehouse_changed(self, _):
        self._reload_stock_map()
        self._push_stock_to_rows()

    def _reload_stock_map(self):
        wh_id = self.f_from_wh.currentData()
        if not wh_id:
            self._stock_map = {}
            self._regular_item_types = []
            self._shared_item_types = []
            self._dc_item_types = []
            return
        conn = database.get_conn()
        if self._subtype == "to_unit":
            rows = conn.execute("""
                SELECT item_type_id, quality_level, SUM(quantity) AS qty
                FROM inventory
                WHERE warehouse_id = ? AND is_shared = 0 AND quantity > 0
                GROUP BY item_type_id, quality_level
            """, (wh_id,)).fetchall()
            stock_map = {(r["item_type_id"], r["quality_level"]): r["qty"] for r in rows}
            regular_ids = {r["item_type_id"] for r in rows}
            self._regular_item_types = [it for it in self._item_types if it.id in regular_ids]
            dc_rows = conn.execute("""
                SELECT item_type_id, quality_level, SUM(quantity) AS qty
                FROM inventory
                WHERE warehouse_id = ? AND is_shared = 1
                  AND quality_level IN ('H3','H4') AND quantity > 0
                GROUP BY item_type_id, quality_level
            """, (wh_id,)).fetchall()
            for r in dc_rows:
                stock_map[(r["item_type_id"], r["quality_level"], True)] = r["qty"]
            self._stock_map = stock_map
            dc_ids = {r["item_type_id"] for r in dc_rows}
            self._dc_item_types = [_ComboItem(it, is_dc=True) for it in self._item_types if it.id in dc_ids]
        else:
            rows = conn.execute("""
                SELECT item_type_id, quality_level, SUM(quantity) AS qty
                FROM inventory
                WHERE warehouse_id = ? AND is_shared = 1
                  AND quality_level IN ('H1','H2','H3') AND quantity > 0
                GROUP BY item_type_id, quality_level
            """, (wh_id,)).fetchall()
            self._stock_map = {(r["item_type_id"], r["quality_level"]): r["qty"] for r in rows}
            shared_ids = {r["item_type_id"] for r in rows}
            self._shared_item_types = [it for it in self._item_types if it.id in shared_ids]

    def _push_stock_to_rows(self):
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                if self._subtype == "to_unit":
                    w.set_item_types(self._regular_item_types + self._dc_item_types)
                elif self._subtype == "shared_loan" and self._shared_item_types:
                    w.set_item_types(self._shared_item_types)
                w.update_stock_map(self._stock_map)

    # ── Combo deduplication ───────────────────────────────────────────────────

    def _refresh_all_combos(self):
        used: set = set()  # (item_type_id, is_dc) tuples
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                d = w.get_data()
                if d:
                    used.add((d.item_type_id, d.is_shared))
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                own_d = w.get_data()
                own_key = (own_d.item_type_id, own_d.is_shared) if own_d else None
                w.refresh_available(used - ({own_key} if own_key else set()))

    # ── Rows ──────────────────────────────────────────────────────────────────

    def _add_line(self, line: IssueLine | None = None):
        if self._subtype == "to_unit":
            item_types = self._regular_item_types + self._dc_item_types
        elif self._subtype == "shared_loan" and line is None and self._shared_item_types:
            item_types = self._shared_item_types
        else:
            item_types = self._item_types
        row = IssueLineRow(
            item_types,
            show_price=self._show_price,
            show_quality=self._show_quality,
            stock_map=self._stock_map,
            quality_levels=self._quality_levels,
            parent=self,
        )
        if line:
            row.fill(line)
        row.removed.connect(self._remove_line)
        row.item_changed.connect(self._refresh_all_combos)
        if self._subtype == "to_unit":
            row.item_changed.connect(self._sort_rows)
        if self._show_price:
            row.value_changed.connect(self._update_total)
        count = self._rows_layout.count()
        self._rows_layout.insertWidget(count - 1, row)
        self._refresh_all_combos()
        if self._show_price:
            self._update_total()

    def _sort_rows(self):
        """Move DC rows to the bottom of the item list."""
        layout = self._rows_layout
        regular, dc = [], []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                d = w.get_data()
                (dc if d and d.is_shared else regular).append(w)
        if not dc:
            return
        for w in regular + dc:
            layout.removeWidget(w)
        for i, w in enumerate(regular + dc):
            layout.insertWidget(i, w)

    def _remove_line(self, row):
        self._rows_layout.removeWidget(row)
        row.deleteLater()
        self._refresh_all_combos()
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

    # ── Fill (edit mode) ──────────────────────────────────────────────────────

    def _fill(self, issue: Issue):
        self.f_ref.setText(issue.reference_number)
        _set_combo_by_data(self.f_from_wh, issue.from_warehouse_id)
        self._reload_stock_map()
        self.f_transport.setText(issue.transporter)
        if self._subtype == "to_unit":
            _set_combo_by_data(self.f_to_wh, issue.to_warehouse_id)
            self.f_person.setText(issue.created_by)
        else:
            if issue.to_warehouse_id:
                self._set_shared_dest("unit")
                _set_combo_by_data(self.f_to_wh, issue.to_warehouse_id)
            else:
                self._set_shared_dest("event")
                self.f_event_name.setText(issue.recipient)
            self.f_person.setText(issue.created_by)
        d = QDate.fromString(issue.transaction_date, "yyyy-MM-dd")
        if d.isValid():
            self.f_date.setText(d.toString("dd/MM/yyyy"))
        self.f_notes.setPlainText(issue.notes)
        for line in get_lines(issue.id):
            self._add_line(line)

    # ── Shared dest toggle ────────────────────────────────────────────────────

    def _update_dest_toggle_style(self):
        if not self._btn_unit_dest:
            return
        active = (
            "QPushButton { border: none; border-radius: 6px; padding: 0 12px;"
            " background: #111; color: white; font-size: 11px; font-weight: 600; }"
        )
        inactive = (
            "QPushButton { border: none; border-radius: 6px; padding: 0 12px;"
            " background: transparent; color: #111; font-size: 11px; }"
            " QPushButton:hover { background: #e3e3e3; }"
        )
        self._btn_unit_dest.setStyleSheet(
            active if self._shared_dest == "unit" else inactive
        )
        self._btn_event_dest.setStyleSheet(
            active if self._shared_dest == "event" else inactive
        )

    def _set_shared_dest(self, dest_type: str):
        self._shared_dest = dest_type
        is_unit = dest_type == "unit"
        if self._lbl_unit_dest:
            self._lbl_unit_dest.setVisible(is_unit)
            self.f_to_wh.setVisible(is_unit)
        if self._lbl_event_dest:
            self._lbl_event_dest.setVisible(not is_unit)
            self.f_event_name.setVisible(not is_unit)
        self._update_dest_toggle_style()

    # ── Save ──────────────────────────────────────────────────────────────────

    def _build_issue(self) -> "Issue | None":
        ref = self.f_ref.text().strip()
        if not ref:
            self._err("Vui lòng nhập Số Phiếu.")
            return None
        _d = QDate.fromString(self.f_date.text(), "dd/MM/yyyy")
        if not _d.isValid():
            self._err("Ngày không hợp lệ. Vui lòng nhập đúng định dạng dd/MM/yyyy.")
            return None
        from_wh_id = self.f_from_wh.currentData()
        if not from_wh_id:
            self._err("Vui lòng chọn Kho Xuất.")
            return None

        if self._subtype == "to_unit":
            to_wh_id = self.f_to_wh.currentData()
            recipient = self.f_person.text().strip()
            person = recipient
            transport = self.f_transport.text().strip()
            notes_txt = self.f_notes.toPlainText().strip()
            if not person:
                self._err("Vui lòng nhập Người Nhận.")
                return None
            if not transport:
                self._err("Vui lòng nhập Vận Chuyển.")
                return None
            if not notes_txt:
                self._err("Vui lòng nhập Nội dung.")
                return None
        elif self._subtype == "shared_loan":
            if self._shared_dest == "unit":
                to_wh_id = self.f_to_wh.currentData()
                recipient = ""
            else:
                to_wh_id = None
                recipient = self.f_event_name.text().strip()
            transport = self.f_transport.text().strip()
            notes_txt = self.f_notes.toPlainText().strip()
        else:
            to_wh_id = self.f_to_wh.currentData()
            recipient = self.f_person.text().strip()
            transport = self.f_transport.text().strip()
            notes_txt = self.f_notes.toPlainText().strip()

        # Separate regular and DC (shared-pool) lines
        all_lines: list[IssueLine] = []
        dc_lines: list[IssueLine] = []
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, IssueLineRow):
                d = w.get_data()
                if d:
                    (dc_lines if d.is_shared else all_lines).append(d)
        self._pending_dc_lines = dc_lines

        if not all_lines and not dc_lines:
            self._err("Vui lòng thêm ít nhất một mặt hàng.")
            return None
        if not all_lines:
            self._err("Phiếu Xuất Đơn Vị cần ít nhất một mặt hàng thường.\n"
                      "Để xuất hàng dùng chung, hãy dùng tab Xuất Hàng Dùng Chung.")
            return None

        zero_lines = [l.item_name + (" (DC)" if l.is_shared else "") for l in all_lines + dc_lines if l.quantity <= 0]
        if zero_lines:
            self._err(
                "Mặt hàng sau đã hết tồn kho, không thể xuất:\n"
                + "\n".join(f"  • {n}" for n in zero_lines)
                + "\n\nVui lòng xóa các dòng hàng này trước khi lưu."
            )
            return None

        if not self._editing:
            self._reload_stock_map()
            for line in all_lines:
                if self._show_quality:
                    available = self._stock_map.get((line.item_type_id, line.quality_level), 0)
                else:
                    available = self._stock_map.get(line.item_type_id, 0)
                if line.quantity > available:
                    ql_info = f" ({line.quality_level})" if self._show_quality else ""
                    self._err(
                        f"'{line.item_name}'{ql_info} không đủ tồn kho.\n"
                        f"Tồn: {available}  –  Xuất: {line.quantity}"
                    )
                    return None
            for line in dc_lines:
                available = self._stock_map.get((line.item_type_id, line.quality_level, True), 0)
                if line.quantity > available:
                    self._err(
                        f"'{line.item_name} (DC)' ({line.quality_level}) không đủ tồn kho dùng chung.\n"
                        f"Tồn DC: {available}  –  Xuất: {line.quantity}"
                    )
                    return None

        exclude = self._editing.id if self._editing else None
        if ref_exists(ref, exclude):
            self._err(f"Số Phiếu '{ref}' đã tồn tại.")
            return None

        return Issue(
            id=self._editing.id if self._editing else None,
            reference_number=ref,
            from_warehouse_id=from_wh_id,
            from_warehouse_name="",
            to_warehouse_id=to_wh_id,
            to_warehouse_name="",
            transaction_date=_d.toString("yyyy-MM-dd"),
            tx_type="XUAT_KHO" if self._subtype == "to_unit" else "MUON",
            recipient=recipient,
            created_by=self.f_person.text().strip(),
            transporter=self.f_transport.text().strip(),
            notes=self.f_notes.toPlainText().strip(),
            lines=all_lines,
        )

    def _save(self):
        issue = self._build_issue()
        if issue is None:
            return
        if self._editing:
            update(issue)
        else:
            insert(issue)
            if self._pending_dc_lines and self._subtype == "to_unit":
                self._auto_create_muon(issue, self._pending_dc_lines)
        self.accept()

    def _on_export_voucher(self):
        issue = self._build_issue()
        if issue is None:
            return
        if self._editing:
            update(issue)
            tx_id = self._editing.id
        else:
            tx_id = insert(issue)
            if self._pending_dc_lines and self._subtype == "to_unit":
                self._auto_create_muon(issue, self._pending_dc_lines)
        self._export_phieu_xlsx(tx_id)
        self.accept()

    def _auto_create_muon(self, xuat_issue: "Issue", dc_lines: list) -> None:
        """Automatically create a MUON transaction for DC lines embedded in a to_unit phiếu."""
        dc_ref = f"{xuat_issue.reference_number}-DC"
        n = 2
        while ref_exists(dc_ref):
            dc_ref = f"{xuat_issue.reference_number}-DC{n}"
            n += 1
        muon = Issue(
            id=None,
            reference_number=dc_ref,
            from_warehouse_id=xuat_issue.from_warehouse_id,
            from_warehouse_name="",
            to_warehouse_id=xuat_issue.to_warehouse_id,
            to_warehouse_name="",
            transaction_date=xuat_issue.transaction_date,
            tx_type="MUON",
            recipient="",
            created_by=xuat_issue.created_by,
            transporter=xuat_issue.transporter,
            notes=xuat_issue.notes,
            lines=dc_lines,
        )
        insert(muon)

    def _export_phieu_xlsx(self, tx_id: int):
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Thiếu thư viện",
                                "Cần cài openpyxl: pip install openpyxl")
            return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Phiếu Xuất Dùng Chung", "phieu_xuat_dung_chung.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            conn = database.get_conn()
            tx = conn.execute("""
                SELECT t.reference_number, t.transaction_date, t.supplier AS recipient,
                       t.created_by, t.transporter, t.notes,
                       wf.name AS from_wh_name, wt.name AS to_wh_name
                FROM transactions t
                LEFT JOIN warehouses wf ON wf.id = t.from_warehouse_id
                LEFT JOIN warehouses wt ON wt.id = t.to_warehouse_id
                WHERE t.id = ?
            """, (tx_id,)).fetchone()
            item_lines = conn.execute("""
                SELECT it.name AS item_name, it.unit_of_measure,
                       tl.quantity, tl.notes
                FROM transaction_lines tl
                JOIN item_types it ON it.id = tl.item_type_id
                WHERE tl.transaction_id = ?
                ORDER BY tl.id
            """, (tx_id,)).fetchall()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Phiếu Xuất Dùng Chung"
            ws.append(["PHIẾU XUẤT HÀNG DÙNG CHUNG"])
            ws.append([])
            ws.append(["Số Phiếu:", tx["reference_number"] or "", "",
                        "Ngày:", tx["transaction_date"] or ""])
            ws.append(["Kho Xuất:", tx["from_wh_name"] or "", "",
                        "Vận Chuyển:", tx["transporter"] or ""])
            borrower = tx["to_wh_name"] or tx["recipient"] or ""
            ws.append(["Đơn Vị / Sự Kiện:", borrower, "",
                        "Người Mượn:", tx["created_by"] or ""])
            if tx["notes"]:
                ws.append(["Nội Dung:", tx["notes"]])
            ws.append([])
            ws.append(["STT", "Tên Hàng", "ĐVT", "Số Lượng", "Ghi Chú"])
            for i, ln in enumerate(item_lines, 1):
                ws.append([i, ln["item_name"], ln["unit_of_measure"],
                            ln["quantity"], ln["notes"] or ""])

            for col in ws.columns:
                max_len = max((len(str(c.value)) for c in col if c.value), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

            wb.save(path)
            QMessageBox.information(self, "Hoàn tất", f"Đã lưu phiếu.\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)


def _set_combo_by_data(combo: QComboBox, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
