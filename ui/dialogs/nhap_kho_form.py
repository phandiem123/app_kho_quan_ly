from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QTextEdit,
    QPushButton, QComboBox, QCompleter, QMessageBox, QFrame, QWidget,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from database.item_types import get_all as item_get_all
from database.warehouses import get_all as wh_get_all
from database.receipts import (
    Receipt, ReceiptLine, insert, update, ref_exists, get_lines,
)
from database.xuat_kho import (
    get_loan_events, get_loan_items_remaining, get_unit_loan_items_remaining,
)

FONT = "Segoe UI"


class _DisplayItem:
    """Wrapper cho ItemType với tên hiển thị tuỳ chỉnh (thêm hậu tố DC/H4)."""
    __slots__ = ('id', 'code', 'name', 'display_name', 'unit_of_measure', 'unit_price', 'category', 'qty')

    def __init__(self, id, code, name, display_name, unit_of_measure, unit_price, category, qty=0):
        self.id = id
        self.code = code
        self.name = name               # tên gốc — dùng khi lưu ReceiptLine
        self.display_name = display_name  # tên hiển thị — dùng trong combo
        self.unit_of_measure = unit_of_measure
        self.unit_price = unit_price
        self.category = category       # 'NORMAL' | 'H4'
        self.qty = qty                 # tổng tồn tại đơn vị


def _get_unit_item_entries(unit_wh_id: int) -> list[_DisplayItem]:
    """Trả về danh sách mặt hàng tại đơn vị, phân loại NORMAL/H4/SHARED.
    SHARED = hàng dùng chung (is_shared=1). H4 và SHARED luôn có hậu tố."""
    import database
    conn = database.get_conn()
    rows = conn.execute("""
        SELECT it.id, it.code, it.name, it.unit_of_measure,
               COALESCE(it.unit_price, 0) AS unit_price,
               CASE
                   WHEN i.is_shared = 1                          THEN 'SHARED'
                   WHEN i.quality_level = 'H4' AND i.is_shared = 0 THEN 'H4'
                   ELSE 'NORMAL'
               END AS category,
               SUM(i.quantity) AS total_qty
        FROM inventory i
        JOIN item_types it ON it.id = i.item_type_id
        WHERE i.warehouse_id = ? AND i.quantity > 0 AND it.is_active = 1
        GROUP BY it.id, category
        HAVING total_qty > 0
        ORDER BY it.name, category
    """, (unit_wh_id,)).fetchall()

    entries = []
    for r in rows:
        name = r["name"]
        if r["category"] == "SHARED":
            display = f"{name} (DC)"
        elif r["category"] == "H4":
            display = f"{name} (H4)"
        else:
            display = name
        entries.append(_DisplayItem(
            id=r["id"],
            code=r["code"],
            name=name,
            display_name=display,
            unit_of_measure=r["unit_of_measure"],
            unit_price=float(r["unit_price"]),
            category=r["category"],
            qty=int(r["total_qty"] or 0),
        ))
    return entries

