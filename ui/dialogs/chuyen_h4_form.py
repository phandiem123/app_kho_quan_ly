from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QPushButton, QComboBox, QFrame, QWidget, QDateEdit, QScrollArea,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
import database

FONT = "Segoe UI"

_FIELD = """
    QLineEdit, QComboBox, QDateEdit {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 10px; background: white; font-size: 12px;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color: #888; }
    QComboBox::drop-down { border: none; width: 24px; }
    QDateEdit::drop-down { border: none; width: 24px; }
"""
_SPIN = """
    QSpinBox {
        border: 1px solid #ddd; border-radius: 6px;
        padding: 0 8px; background: white; font-size: 12px;
    }
    QSpinBox:focus { border-color: #888; }
    QSpinBox::up-button, QSpinBox::down-button { width: 18px; }
"""


class _LineRow(QWidget):
    remove_requested = pyqtSignal(object)

    def __init__(self, items: list[dict], wh_id: int, parent=None):
        super().__init__(parent)
        self._items = items
        self._wh_id = wh_id
        self._build()

    def _build(self):
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(6)
        self.setStyleSheet("background: transparent;")

        self.combo_item = QComboBox()
        self.combo_item.setFixedHeight(34)
        self.combo_item.setMinimumWidth(180)
        self.combo_item.setStyleSheet(_FIELD)
        for it in self._items:
            self.combo_item.addItem(it["name"], it)
        self.combo_item.currentIndexChanged.connect(self._refresh_available)

        self.lbl_avail = QLabel("0")
        self.lbl_avail.setFixedSize(70, 34)
        self.lbl_avail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_avail.setFont(QFont(FONT, 11))
        self.lbl_avail.setStyleSheet(
            "color: #555; background: #f5f5f5; border-radius: 5px;"
        )

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 999999)
        self.spin_qty.setValue(1)
        self.spin_qty.setFixedSize(90, 34)
        self.spin_qty.setStyleSheet(_SPIN)

        btn_rm = QPushButton("✕")
        btn_rm.setFixedSize(30, 30)
        btn_rm.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_rm.setStyleSheet("""
            QPushButton { border: 1px solid #e0e0e0; border-radius: 6px;
                background: white; color: #aaa; font-size: 11px; }
            QPushButton:hover { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
        """)
        btn_rm.clicked.connect(lambda: self.remove_requested.emit(self))

        h.addWidget(self.combo_item, 1)
        h.addWidget(self.lbl_avail)
        h.addWidget(self.spin_qty)
        h.addWidget(btn_rm)

        self._refresh_available()

    def _refresh_available(self):
        it = self.combo_item.currentData()
        if not it or not self._wh_id:
            self.lbl_avail.setText("0")
            return
        conn = database.get_conn()
        row = conn.execute("""
            SELECT COALESCE(SUM(quantity), 0) AS qty
            FROM inventory
            WHERE warehouse_id=? AND item_type_id=? AND quality_level='H3' AND is_shared=1
        """, (self._wh_id, it["id"])).fetchone()
        avail = row["qty"] if row else 0
        self.lbl_avail.setText(str(avail))
        self.spin_qty.setMaximum(max(1, avail) if avail > 0 else 1)

    def get_line(self) -> dict:
        it = self.combo_item.currentData()
        return {
            "item_type_id": it["id"],
            "item_name": it["name"],
            "from_ql": "H3",
            "quantity": self.spin_qty.value(),
            "available": int(self.lbl_avail.text()),
        }


