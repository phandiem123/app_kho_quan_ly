"""Trang Thanh Xử Lý – dùng chung cho Tại Kho và Tại Đơn Vị."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QComboBox, QMessageBox, QMenu, QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor, QAction
from database.txl import get_h4_inventory, get_all, get_lines, delete, TxlRecord

FONT = "Segoe UI"

_TABLE_STYLE = """
    QTableWidget { border: none; background: white; outline: 0; gridline-color: transparent; }
    QHeaderView::section {
        background: white; color: #aaa; font-size: 12px;
        border: none; border-bottom: 1px solid #efefef;
        padding: 8px 12px; font-weight: normal;
    }
    QTableWidget::item {
        padding: 0 12px; border: none;
        color: #111; font-size: 13px;
    }
    QTableWidget::item:selected { background: #f5f7fa; color: #111; }
"""
_BTN_DARK = """
    QPushButton { border: none; border-radius: 7px; padding: 0 16px;
        background: #111; color: white; font-size: 12px; font-weight: 600; }
    QPushButton:hover { background: #333; }
"""
_BTN_RED = """
    QPushButton { border: none; border-radius: 7px; padding: 0 16px;
        background: #c0392b; color: white; font-size: 12px; font-weight: 600; }
    QPushButton:hover { background: #a93226; }
"""


# ── Detail panel (lịch sử) ────────────────────────────────────────────────────

class _DetailPanel(QWidget):
    def __init__(self, rec: TxlRecord, lines, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            _DetailPanel { background: #f5f5f5; }
            QLabel { background: transparent; border: none; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 12, 28, 12)
        root.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setHorizontalSpacing(24)

        def pair(lbl, val):
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)
            l = QLabel(lbl + ":")
            l.setFont(QFont(FONT, 11))
            l.setFixedWidth(80)
            l.setStyleSheet("color: #888;")
            v = QLabel(val or "—")
            v.setFont(QFont(FONT, 11, QFont.Weight.Medium))
            v.setStyleSheet("color: #111;")
            hl.addWidget(l)
            hl.addWidget(v, 1)
            return w

        grid.addWidget(pair("Số Phiếu", rec.reference_number), 0, 0)
        grid.addWidget(pair("Kho / ĐV", rec.warehouse_name), 0, 1)
        grid.addWidget(pair("Người Lập", rec.created_by), 0, 2)
        grid.addWidget(pair("Nội Dung", rec.notes), 1, 0, 1, 3)
        root.addLayout(grid)

        sub = QTableWidget(0, 4)
        sub.setHorizontalHeaderLabels(["STT", "Tên Hàng", "ĐVT", "Số Lượng"])
        sub.verticalHeader().setVisible(False)
        sub.setShowGrid(False)
        sub.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sub.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        sub.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        sub.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sub.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sub.setStyleSheet("""
            QTableWidget { border: none; background: #f0f0f0;
                outline: 0; border-radius: 6px; }
            QHeaderView::section { background: #e8e8e8; color: #777; font-size: 10px;
                border: none; padding: 4px 8px; }
            QTableWidget::item { padding: 4px 8px; color: #111;
                font-size: 12px; border: none; }
        """)
        sh = sub.horizontalHeader()
        for i, (mode, w) in enumerate([
            (QHeaderView.ResizeMode.Fixed, 44),
            (QHeaderView.ResizeMode.Stretch, None),
            (QHeaderView.ResizeMode.Fixed, 60),
            (QHeaderView.ResizeMode.Fixed, 80),
        ]):
            sh.setSectionResizeMode(i, mode)
            if w:
                sub.setColumnWidth(i, w)

        for i, line in enumerate(lines):
            r = sub.rowCount()
            sub.insertRow(r)
            sub.setRowHeight(r, 36)
            for c, val in enumerate([
                str(i + 1), line.item_name,
                line.unit_of_measure, str(line.quantity),
            ]):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 11))
                if c in (0, 2, 3):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                sub.setItem(r, c, cell)

        sub.setFixedHeight(34 + max(1, len(lines)) * 36)
        root.addWidget(sub)


# ── Main page ─────────────────────────────────────────────────────────────────

class TxlPage(QWidget):
    """
    wh_type = 'TONG'    → Thanh Xử Lý tại Kho Tổng
    wh_type = 'DON_VI'  → Thanh Xử Lý tại Đơn Vị
    """

    def __init__(self, wh_type: str):
        super().__init__()
        self._wh_type = wh_type
        self._cache: list[TxlRecord] = []
        self._expanded_row: int | None = None
        self._h4_cols = _h4_columns(wh_type)
        self._history_cols = ["STT", "Số Phiếu", "Kho / ĐV", "Số M.Hàng",
                               "Ngày TXL", "Người Lập", "Nội Dung", ""]
        self.setStyleSheet("TxlPage { background: #fafafa; }")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 24)
        root.setSpacing(0)

        # ── Tab bar ────────────────────────────────────────────────────────
        top = QHBoxLayout()
        tab_container = QWidget()
        tab_container.setFixedHeight(36)
        tab_container.setStyleSheet("background: #f0f0f0; border-radius: 9px;")
        tab_h = QHBoxLayout(tab_container)
        tab_h.setContentsMargins(3, 3, 3, 3)
        tab_h.setSpacing(2)
        self._tabs: list[QPushButton] = []
        for i, txt in enumerate(["Tồn H4", "Lịch Sử TXL"]):
            btn = QPushButton(txt)
            btn.setFont(QFont(FONT, 11))
            btn.setFixedHeight(30)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._tabs.append(btn)
            tab_h.addWidget(btn)
            btn.clicked.connect(lambda _, i=i: self._on_tab(i))
        self._apply_tab_style(0)
        top.addWidget(tab_container)
        top.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Tìm kiếm...")
        self._search.setFixedSize(240, 34)
        self._search.setFont(QFont(FONT, 12))
        self._search.setStyleSheet("""
            QLineEdit { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 0 12px; background: white; color: #111; }
            QLineEdit:focus { border-color: #bbb; }
        """)
        self._search.textChanged.connect(self._apply_filter)
        top.addWidget(self._search)

        self._year_combo = QComboBox()
        self._year_combo.setFixedHeight(34)
        self._year_combo.setFont(QFont(FONT, 12))
        self._year_combo.setStyleSheet("""
            QComboBox { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 0 32px 0 12px; background: white;
                color: #111; min-width: 120px; }
            QComboBox::drop-down { subcontrol-origin: padding;
                subcontrol-position: center right; width: 28px;
                border-left: 1px solid #e0e0e0;
                border-top-right-radius: 8px; border-bottom-right-radius: 8px;
                background: white; }
            QComboBox::down-arrow { width: 10px; height: 10px; image: none;
                border-top: 5px solid #111;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent; }
            QComboBox QAbstractItemView { border: 1px solid #e0e0e0;
                border-radius: 6px; background: white; color: #111;
                selection-background-color: #f0f0f0; }
        """)
        from datetime import date as _date
        cur = _date.today().year
        self._year_combo.addItem("Tất cả", None)
        for y in range(cur, cur - 5, -1):
            self._year_combo.addItem(f"Năm {y}", y)
        self._year_combo.setCurrentIndex(1)
        self._year_combo.currentIndexChanged.connect(self._reload_history)
        self._year_combo.hide()
        top.addWidget(self._year_combo)

        root.addLayout(top)
        root.addSpacing(16)

        # ── H4 inventory table ─────────────────────────────────────────────
        self._h4_card = QFrame()
        self._h4_card.setStyleSheet(
            "QFrame { background: white; border-radius: 12px; border: 1px solid #efefef; }"
        )
        h4_v = QVBoxLayout(self._h4_card)
        h4_v.setContentsMargins(0, 0, 0, 0)

        self._h4_table = QTableWidget(0, len(self._h4_cols))
        self._h4_table.setHorizontalHeaderLabels(self._h4_cols)
        self._h4_table.verticalHeader().setVisible(False)
        self._h4_table.setShowGrid(False)
        self._h4_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._h4_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._h4_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._h4_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._h4_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._h4_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._h4_table.setStyleSheet(_TABLE_STYLE)
        _set_h4_col_widths(self._h4_table, self._wh_type)
        h4_v.addWidget(self._h4_table)

        # ── History table ──────────────────────────────────────────────────
        self._hist_card = QFrame()
        self._hist_card.setStyleSheet(
            "QFrame { background: white; border-radius: 12px; border: 1px solid #efefef; }"
        )
        hist_v = QVBoxLayout(self._hist_card)
        hist_v.setContentsMargins(0, 0, 0, 0)

        self._hist_table = QTableWidget(0, len(self._history_cols))
        self._hist_table.setHorizontalHeaderLabels(self._history_cols)
        self._hist_table.verticalHeader().setVisible(False)
        self._hist_table.verticalHeader().setMinimumSectionSize(0)
        self._hist_table.setShowGrid(False)
        self._hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hist_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._hist_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._hist_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hist_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hist_table.setStyleSheet(_TABLE_STYLE)
        _set_hist_col_widths(self._hist_table)
        self._hist_table.cellClicked.connect(self._on_hist_cell_clicked)
        hist_v.addWidget(self._hist_table)

        self._hist_card.hide()

        root.addWidget(self._h4_card, 1)
        root.addWidget(self._hist_card, 1)
        root.addSpacing(16)

        # ── Bottom button ──────────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.addStretch()
        self._btn_txl = QPushButton("+ Tạo Phiếu TXL")
        self._btn_txl.setFixedHeight(38)
        self._btn_txl.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        self._btn_txl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_txl.setStyleSheet(_BTN_RED)
        self._btn_txl.clicked.connect(self._on_create)
        bot.addWidget(self._btn_txl)
        root.addLayout(bot)

        self._active_tab = 0
        self.refresh()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _on_tab(self, idx: int):
        self._active_tab = idx
        self._apply_tab_style(idx)
        self._search.clear()
        if idx == 0:
            self._h4_card.show()
            self._hist_card.hide()
            self._year_combo.hide()
            self._btn_txl.show()
            self._reload_h4()
        else:
            self._h4_card.hide()
            self._hist_card.show()
            self._year_combo.show()
            self._btn_txl.hide()
            self._reload_history()

    def _apply_tab_style(self, active: int):
        for i, btn in enumerate(self._tabs):
            if i == active:
                btn.setStyleSheet("""
                    QPushButton { border: none; border-radius: 7px; padding: 0 14px;
                        background: #111; color: white; font-size: 11px; font-weight: 600; }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton { border: none; border-radius: 7px; padding: 0 14px;
                        background: transparent; color: #111; font-size: 11px; }
                    QPushButton:hover { background: #e3e3e3; }
                """)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        if self._active_tab == 0:
            self._reload_h4()
        else:
            self._reload_history()

    def _reload_h4(self):
        items = get_h4_inventory(self._wh_type)
        q = self._search.text().strip().lower()
        if q:
            items = [i for i in items if q in i.item_name.lower()
                     or q in i.warehouse_name.lower()]
        self._load_h4_table(items)

    def _reload_history(self):
        year = self._year_combo.currentData()
        self._cache = get_all(self._wh_type, year=year)
        self._apply_filter()

    def _apply_filter(self):
        q = self._search.text().strip().lower()
        if self._active_tab == 1:
            data = [
                r for r in self._cache
                if not q or any(q in s for s in [
                    r.reference_number.lower(),
                    r.warehouse_name.lower(),
                    (r.notes or "").lower(),
                    (r.created_by or "").lower(),
                    r.transaction_date.lower(),
                ])
            ]
            self._load_hist_table(data)
        else:
            self._reload_h4()

    def _load_h4_table(self, items):
        self._h4_table.setRowCount(0)
        show_months = (self._wh_type == "DON_VI")
        for i, item in enumerate(items):
            r = self._h4_table.rowCount()
            self._h4_table.insertRow(r)
            self._h4_table.setRowHeight(r, 52)

            cells = _h4_cells(i, item, show_months)
            for c, (val, center, style) in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 12))
                if center:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if style:
                    cell.setForeground(Qt.GlobalColor.red
                                       if "red" in style else Qt.GlobalColor.black)
                self._h4_table.setItem(r, c, cell)

    def _load_hist_table(self, records: list[TxlRecord]):
        self._expanded_row = None
        self._hist_table.clearSpans()
        n = len(self._history_cols)
        self._hist_table.setRowCount(len(records) * 2)
        for i, rec in enumerate(records):
            dr = i * 2
            det = i * 2 + 1
            self._hist_table.setRowHeight(dr, 52)
            self._hist_table.setRowHeight(det, 0)
            self._hist_table.setSpan(det, 0, 1, n)

            for c, val in enumerate([
                str(i + 1), rec.reference_number,
                rec.warehouse_name, str(rec.line_count),
                rec.transaction_date, rec.created_by, rec.notes or "",
            ]):
                cell = QTableWidgetItem(val)
                cell.setFont(QFont(FONT, 12))
                if c == 0:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._hist_table.setItem(dr, c, cell)

            dots = QPushButton("···")
            dots.setFlat(True)
            dots.setFont(QFont(FONT, 14))
            dots.setFixedSize(40, 40)
            dots.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            dots.setStyleSheet("""
                QPushButton { color: #111; border: none; background: transparent;
                    letter-spacing: 2px; border-radius: 6px; }
                QPushButton:hover { background: #f0f0f0; color: #555; }
            """)
            rx = rec
            dots.clicked.connect(lambda _, rx=rx: self._show_menu(rx))
            self._hist_table.setCellWidget(dr, n - 1, dots)

        self._hist_records = records

    # ── Interaction ───────────────────────────────────────────────────────────

    def _on_hist_cell_clicked(self, row: int, col: int):
        if row % 2 == 1:
            return
        det_row = row + 1
        if self._expanded_row == row:
            self._hist_table.setRowHeight(det_row, 0)
            self._hist_table.removeCellWidget(det_row, 0)
            self._expanded_row = None
            return
        if self._expanded_row is not None:
            prev = self._expanded_row + 1
            self._hist_table.setRowHeight(prev, 0)
            self._hist_table.removeCellWidget(prev, 0)

        rec = self._hist_records[row // 2]
        lines = get_lines(rec.id)
        panel = _DetailPanel(rec, lines)
        h = 120 + max(1, len(lines)) * 36
        self._hist_table.setCellWidget(det_row, 0, panel)
        self._hist_table.setRowHeight(det_row, h)
        self._expanded_row = row

    def _show_menu(self, rec: TxlRecord):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: white; border: 1px solid #e5e5e5;
                border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 20px; font-size: 13px;
                border-radius: 6px; color: #111; }
            QMenu::item:selected { background: #f5f5f5; }
        """)
        act_del = QAction("Xóa & Hoàn Tồn Kho", self)
        act_del.triggered.connect(lambda: self._delete(rec))
        menu.addAction(act_del)
        menu.exec(self._hist_table.cursor().pos())

    def _delete(self, rec: TxlRecord):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Xóa phiếu <b>{rec.reference_number or '(không số)'}</b>?<br>"
            "Số lượng H4 sẽ được hoàn lại về tồn kho.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete(rec.id)
            self._reload_history()

    def _on_create(self):
        from ui.dialogs.txl_form import TxlFormDialog
        dlg = TxlFormDialog(self._wh_type, self)
        if dlg.exec():
            self.refresh()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _h4_columns(wh_type: str) -> list[str]:
    cols = ["STT", "Kho / ĐV", "Tên Hàng", "ĐVT", "H4"]
    if wh_type == "DON_VI":
        cols += ["Ngày Nhận ĐV", "Niên Hạn (Năm)"]
    cols += ["Số Lô", "Ghi Chú"]
    return cols


def _h4_cells(i: int, item, show_months: bool):
    cells = [
        (str(i + 1), True, None),
        (item.warehouse_name, False, None),
        (item.item_name, False, None),
        (item.unit_of_measure, True, None),
        (str(item.quantity), True, None),
    ]
    if show_months:
        cells.append((item.received_at_unit_date or "—", True, None))
        mo = item.months_at_unit
        cells.append((f"{mo // 12} năm" if mo is not None else "—", True,
                       "red" if mo and mo >= 24 else None))
    cells += [
        (item.lot_number or "—", True, None),
        (item.notes or "", False, None),
    ]
    return cells


def _set_h4_col_widths(table: QTableWidget, wh_type: str):
    h = table.horizontalHeader()
    modes = [
        (QHeaderView.ResizeMode.Fixed, 52),
        (QHeaderView.ResizeMode.Stretch, None),
        (QHeaderView.ResizeMode.Stretch, None),
        (QHeaderView.ResizeMode.Fixed, 56),
        (QHeaderView.ResizeMode.Fixed, 72),
    ]
    if wh_type == "DON_VI":
        modes += [
            (QHeaderView.ResizeMode.Fixed, 110),
            (QHeaderView.ResizeMode.Fixed, 100),
        ]
    modes += [
        (QHeaderView.ResizeMode.Fixed, 100),
        (QHeaderView.ResizeMode.Stretch, None),
    ]
    for i, (mode, w) in enumerate(modes):
        h.setSectionResizeMode(i, mode)
        if w:
            table.setColumnWidth(i, w)


def _set_hist_col_widths(table: QTableWidget):
    h = table.horizontalHeader()
    for i, (mode, w) in enumerate([
        (QHeaderView.ResizeMode.Fixed, 52),
        (QHeaderView.ResizeMode.Fixed, 120),
        (QHeaderView.ResizeMode.Stretch, None),
        (QHeaderView.ResizeMode.Fixed, 88),
        (QHeaderView.ResizeMode.Fixed, 100),
        (QHeaderView.ResizeMode.Fixed, 120),
        (QHeaderView.ResizeMode.Stretch, None),
        (QHeaderView.ResizeMode.Fixed, 52),
    ]):
        h.setSectionResizeMode(i, mode)
        if w:
            table.setColumnWidth(i, w)


# ── Thin wrappers cho main.py ─────────────────────────────────────────────────

class TxlKhoPage(TxlPage):
    def __init__(self):
        super().__init__("TONG")


class TxlDonViPage(TxlPage):
    def __init__(self):
        super().__init__("DON_VI")