_FIELD = """
    QLineEdit, QComboBox, QTextEdit, QDateEdit {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 10px; background: white; font-size: 12px;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QDateEdit:focus { border-color: #888; }
    QComboBox::drop-down { border: none; width: 24px; }
    QDateEdit::drop-down { border: none; width: 24px; }
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
    "new":            "Nhập Hàng Mới",
    "from_unit":      "Nhập Hàng Từ Đơn Vị Về",
    "unit_return":    "Nhận Hàng Dùng Chung – Đơn Vị Trả",
    "event_return":   "Nhận Hàng Dùng Chung – Sự Kiện Trả",
    "shared_return":  "Nhận Hàng Dùng Chung Về",
    "shared_from_wh": "Nhập Hàng Dùng Chung Từ Kho",
}


class LineItemRow(QWidget):
    removed = pyqtSignal(object)
    value_changed = pyqtSignal()
    item_changed = pyqtSignal()

    def __init__(self, item_types, show_price: bool = True,
                 show_quality: bool = False, max_qty_map: dict | None = None,
                 dynamic_price_by_category: bool = False,
                 parent=None):
        super().__init__(parent)
        self._item_types = item_types
        self._show_quality = show_quality
        self._max_qty_map: dict[int, int] = max_qty_map or {}
        self._dynamic_price_by_category = dynamic_price_by_category
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
            self.combo.addItem(getattr(it, 'display_name', it.name), it)
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

        self.lbl_remaining = QLabel("")
        self.lbl_remaining.setFixedWidth(66)
        self.lbl_remaining.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_remaining.setFont(QFont(FONT, 10))
        self.lbl_remaining.setStyleSheet("color: #999; background: transparent;")
        self.lbl_remaining.setVisible(bool(self._max_qty_map))

        self.combo_quality = QComboBox()
        self.combo_quality.setFixedHeight(34)
        self.combo_quality.setFixedWidth(70)
        self.combo_quality.setFont(QFont(FONT, 12))
        for ql in ("H1", "H2", "H3", "H4"):
            self.combo_quality.addItem(ql)
        self.combo_quality.setStyleSheet("""
            QComboBox { border: 1px solid #ddd; border-radius: 6px;
                padding: 0 6px; background: white; font-size: 12px;
                font-weight: 600; color: #111; }
            QComboBox:focus { border-color: #888; }
            QComboBox::drop-down { border: none; width: 18px; }
        """)
        self.combo_quality.setVisible(show_quality)

        self._show_price = show_price
        self._unit_price = 0.0

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
        h.addWidget(self.lbl_remaining)
        if show_quality:
            h.addWidget(self.combo_quality)
        if show_price:
            h.addWidget(self.lbl_price)
            h.addWidget(self.lbl_total)
        h.addWidget(self.edit_notes, 1)
        h.addWidget(btn_del)

        self.combo.currentIndexChanged.connect(self._on_item_changed)
        self.spin_qty.valueChanged.connect(self._recalc)

    def _setup_search(self):
        completer = self.combo.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def _on_item_changed(self, _):
        it = self.combo.currentData()
        self.lbl_unit.setText(it.unit_of_measure if it else "—")
        cat = self._dynamic_price_by_category and it and getattr(it, 'category', None)
        is_h4     = (cat == 'H4')
        is_shared = (cat == 'SHARED')
        no_price  = is_h4 or is_shared

        # Remaining quantity
        if self._max_qty_map and it:
            max_q = self._max_qty_map.get(it.id, 0)
            self.spin_qty.setRange(1, max(1, max_q))
            if self.spin_qty.value() > max_q:
                self.spin_qty.setValue(max(1, max_q))
            self.lbl_remaining.setText(f"≤ {max_q}")
            self.lbl_remaining.setVisible(True)
        elif it and not self._max_qty_map and hasattr(it, 'qty') and it.qty > 0:
            max_q = it.qty
            self.spin_qty.setRange(1, max_q)
            if self.spin_qty.value() > max_q:
                self.spin_qty.setValue(max_q)
            self.lbl_remaining.setText(f"≤ {max_q}")
            self.lbl_remaining.setVisible(True)
        else:
            self.spin_qty.setRange(1, 9_999_999)
            self.lbl_remaining.setVisible(False)

        # Price display — hide for H4 and DC items
        if self._show_price:
            self.lbl_price.setVisible(not no_price)
            self.lbl_total.setVisible(not no_price)
            if not no_price and it:
                self._unit_price = it.unit_price or 0.0
                self.lbl_price.setText(f"{self._unit_price:,.0f} đ" if self._unit_price else "—")
            else:
                self._unit_price = 0.0
                self.lbl_price.setText("—")
        else:
            self._unit_price = 0.0
            self.lbl_price.setText("—")

        # Quality combo — lock to H4 for H4 items, H3 for DC items
        if self._show_quality:
            if is_h4 or is_shared:
                lock_ql = "H4" if is_h4 else "H3"
                self.combo_quality.blockSignals(True)
                idx = self.combo_quality.findText(lock_ql)
                if idx >= 0:
                    self.combo_quality.setCurrentIndex(idx)
                self.combo_quality.setEnabled(False)
                self.combo_quality.blockSignals(False)
            else:
                self.combo_quality.setEnabled(True)

        self._recalc()
        self.item_changed.emit()

    def update_max_qty_map(self, max_qty_map: dict[int, int]):
        self._max_qty_map = max_qty_map
        self.lbl_remaining.setVisible(bool(max_qty_map))
        self._on_item_changed(None)

    def refresh_available(self, exclude_ids: set):
        current_it = self.combo.currentData()
        current_id = current_it.id if current_it else None
        self.combo.blockSignals(True)
        self.combo.clear()
        for it in self._item_types:
            if it.id not in exclude_ids or it.id == current_id:
                self.combo.addItem(getattr(it, 'display_name', it.name), it)
        if current_id is not None:
            for i in range(self.combo.count()):
                d = self.combo.itemData(i)
                if d and d.id == current_id:
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

    def get_data(self) -> ReceiptLine | None:
        it = self.combo.currentData()
        if not it:
            return None
        cat = self._dynamic_price_by_category and getattr(it, 'category', None)
        is_shared = (cat == 'SHARED')
        is_h4     = (cat == 'H4')
        if is_shared:
            quality_level = "H3"
        elif is_h4:
            quality_level = "H4"
        else:
            quality_level = self.combo_quality.currentText() if self._show_quality else "H1"
        return ReceiptLine(
            item_type_id=it.id,
            item_code=it.code,
            item_name=it.name,
            unit_of_measure=it.unit_of_measure,
            quantity=self.spin_qty.value(),
            unit_price=self._unit_price,
            notes=self.edit_notes.text().strip(),
            quality_level=quality_level,
            is_shared=is_shared,
        )

    def fill(self, line: ReceiptLine):
        preferred_cat = 'H4' if line.quality_level == 'H4' else 'NORMAL'
        best_idx = -1
        for i in range(self.combo.count()):
            it = self.combo.itemData(i)
            if it and it.id == line.item_type_id:
                if best_idx == -1:
                    best_idx = i
                if getattr(it, 'category', None) == preferred_cat:
                    best_idx = i
                    break
        if best_idx >= 0:
            self.combo.setCurrentIndex(best_idx)
        if line.quantity > self.spin_qty.maximum():
            self.spin_qty.setMaximum(line.quantity)
        self.spin_qty.setValue(line.quantity)
        if self._show_price:
            self._unit_price = line.unit_price or 0.0
            self.lbl_price.setText(f"{self._unit_price:,.0f} đ" if self._unit_price else "—")
        self.edit_notes.setText(line.notes)
        if self._show_quality:
            idx = self.combo_quality.findText(line.quality_level)
            if idx >= 0:
                self.combo_quality.setCurrentIndex(idx)


class NhapKhoFormDialog(QDialog):
    def __init__(self, parent=None, receipt: Receipt | None = None,
                 subtype: str = "new"):
        super().__init__(parent)
        self._editing = receipt
        self._subtype = receipt.subtype if receipt else subtype
        self._item_types = item_get_all()
        warehouses = wh_get_all()
        self._tong = [w for w in warehouses if w.type == "TONG"]
        self._don_vi = [w for w in warehouses if w.type == "DON_VI"]

        title = _TITLES[self._subtype]
        if receipt:
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

        # ── Fields ──────────────────────────────────────────────────────────
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

        def combo_wh(warehouses):
            c = QComboBox()
            c.setFont(QFont(FONT, 12))
            c.setFixedHeight(36)
            c.setMaximumWidth(280)
            c.setStyleSheet(_FIELD)
            c.addItem("— Chọn —", None)
            for w in warehouses:
                c.addItem(w.name, w.id)
            return c

        self.f_ref = fld("VD: QL-001", 260)
        self.f_wh = combo_wh(self._tong)

        today = QDate.currentDate()
        self.f_date = QLineEdit(today.toString("dd/MM/yyyy"))
        self.f_date.setPlaceholderText("00/00/0000")
        self.f_date.setMaxLength(10)
        self.f_date.setFixedHeight(36)
        self.f_date.setFixedWidth(140)
        self.f_date.setFont(QFont(FONT, 12))
        self.f_date.setStyleSheet(_FIELD)
        self.f_date.textEdited.connect(self._fmt_date)

        self.f_person = fld("Tên người giao")
        ph_sup = "Đơn vị / công ty cung cấp" if self._subtype == "new" else "Tên sự kiện / nguồn"
        self.f_supplier = fld(ph_sup)
        self.f_transport = fld("Phương tiện / đơn vị vận chuyển")
        self._from_label = {
            "from_unit":   "Đơn Vị Giao *",
            "unit_return": "Đơn Vị Trả *",
        }.get(self._subtype, "")
        self.f_from_wh = combo_wh(self._don_vi)

        self.f_src_wh = combo_wh(self._tong)  # kho nguồn cho shared_from_wh

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Nội dung nhập kho (tuỳ chọn)")
        self.f_notes.setFont(QFont(FONT, 12))
        self.f_notes.setFixedHeight(56)
        self.f_notes.setStyleSheet(_FIELD)

        self._shared_source = "unit_return"
        self._btn_unit_src = self._btn_event_src = self._btn_wh_src = None
        self._lbl_unit_src = self._lbl_event_src = self._lbl_wh_src = None
        self._loan_tx_id: int | None = None
        # Loan-item restriction (for return subtypes)
        self._loan_item_types_filtered: list = []
        self._loan_max_qty_map: dict[int, int] = {}
        self._is_return_mode = self._subtype in ("unit_return", "event_return", "shared_return")
        self._unit_item_types: list = []  # hàng lọc theo đơn vị cho subtype from_unit

        # Build event combo for event_return / shared_return-event source
        self.f_event_combo = QComboBox()
        self.f_event_combo.setFont(QFont(FONT, 12))
        self.f_event_combo.setFixedHeight(36)
        self.f_event_combo.setStyleSheet(_FIELD)
        self.f_event_combo.addItem("— Chọn sự kiện —", None)
        for ev in get_loan_events():
            label = f"{ev['supplier']}  ({ev['reference_number']}, {ev['transaction_date']})"
            self.f_event_combo.addItem(label, ev["id"])
        self.f_event_combo.currentIndexChanged.connect(self._on_event_combo_changed)

        row1 = QHBoxLayout()
        row1.setSpacing(24)

        col_a = QFormLayout()
        col_a.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_a.setSpacing(10)
        col_a.addRow(lbl("Số Phiếu *"), self.f_ref)
        col_a.addRow(lbl("Kho Nhập *"), self.f_wh)

        col_b = QFormLayout()
        col_b.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_b.setSpacing(10)
        if self._subtype == "new":
            col_b.addRow(lbl("Đơn Vị Giao"), self.f_supplier)
        elif self._subtype == "unit_return":
            col_b.addRow(lbl("Đơn Vị Trả *"), self.f_from_wh)
        elif self._subtype == "event_return":
            col_b.addRow(lbl("Tên Sự Kiện *"), self.f_event_combo)
        elif self._subtype == "shared_return":
            tgl_w = QWidget()
            tgl_w.setFixedHeight(32)
            tgl_w.setStyleSheet("background: #f0f0f0; border-radius: 8px;")
            tgl_h = QHBoxLayout(tgl_w)
            tgl_h.setContentsMargins(3, 3, 3, 3)
            tgl_h.setSpacing(2)
            self._btn_unit_src  = QPushButton("Đơn Vị Trả Về")
            self._btn_event_src = QPushButton("Sự Kiện")
            self._btn_wh_src    = QPushButton("Từ Kho")
            for _b in (self._btn_unit_src, self._btn_event_src, self._btn_wh_src):
                _b.setFont(QFont(FONT, 11))
                _b.setFixedHeight(26)
                _b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                tgl_h.addWidget(_b)
            self._btn_unit_src.clicked.connect(lambda: self._set_shared_source("unit_return"))
            self._btn_event_src.clicked.connect(lambda: self._set_shared_source("event_return"))
            self._btn_wh_src.clicked.connect(lambda: self._set_shared_source("warehouse"))
            col_b.addRow(lbl("Nguồn Trả *"), tgl_w)
            self._lbl_unit_src  = lbl("Đơn Vị Trả *")
            self._lbl_event_src = lbl("Tên Sự Kiện *")
            self._lbl_wh_src    = lbl("Kho Nguồn *")
            col_b.addRow(self._lbl_unit_src, self.f_from_wh)
            col_b.addRow(self._lbl_event_src, self.f_event_combo)
            col_b.addRow(self._lbl_wh_src, self.f_src_wh)
            self.f_event_combo.setVisible(False)
            self._lbl_event_src.setVisible(False)
            self.f_src_wh.setVisible(False)
            self._lbl_wh_src.setVisible(False)
            self.f_src_wh.currentIndexChanged.connect(self._on_src_wh_changed)
            self._update_source_toggle_style()
        else:
            col_b.addRow(lbl(self._from_label), self.f_from_wh)
        col_b.addRow(lbl("Người giao"), self.f_person)

        col_c = QFormLayout()
        col_c.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        col_c.setSpacing(10)
        date_lbl = "Ngày Trả *" if self._subtype in ("unit_return", "event_return", "shared_return") else "Ngày Nhập *"
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

        # ── Line items ─────────────────────────────────────────────────────
        sec = QLabel("Danh Sách Hàng Nhập")
        sec.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        sec.setStyleSheet("color: #333;")
        root.addWidget(sec)
        root.addSpacing(6)

        show_price   = (self._subtype in ("new", "from_unit"))
        show_quality = (self._subtype == "from_unit")
        self._show_price   = show_price
        self._show_quality = show_quality

        # Column header strip
        hdr_w = QWidget()
        hdr_w.setStyleSheet("background: #f8f8f8; border-radius: 6px;")
        ch = QHBoxLayout(hdr_w)
        ch.setContentsMargins(6, 5, 6, 5)
        ch.setSpacing(6)
        col_defs = [("Mặt Hàng", 2, None), ("ĐVT", 0, 56), ("Số lượng", 0, 80)]
        if self._is_return_mode or self._subtype == "from_unit":
            col_defs += [("Còn lại", 0, 66)]
        if show_quality:
            col_defs += [("Mức HH", 0, 70)]
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

        self._btn_add = QPushButton("+ Thêm dòng hàng")
        self._btn_add.setFont(QFont(FONT, 11))
        self._btn_add.setFixedHeight(32)
        self._btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_add.setStyleSheet("""
            QPushButton { border: 1px dashed #bbb; border-radius: 6px;
                background: white; color: #555; }
            QPushButton:hover { border-color: #888; color: #111; background: #f8f8f8; }
        """)
        self._btn_add.clicked.connect(lambda: self._add_line())
        root.addWidget(self._btn_add)

        if show_price:
            tr = QHBoxLayout()
            tr.addStretch()
            tc = QLabel("Tổng tiền (không tính H4):" if self._subtype == "from_unit" else "Tổng tiền:")
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

        # Connect unit-combo signal for return subtypes
        if self._subtype in ("unit_return", "shared_return"):
            self.f_from_wh.currentIndexChanged.connect(self._on_unit_combo_changed)
        # Also connect warehouse-to combo (affects unit remaining lookup)
        if self._subtype == "unit_return":
            self.f_wh.currentIndexChanged.connect(self._on_unit_combo_changed)
        # from_unit: lọc mặt hàng theo đơn vị được chọn
        if self._subtype == "from_unit":
            self.f_from_wh.currentIndexChanged.connect(self._on_from_unit_changed)

        if receipt:
            self._fill(receipt)
        elif not self._is_return_mode:
            self._add_line()

    # ─────────────────────────────────────────────────────────────────────────

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

    def _update_source_toggle_style(self):
        if not self._btn_unit_src:
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
        self._btn_unit_src.setStyleSheet(
            active if self._shared_source == "unit_return" else inactive
        )
        self._btn_event_src.setStyleSheet(
            active if self._shared_source == "event_return" else inactive
        )
        if self._btn_wh_src:
            self._btn_wh_src.setStyleSheet(
                active if self._shared_source == "warehouse" else inactive
            )

    def _set_shared_source(self, source_type: str):
        self._shared_source = source_type
        is_unit  = (source_type == "unit_return")
        is_event = (source_type == "event_return")
        is_wh    = (source_type == "warehouse")
        if self._lbl_unit_src:
            self._lbl_unit_src.setVisible(is_unit)
            self.f_from_wh.setVisible(is_unit)
        if self._lbl_event_src:
            self._lbl_event_src.setVisible(is_event)
            self.f_event_combo.setVisible(is_event)
        if self._lbl_wh_src:
            self._lbl_wh_src.setVisible(is_wh)
            self.f_src_wh.setVisible(is_wh)
        self._update_source_toggle_style()
        if not self._editing:
            self._clear_rows()
            if is_wh:
                self._reload_wh_items()

    def _on_from_unit_changed(self, _):
        unit_wh_id = self.f_from_wh.currentData()
        self._unit_item_types = _get_unit_item_entries(unit_wh_id) if unit_wh_id else []
        if not self._editing:
            self._clear_rows()
            if self._unit_item_types:
                self._add_line()

    def _on_event_combo_changed(self, _):
        self._loan_tx_id = self.f_event_combo.currentData()
        if not self._editing:
            self._reload_return_items()

    def _on_unit_combo_changed(self, _):
        if not self._editing:
            self._reload_return_items()

    def _clear_rows(self):
        rows = []
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, LineItemRow):
                rows.append(w)
        for w in rows:
            self._rows_layout.removeWidget(w)
            w.deleteLater()

    def _reload_return_items(self):
        """Load loan items for the currently selected source and pre-populate rows."""
        loan_data = self._fetch_loan_item_data()
        if not loan_data:
            self._clear_rows()
            self._loan_item_types_filtered = []
            self._loan_max_qty_map = {}
            return

        loan_ids = {d["item_type_id"] for d in loan_data}
        self._loan_item_types_filtered = [it for it in self._item_types if it.id in loan_ids]
        self._loan_max_qty_map = {d["item_type_id"]: d["remaining_qty"] for d in loan_data}

        self._clear_rows()
        for d in loan_data:
            self._add_loan_item_row(d)

    def _fetch_loan_item_data(self) -> list[dict]:
        if self._subtype == "event_return":
            loan_tx_id = self.f_event_combo.currentData()
            if not loan_tx_id:
                return []
            return get_loan_items_remaining(loan_tx_id)
        elif self._subtype == "unit_return":
            unit_wh_id = self.f_from_wh.currentData()
            tong_wh_id = self.f_wh.currentData()
            if not unit_wh_id or not tong_wh_id:
                return []
            return get_unit_loan_items_remaining(unit_wh_id, tong_wh_id)
        elif self._subtype == "shared_return":
            if self._shared_source == "event_return":
                loan_tx_id = self.f_event_combo.currentData()
                if not loan_tx_id:
                    return []
                return get_loan_items_remaining(loan_tx_id)
            elif self._shared_source == "warehouse":
                return []
            else:
                unit_wh_id = self.f_from_wh.currentData()
                tong_wh_id = self.f_wh.currentData()
                if not unit_wh_id or not tong_wh_id:
                    return []
                return get_unit_loan_items_remaining(unit_wh_id, tong_wh_id)
        return []

    def _on_src_wh_changed(self, _):
        if not self._editing and self._shared_source == "warehouse":
            self._reload_wh_items()

    def _reload_wh_items(self):
        """Load available items from the source warehouse for shared_from_wh source."""
        import database
        wh_id = self.f_src_wh.currentData()
        self._clear_rows()
        if not wh_id:
            self._loan_item_types_filtered = []
            self._loan_max_qty_map = {}
            return
        conn = database.get_conn()
        rows = conn.execute("""
            SELECT it.id, SUM(i.quantity) AS total_qty
            FROM inventory i
            JOIN item_types it ON it.id = i.item_type_id
            WHERE i.warehouse_id=? AND i.is_shared=0 AND i.quantity > 0
            GROUP BY it.id HAVING total_qty > 0 ORDER BY it.name
        """, (wh_id,)).fetchall()
        self._loan_max_qty_map = {r["id"]: int(r["total_qty"]) for r in rows}
        item_ids = {r["id"] for r in rows}
        self._loan_item_types_filtered = [it for it in self._item_types if it.id in item_ids]
        if self._loan_item_types_filtered:
            self._add_line()

    def _add_loan_item_row(self, item_data: dict):
        """Add a pre-filled row locked to one loan item with capped quantity."""
        single_types = [it for it in self._item_types if it.id == item_data["item_type_id"]]
        row = LineItemRow(
            single_types,
            show_price=self._show_price,
            show_quality=self._show_quality,
            max_qty_map={item_data["item_type_id"]: item_data["remaining_qty"]},
            dynamic_price_by_category=(self._subtype == "from_unit"),
            parent=self,
        )
        if row.combo.count() > 0:
            row.combo.setCurrentIndex(0)
        row.spin_qty.setValue(item_data["remaining_qty"])
        row.removed.connect(self._remove_line)
        row.item_changed.connect(self._refresh_all_combos)
        if self._show_price:
            row.value_changed.connect(self._update_total)
        count = self._rows_layout.count()
        self._rows_layout.insertWidget(count - 1, row)

    def _refresh_all_combos(self):
        if self._subtype == "from_unit":
            return  # from_unit cho phép cùng id với category khác nhau
        used: set[int] = set()
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, LineItemRow):
                d = w.get_data()
                if d:
                    used.add(d.item_type_id)
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, LineItemRow):
                own_d = w.get_data()
                own_id = own_d.item_type_id if own_d else None
                w.refresh_available(used - ({own_id} if own_id else set()))

    def _add_line(self, line: ReceiptLine | None = None):
        if self._subtype == "from_unit" and not line and not self._unit_item_types:
            return  # chưa chọn đơn vị → không thêm row trống
        if self._subtype == "from_unit":
            item_types = self._unit_item_types if self._unit_item_types else self._item_types
        elif self._is_return_mode and self._loan_item_types_filtered:
            item_types = self._loan_item_types_filtered
        else:
            item_types = self._item_types
        max_map = self._loan_max_qty_map if self._is_return_mode and self._loan_max_qty_map else {}
        row = LineItemRow(item_types, show_price=self._show_price,
                          show_quality=self._show_quality,
                          max_qty_map=max_map or None,
                          dynamic_price_by_category=(self._subtype == "from_unit"),
                          parent=self)
        if line:
            row.fill(line)
        row.removed.connect(self._remove_line)
        row.item_changed.connect(self._refresh_all_combos)
        if self._show_price:
            row.value_changed.connect(self._update_total)
        count = self._rows_layout.count()
        self._rows_layout.insertWidget(count - 1, row)
        self._refresh_all_combos()
        if self._show_price:
            self._update_total()

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
            if isinstance(w, LineItemRow):
                d = w.get_data()
                if d:
                    total += d.quantity * d.unit_price
        self._form_total_lbl.setText(f"{total:,.0f} đ")

    def _fill(self, receipt: Receipt):
        self.f_ref.setText(receipt.reference_number)
        _set_combo_by_data(self.f_wh, receipt.to_warehouse_id)
        self.f_transport.setText(receipt.transporter)
        if self._subtype == "new":
            self.f_supplier.setText(receipt.supplier)
        elif self._subtype == "unit_return":
            _set_combo_by_data(self.f_from_wh, receipt.from_warehouse_id)
            self._load_edit_loan_data(receipt)
        elif self._subtype == "event_return":
            _set_combo_by_data(self.f_event_combo, receipt.loan_transaction_id)
            self._loan_tx_id = receipt.loan_transaction_id
            self._load_edit_loan_data(receipt)
        elif self._subtype == "shared_return":
            if receipt.from_warehouse_id:
                self._set_shared_source("unit_return")
                _set_combo_by_data(self.f_from_wh, receipt.from_warehouse_id)
            else:
                self._set_shared_source("event_return")
                _set_combo_by_data(self.f_event_combo, receipt.loan_transaction_id)
                self._loan_tx_id = receipt.loan_transaction_id
            self._load_edit_loan_data(receipt)
        else:
            _set_combo_by_data(self.f_from_wh, receipt.from_warehouse_id)
        self.f_person.setText(receipt.created_by)
        d = QDate.fromString(receipt.transaction_date, "yyyy-MM-dd")
        if d.isValid():
            self.f_date.setText(d.toString("dd/MM/yyyy"))
        self.f_notes.setPlainText(receipt.notes)
        for line in get_lines(receipt.id):
            self._add_line(line)

    def _load_edit_loan_data(self, receipt: Receipt):
        """Set loan item list and max quantities for edit mode.

        Max per item = (loaned - returned by other receipts) so the user can
        keep or reduce their existing quantities.  Items only in this receipt
        (remaining_qty = 0 after excluding it) are added with their saved qty
        as the ceiling so the row can still be displayed.
        """
        is_event = self._subtype == "event_return" or (
            self._subtype == "shared_return" and not receipt.from_warehouse_id
        )
        is_unit = self._subtype == "unit_return" or (
            self._subtype == "shared_return" and bool(receipt.from_warehouse_id)
        )

        data: list[dict] = []
        if is_event and receipt.loan_transaction_id:
            data = get_loan_items_remaining(
                receipt.loan_transaction_id, exclude_receipt_id=receipt.id
            )
        elif is_unit and receipt.from_warehouse_id and receipt.to_warehouse_id:
            data = get_unit_loan_items_remaining(
                receipt.from_warehouse_id, receipt.to_warehouse_id,
                exclude_receipt_id=receipt.id,
            )

        # Ensure items currently in this receipt appear even if remaining = 0
        data_ids = {d["item_type_id"] for d in data}
        for saved_line in get_lines(receipt.id):
            if saved_line.item_type_id not in data_ids:
                for it in self._item_types:
                    if it.id == saved_line.item_type_id:
                        data.append({
                            "item_type_id": saved_line.item_type_id,
                            "remaining_qty": saved_line.quantity,
                        })
                        break

        if data:
            self._loan_max_qty_map = {d["item_type_id"]: d["remaining_qty"] for d in data}
            loan_ids = {d["item_type_id"] for d in data}
            self._loan_item_types_filtered = [
                it for it in self._item_types if it.id in loan_ids
            ]

    def _do_save(self) -> "Receipt | None":
        ref = self.f_ref.text().strip()
        if not ref:
            self._err("Vui lòng nhập Số Phiếu."); return None
        _d = QDate.fromString(self.f_date.text(), "dd/MM/yyyy")
        if not _d.isValid():
            self._err("Ngày không hợp lệ. Vui lòng nhập đúng định dạng dd/MM/yyyy."); return None
        wh_id = self.f_wh.currentData()
        if not wh_id:
            self._err("Vui lòng chọn Kho Nhập."); return None
        wh_name = self.f_wh.currentText()

        from_wh_id = None
        supplier = ""
        transporter = self.f_transport.text().strip()
        loan_tx_id: int | None = None
        if self._subtype == "new":
            supplier = self.f_supplier.text().strip()
        elif self._subtype == "unit_return":
            from_wh_id = self.f_from_wh.currentData()
            if not from_wh_id:
                self._err("Vui lòng chọn Đơn Vị Trả."); return None
        elif self._subtype == "event_return":
            loan_tx_id = self.f_event_combo.currentData()
            if not loan_tx_id:
                self._err("Vui lòng chọn Sự Kiện."); return None
            combo_text = self.f_event_combo.currentText()
            supplier = combo_text.split("  (")[0] if "  (" in combo_text else combo_text
        elif self._subtype == "shared_return":
            if self._shared_source == "unit_return":
                from_wh_id = self.f_from_wh.currentData()
                if not from_wh_id:
                    self._err("Vui lòng chọn Đơn Vị Trả."); return None
            elif self._shared_source == "warehouse":
                from_wh_id = self.f_src_wh.currentData()
                if not from_wh_id:
                    self._err("Vui lòng chọn Kho Nguồn."); return None
            else:
                loan_tx_id = self.f_event_combo.currentData()
                if not loan_tx_id:
                    self._err("Vui lòng chọn Sự Kiện."); return None
                combo_text = self.f_event_combo.currentText()
                supplier = combo_text.split("  (")[0] if "  (" in combo_text else combo_text
        else:
            from_wh_id = self.f_from_wh.currentData()
            if not from_wh_id:
                self._err("Vui lòng chọn Đơn Vị Giao."); return None

        lines: list[ReceiptLine] = []
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, LineItemRow):
                d = w.get_data()
                if d:
                    lines.append(d)
        if not lines:
            self._err("Vui lòng thêm ít nhất một mặt hàng."); return None

        # Separate DC lines (sẽ tạo TRA riêng) và regular/H4 lines
        dc_lines    = [l for l in lines if l.is_shared] if self._subtype == "from_unit" else []
        nhap_lines  = [l for l in lines if not l.is_shared]

        if self._subtype == "from_unit" and not nhap_lines and not dc_lines:
            self._err("Vui lòng thêm ít nhất một mặt hàng."); return None
        if self._subtype == "from_unit" and not nhap_lines and dc_lines:
            # DC-only: không tạo NHAP_KHO, chỉ tạo TRA
            pass

        exclude = self._editing.id if self._editing else None
        if ref_exists(ref, exclude):
            self._err(f"Số Phiếu '{ref}' đã tồn tại."); return None

        date_str = QDate.fromString(self.f_date.text(), "dd/MM/yyyy").toString("yyyy-MM-dd")
        receipt = Receipt(
            id=self._editing.id if self._editing else None,
            reference_number=ref,
            to_warehouse_id=wh_id,
            to_warehouse_name=wh_name,
            from_warehouse_id=from_wh_id,
            transaction_date=date_str,
            supplier=supplier,
            created_by=self.f_person.text().strip(),
            transporter=transporter,
            notes=self.f_notes.toPlainText().strip(),
            loan_transaction_id=loan_tx_id,
            lines=nhap_lines if self._subtype == "from_unit" else lines,
        )
        if self._subtype in ("unit_return", "event_return", "shared_return"):
            if self._subtype == "shared_return" and self._shared_source == "warehouse":
                receipt.tx_type = "NHAP_DC_TU_KHO"
            else:
                receipt.tx_type = "TRA"

        if self._subtype == "from_unit" and not nhap_lines:
            # DC-only: bỏ qua NHAP_KHO, tạo TRA cho DC rồi trả receipt giả
            if not self._editing and dc_lines:
                self._auto_create_tra_dc(ref, wh_id, from_wh_id, date_str,
                                         self.f_person.text().strip(),
                                         transporter, self.f_notes.toPlainText().strip(),
                                         dc_lines)
            return receipt  # receipt.lines rỗng nhưng đủ để close dialog
        elif self._editing:
            update(receipt)
        else:
            insert(receipt)
            if not self._editing and dc_lines:
                self._auto_create_tra_dc(ref, wh_id, from_wh_id, date_str,
                                         self.f_person.text().strip(),
                                         transporter, self.f_notes.toPlainText().strip(),
                                         dc_lines)
        return receipt

    def _auto_create_tra_dc(self, base_ref, to_wh_id, from_wh_id, date_str,
                            created_by, transporter, notes, dc_lines):
        """Tự tạo phiếu TRA (unit_return) cho các dòng hàng DC trong from_unit."""
        dc_ref = f"{base_ref}-DC"
        n = 2
        while ref_exists(dc_ref):
            dc_ref = f"{base_ref}-DC{n}"
            n += 1
        tra = Receipt(
            id=None,
            reference_number=dc_ref,
            to_warehouse_id=to_wh_id,
            to_warehouse_name="",
            from_warehouse_id=from_wh_id,
            transaction_date=date_str,
            supplier="",
            created_by=created_by,
            transporter=transporter,
            notes=notes,
            lines=dc_lines,
        )
        tra.tx_type = "TRA"
        insert(tra)

    def _save(self):
        receipt = self._do_save()
        if receipt is not None:
            self.accept()

    def _on_export_phieu(self):
        receipt = self._do_save()
        if receipt is None:
            return
        from ui.word_export import export_nhap_kho_excel
        export_nhap_kho_excel(self, receipt, receipt.lines)
        self.accept()

    def _err(self, msg: str):
        QMessageBox.warning(self, "Lỗi", msg)


def _set_combo_by_data(combo: QComboBox, value):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