class ChuyenH4FormDialog(QDialog):
    def __init__(self, parent=None, tx_id: int | None = None, wh_id: int | None = None):
        super().__init__(parent)
        self._tx_id = tx_id
        self._init_wh_id = wh_id
        title = "Sửa – Phiếu Chuyển Sang H4" if tx_id else "Phiếu Chuyển Sang H4"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(680)
        self.setStyleSheet("QDialog { background: white; }")
        self._line_rows: list[_LineRow] = []
        self._items: list[dict] = []
        self._wh_id: int | None = None
        self._build()
        self._load_warehouses()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(0)

        title = QLabel("Phiếu Chuyển Sang H4")
        title.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #111;")
        root.addWidget(title)
        root.addSpacing(4)

        sub = QLabel("Chuyển hàng dùng chung từ tồn kho sang H4 để chờ thanh lý")
        sub.setFont(QFont(FONT, 11))
        sub.setStyleSheet("color: #888;")
        root.addWidget(sub)
        root.addSpacing(16)
        root.addWidget(self._hsep())
        root.addSpacing(16)

        # ── Header fields ─────────────────────────────────────────────────
        frow = QHBoxLayout()
        frow.setSpacing(14)

        kho_col = QVBoxLayout()
        kho_col.setSpacing(4)
        kho_col.addWidget(self._flbl("Kho"))
        self._wh_combo = QComboBox()
        self._wh_combo.setFixedHeight(36)
        self._wh_combo.setStyleSheet(_FIELD)
        self._wh_combo.currentIndexChanged.connect(self._on_wh_changed)
        kho_col.addWidget(self._wh_combo)
        frow.addLayout(kho_col, 2)

        ref_col = QVBoxLayout()
        ref_col.setSpacing(4)
        ref_col.addWidget(self._flbl("Số phiếu"))
        self._ref = QLineEdit()
        self._ref.setFixedHeight(36)
        self._ref.setStyleSheet(_FIELD)
        ref_col.addWidget(self._ref)
        frow.addLayout(ref_col, 1)

        date_col = QVBoxLayout()
        date_col.setSpacing(4)
        date_col.addWidget(self._flbl("Ngày"))
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setFixedHeight(36)
        self._date.setDisplayFormat("dd/MM/yyyy")
        self._date.setStyleSheet(_FIELD)
        date_col.addWidget(self._date)
        frow.addLayout(date_col, 1)

        root.addLayout(frow)
        root.addSpacing(20)

        # ── Column headers ────────────────────────────────────────────────
        ch = QHBoxLayout()
        ch.setContentsMargins(0, 0, 0, 4)
        ch.setSpacing(6)
        for txt, stretch, fixw in [
            ("Mặt hàng", 1, None),
            ("Tồn kho H3", 0, 70),
            ("Số lượng", 0, 90),
            ("", 0, 30),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont(FONT, 10))
            lbl.setStyleSheet("color: #999;")
            if fixw:
                lbl.setFixedWidth(fixw)
            if stretch:
                ch.addWidget(lbl, 1)
            else:
                ch.addWidget(lbl)
        root.addLayout(ch)

        # ── Lines scroll ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #efefef; border-radius: 8px; background: white; }"
        )
        scroll.setFixedHeight(200)

        self._lines_w = QWidget()
        self._lines_w.setStyleSheet("background: white;")
        self._lines_v = QVBoxLayout(self._lines_w)
        self._lines_v.setContentsMargins(8, 6, 8, 6)
        self._lines_v.setSpacing(0)
        self._lines_v.addStretch()
        scroll.setWidget(self._lines_w)
        root.addWidget(scroll)
        root.addSpacing(8)

        btn_add = QPushButton("+ Thêm mặt hàng")
        btn_add.setFixedHeight(32)
        btn_add.setFont(QFont(FONT, 11))
        btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add.setStyleSheet("""
            QPushButton { border: 1px solid #d0d0d0; border-radius: 7px;
                background: white; color: #555; }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_add.clicked.connect(self._add_line)
        root.addWidget(btn_add)
        root.addSpacing(20)
        root.addWidget(self._hsep())
        root.addSpacing(14)

        # ── Action buttons ────────────────────────────────────────────────
        brow = QHBoxLayout()
        brow.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedSize(100, 38)
        btn_cancel.setFont(QFont(FONT, 12))
        btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cancel.setStyleSheet("""
            QPushButton { border: 1px solid #e0e0e0; border-radius: 8px;
                background: white; color: #555; }
            QPushButton:hover { background: #f5f5f5; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Lưu Phiếu")
        btn_save.setFixedSize(130, 38)
        btn_save.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save.setStyleSheet("""
            QPushButton { border: none; border-radius: 8px;
                background: #c0392b; color: white; }
            QPushButton:hover { background: #a93226; }
            QPushButton:pressed { background: #922b21; }
        """)
        btn_save.clicked.connect(self._on_save)

        brow.addWidget(btn_cancel)
        brow.addSpacing(10)
        brow.addWidget(btn_save)
        root.addLayout(brow)

    def _flbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(FONT, 10))
        lbl.setStyleSheet("color: #888;")
        return lbl

    def _hsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("QFrame { color: #f0f0f0; }")
        return f

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_warehouses(self):
        conn = database.get_conn()
        rows = conn.execute(
            "SELECT id, code, name FROM warehouses WHERE type='TONG' AND is_active=1 ORDER BY name"
        ).fetchall()
        self._wh_combo.blockSignals(True)
        self._wh_combo.clear()
        for r in rows:
            self._wh_combo.addItem(r["name"], r["id"])
        self._wh_combo.blockSignals(False)
        self._load_items()

        if self._tx_id:
            tx = conn.execute(
                "SELECT to_warehouse_id, reference_number, transaction_date"
                " FROM transactions WHERE id=?", (self._tx_id,)
            ).fetchone()
            if tx:
                for i in range(self._wh_combo.count()):
                    if self._wh_combo.itemData(i) == tx["to_warehouse_id"]:
                        self._wh_combo.setCurrentIndex(i)
                        break
                self._wh_id = tx["to_warehouse_id"]
                self._ref.setText(tx["reference_number"] or "")
                if tx["transaction_date"]:
                    from PyQt6.QtCore import QDate
                    self._date.setDate(QDate.fromString(tx["transaction_date"], "yyyy-MM-dd"))
                tl_rows = conn.execute(
                    "SELECT item_type_id, quantity FROM transaction_lines"
                    " WHERE transaction_id=?", (self._tx_id,)
                ).fetchall()
                for tl in tl_rows:
                    row = _LineRow(self._items, self._wh_id, self._lines_w)
                    row.remove_requested.connect(self._remove_line)
                    for j in range(row.combo_item.count()):
                        if row.combo_item.itemData(j)["id"] == tl["item_type_id"]:
                            row.combo_item.setCurrentIndex(j)
                            break
                    row.spin_qty.setValue(tl["quantity"])
                    self._line_rows.append(row)
                    self._lines_v.insertWidget(self._lines_v.count() - 1, row)
        else:
            # pre-select the warehouse passed from the caller (if any)
            target = self._init_wh_id
            self._wh_combo.blockSignals(True)
            if target:
                for i in range(self._wh_combo.count()):
                    if self._wh_combo.itemData(i) == target:
                        self._wh_combo.setCurrentIndex(i)
                        break
            self._wh_combo.blockSignals(False)
            if self._wh_combo.count():
                self._wh_id = self._wh_combo.currentData()
            self._add_line()

    def _load_items(self):
        conn = database.get_conn()
        rows = conn.execute(
            "SELECT id, code, name FROM item_types WHERE is_active=1 ORDER BY name"
        ).fetchall()
        self._items = [{"id": r["id"], "code": r["code"], "name": r["name"]} for r in rows]

    def _on_wh_changed(self, idx: int):
        self._wh_id = self._wh_combo.itemData(idx)
        for row in list(self._line_rows):
            self._lines_v.removeWidget(row)
            row.setParent(None)
        self._line_rows.clear()
        self._add_line()

    def _add_line(self):
        if not self._items:
            return
        row = _LineRow(self._items, self._wh_id, self._lines_w)
        row.remove_requested.connect(self._remove_line)
        self._line_rows.append(row)
        self._lines_v.insertWidget(self._lines_v.count() - 1, row)

    def _remove_line(self, row: _LineRow):
        if row in self._line_rows:
            self._line_rows.remove(row)
        self._lines_v.removeWidget(row)
        row.setParent(None)

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_save(self):
        if not self._wh_id:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn kho.")
            return
        if not self._line_rows:
            QMessageBox.warning(self, "Lỗi", "Vui lòng thêm ít nhất một mặt hàng.")
            return

        lines = [row.get_line() for row in self._line_rows]
        conn = database.get_conn()

        # For edit mode: compute old quantities per item to adjust available check
        old_qty_by_item: dict[int, int] = {}
        old_wh_id = self._wh_id
        if self._tx_id:
            old_tx = conn.execute(
                "SELECT to_warehouse_id FROM transactions WHERE id=?", (self._tx_id,)
            ).fetchone()
            if old_tx:
                old_wh_id = old_tx["to_warehouse_id"]
            for ol in conn.execute(
                "SELECT item_type_id, quantity FROM transaction_lines WHERE transaction_id=?",
                (self._tx_id,)
            ).fetchall():
                old_qty_by_item[ol["item_type_id"]] = (
                    old_qty_by_item.get(ol["item_type_id"], 0) + ol["quantity"]
                )

        for line in lines:
            old_bonus = old_qty_by_item.get(line["item_type_id"], 0) if self._tx_id else 0
            effective_avail = line["available"] + old_bonus
            if effective_avail <= 0:
                QMessageBox.warning(
                    self, "Lỗi",
                    f"Mặt hàng '{line['item_name']}' ({line['from_ql']}) "
                    f"không còn tồn kho."
                )
                return
            if line["quantity"] > effective_avail:
                QMessageBox.warning(
                    self, "Lỗi",
                    f"Mặt hàng '{line['item_name']}' ({line['from_ql']}): "
                    f"Số lượng chuyển ({line['quantity']}) vượt quá "
                    f"tồn kho ({effective_avail})."
                )
                return

        ref = self._ref.text().strip() or None
        tx_date = self._date.date().toString("yyyy-MM-dd")

        if self._tx_id:
            # rollback old inventory changes
            for ol in conn.execute(
                "SELECT item_type_id, quality_level_from, quantity"
                " FROM transaction_lines WHERE transaction_id=?", (self._tx_id,)
            ).fetchall():
                conn.execute("""
                    UPDATE inventory SET quantity=quantity+?
                    WHERE warehouse_id=? AND item_type_id=? AND quality_level=? AND is_shared=1
                """, (ol["quantity"], old_wh_id, ol["item_type_id"], ol["quality_level_from"]))
                conn.execute("""
                    UPDATE inventory SET quantity=MAX(0, quantity-?)
                    WHERE warehouse_id=? AND item_type_id=? AND quality_level='H4' AND is_shared=1
                """, (ol["quantity"], old_wh_id, ol["item_type_id"]))
            conn.execute("DELETE FROM transaction_lines WHERE transaction_id=?", (self._tx_id,))
            conn.execute("""
                UPDATE transactions
                SET reference_number=?, to_warehouse_id=?, transaction_date=?
                WHERE id=?
            """, (ref, self._wh_id, tx_date, self._tx_id))
            tx_id = self._tx_id
        else:
            cur = conn.execute("""
                INSERT INTO transactions
                    (type, reference_number, to_warehouse_id, transaction_date, notes)
                VALUES ('CHUYEN_H4', ?, ?, ?, '')
            """, (ref, self._wh_id, tx_date))
            tx_id = cur.lastrowid

        for line in lines:
            conn.execute("""
                INSERT INTO transaction_lines
                    (transaction_id, item_type_id, quality_level_from,
                     quality_level_to, quantity)
                VALUES (?, ?, ?, 'H4', ?)
            """, (tx_id, line["item_type_id"], line["from_ql"], line["quantity"]))

            conn.execute("""
                UPDATE inventory SET quantity = MAX(0, quantity - ?)
                WHERE warehouse_id=? AND item_type_id=? AND quality_level=? AND is_shared=1
            """, (line["quantity"], self._wh_id, line["item_type_id"], line["from_ql"]))

            h4_row = conn.execute("""
                SELECT id FROM inventory
                WHERE warehouse_id=? AND item_type_id=? AND quality_level='H4' AND is_shared=1
                LIMIT 1
            """, (self._wh_id, line["item_type_id"])).fetchone()
            if h4_row:
                conn.execute(
                    "UPDATE inventory SET quantity=quantity+? WHERE id=?",
                    (line["quantity"], h4_row["id"])
                )
            else:
                conn.execute("""
                    INSERT INTO inventory
                        (warehouse_id, item_type_id, quality_level, quantity, is_shared)
                    VALUES (?, ?, 'H4', ?, 1)
                """, (self._wh_id, line["item_type_id"], line["quantity"]))

        conn.commit()
        self.accept()
