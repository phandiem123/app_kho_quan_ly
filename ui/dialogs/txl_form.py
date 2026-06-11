"""Dialog tạo Phiếu Thanh Xử Lý."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QSpinBox, QTextEdit, QPushButton,
    QComboBox, QMessageBox, QFrame, QWidget, QDateEdit,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QCursor
from database.warehouses import get_all as wh_get_all
from database.txl import H4Item, get_h4_inventory, create

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


class _ItemRow(QWidget):
    def __init__(self, item: H4Item, show_months: bool, parent=None):
        super().__init__(parent)
        self._item = item
        self.setStyleSheet("background: transparent;")

        h = QHBoxLayout(self)
        h.setContentsMargins(4, 3, 4, 3)
        h.setSpacing(8)

        self.chk = QCheckBox()
        self.chk.toggled.connect(self._on_toggle)
        h.addWidget(self.chk)

        wh = QLabel(item.warehouse_name)
        wh.setFont(QFont(FONT, 11))
        wh.setFixedWidth(130)
        wh.setStyleSheet("color: #444;")
        h.addWidget(wh)

        name = QLabel(item.item_name)
        name.setFont(QFont(FONT, 11))
        name.setMinimumWidth(180)
        h.addWidget(name, 1)

        uom = QLabel(item.unit_of_measure)
        uom.setFont(QFont(FONT, 11))
        uom.setFixedWidth(48)
        uom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        uom.setStyleSheet("color: #666;")
        h.addWidget(uom)

        self.lbl_max = QLabel(f"/{item.quantity}")
        self.lbl_max.setFont(QFont(FONT, 11))
        self.lbl_max.setStyleSheet("color: #aaa;")

        self.spin = QSpinBox()
        self.spin.setRange(1, item.quantity)
        self.spin.setValue(item.quantity)
        self.spin.setFixedWidth(72)
        self.spin.setFixedHeight(30)
        self.spin.setStyleSheet(_SPIN)
        self.spin.setEnabled(False)
        h.addWidget(self.spin)
        h.addWidget(self.lbl_max)

        if show_months and item.months_at_unit is not None:
            mo = QLabel(f"{item.months_at_unit // 12} năm")
            mo.setFont(QFont(FONT, 10))
            mo.setFixedWidth(70)
            mo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mo.setStyleSheet(
                "color: #c0392b; background: #fdecea; border-radius: 4px; padding: 1px 4px;"
                if item.months_at_unit >= 24
                else "color: #666;"
            )
            h.addWidget(mo)

        if item.lot_number:
            lot = QLabel(item.lot_number)
            lot.setFont(QFont(FONT, 10))
            lot.setFixedWidth(80)
            lot.setStyleSheet("color: #888;")
            h.addWidget(lot)

    def _on_toggle(self, checked: bool):
        self.spin.setEnabled(checked)

    def is_checked(self) -> bool:
        return self.chk.isChecked()

    def get_entry(self) -> tuple[int, int, int, str]:
        """(inventory_id, item_type_id, qty, notes)"""
        return (self._item.inventory_id, self._item.item_type_id,
                self.spin.value(), "")


class TxlFormDialog(QDialog):
    def __init__(self, wh_type: str, parent=None):
        super().__init__(parent)
        self._wh_type = wh_type
        self._rows: list[_ItemRow] = []
        title = "Tại Kho Tổng" if wh_type == "TONG" else "Tại Đơn Vị"
        self.setWindowTitle(f"Tạo Phiếu Thanh Xử Lý – {title}")
        self.setMinimumSize(820, 620)
        self.setStyleSheet("background: white;")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        title = QLabel("Tạo Phiếu Thanh Xử Lý")
        title.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        root.addWidget(title)

        # ── Header fields ──────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(14)

        self._wh_combo = QComboBox()
        self._wh_combo.setFixedHeight(34)
        self._wh_combo.setStyleSheet(_FIELD)
        for wh in wh_get_all(wh_type=self._wh_type):
            self._wh_combo.addItem(wh.name, wh.id)
        self._wh_combo.currentIndexChanged.connect(self._reload_items)
        form.addRow(_lbl("Kho / ĐV:"), self._wh_combo)

        row_top = QHBoxLayout()
        self._ref = QLineEdit()
        self._ref.setFixedHeight(34)
        self._ref.setPlaceholderText("Số phiếu...")
        self._ref.setStyleSheet(_FIELD)

        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd/MM/yyyy")
        self._date.setFixedSize(140, 34)
        self._date.setStyleSheet(_FIELD)

        self._created_by = QLineEdit()
        self._created_by.setFixedHeight(34)
        self._created_by.setPlaceholderText("Người lập phiếu...")
        self._created_by.setStyleSheet(_FIELD)

        row_top.addWidget(self._ref, 2)
        row_top.addWidget(self._date)
        row_top.addWidget(self._created_by, 2)
        form.addRow(_lbl("Số phiếu / Ngày / Người lập:"), row_top)

        self._notes = QTextEdit()
        self._notes.setFixedHeight(56)
        self._notes.setPlaceholderText("Ghi chú...")
        self._notes.setStyleSheet(_FIELD + "QTextEdit { padding: 6px 10px; }")
        form.addRow(_lbl("Nội dung:"), self._notes)
        root.addLayout(form)

        # ── Item list ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_items = QLabel("Danh Sách Hàng H4")
        lbl_items.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        hdr.addWidget(lbl_items)
        hdr.addStretch()

        self._lbl_count = QLabel("")
        self._lbl_count.setFont(QFont(FONT, 11))
        self._lbl_count.setStyleSheet("color: #888;")
        hdr.addWidget(self._lbl_count)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #efefef; border: none;")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: white; }")

        self._item_container = QWidget()
        self._item_container.setStyleSheet("background: white;")
        self._item_v = QVBoxLayout(self._item_container)
        self._item_v.setContentsMargins(0, 0, 0, 0)
        self._item_v.setSpacing(2)
        scroll.setWidget(self._item_container)
        root.addWidget(scroll, 1)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFont(QFont(FONT, 12))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet("""
            QPushButton { border: 1px solid #ddd; border-radius: 7px;
                padding: 0 20px; background: white; color: #333; }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Lưu Phiếu TXL")
        btn_ok.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_ok.setFixedHeight(36)
        btn_ok.setStyleSheet("""
            QPushButton { border: none; border-radius: 7px;
                padding: 0 24px; background: #c0392b; color: white; }
            QPushButton:hover { background: #a93226; }
        """)
        btn_ok.clicked.connect(self._submit)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

        self._reload_items()

    def _reload_items(self):
        wh_id = self._wh_combo.currentData()
        all_items = get_h4_inventory(self._wh_type)
        items = [i for i in all_items if i.warehouse_id == wh_id] if wh_id else all_items

        # clear old
        while self._item_v.count():
            w = self._item_v.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._rows.clear()

        show_months = (self._wh_type == "DON_VI")

        if not items:
            no = QLabel("Không có hàng H4 tại kho/đơn vị này.")
            no.setFont(QFont(FONT, 11))
            no.setStyleSheet("color: #aaa; padding: 12px 0;")
            self._item_v.addWidget(no)
            self._lbl_count.setText("0 lô")
        else:
            for item in items:
                row = _ItemRow(item, show_months)
                self._rows.append(row)
                self._item_v.addWidget(row)
            self._item_v.addStretch()
            self._lbl_count.setText(f"{len(items)} lô")

    def _submit(self):
        wh_id = self._wh_combo.currentData()
        if not wh_id:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn kho/đơn vị.")
            return

        selected = [r.get_entry() for r in self._rows if r.is_checked()]
        if not selected:
            QMessageBox.warning(self, "Chưa chọn hàng",
                                "Vui lòng tick chọn ít nhất một lô hàng để xử lý.")
            return

        ref = self._ref.text().strip()
        date = self._date.date().toString("yyyy-MM-dd")
        notes = self._notes.toPlainText().strip()
        created_by = self._created_by.text().strip()

        create(wh_id, ref, date, notes, created_by, selected)
        QMessageBox.information(
            self, "Thành công",
            f"Đã lưu phiếu TXL với {len(selected)} lô hàng."
        )
        self.accept()


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont(FONT, 12))
    return l
