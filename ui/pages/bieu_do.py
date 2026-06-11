"""Trang Biểu Đồ Thống Kê"""
from __future__ import annotations
import database
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRect, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath

FONT = "Segoe UI"

_H_COLORS = {"H1": "#4caf50", "H2": "#2196f3", "H3": "#ff9800", "H4": "#f44336"}
_BAR_PALETTE = [
    "#4361ee", "#7209b7", "#3a86ff", "#f72585",
    "#4cc9f0", "#560bad", "#06d6a0", "#e63946",
    "#ffd166", "#118ab2", "#ef476f", "#073b4c",
]


# ── Chart card wrapper ────────────────────────────────────────────────────────
def _card(title: str, widget: QWidget) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background: white; border: 1px solid #efefef; border-radius: 12px; }"
    )
    v = QVBoxLayout(frame)
    v.setContentsMargins(20, 16, 20, 20)
    v.setSpacing(12)
    lbl = QLabel(title)
    lbl.setFont(QFont(FONT, 12, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #111; border: none;")
    v.addWidget(lbl)
    v.addWidget(widget)
    return frame


# ── Donut Chart ───────────────────────────────────────────────────────────────
class _DonutChart(QWidget):
    """Donut/pie chart with inline legend."""

    def __init__(self):
        super().__init__()
        self._data: dict[str, tuple[int, str]] = {}  # label → (value, hex_color)
        self._center_text = ""
        self.setFixedHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, data: dict[str, tuple[int, str]], center: str = ""):
        self._data = {k: v for k, v in data.items() if v[0] > 0}
        self._center_text = center
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        total = sum(v for v, _ in self._data.values())
        if total == 0:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        LEGEND_W = 160
        chart_area_w = self.width() - LEGEND_W - 20
        h = self.height()

        # Donut dimensions
        size = min(chart_area_w, h) - 24
        cx = chart_area_w // 2
        cy = h // 2
        outer_r = size // 2
        inner_r = int(outer_r * 0.56)
        rect = QRect(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)

        # Draw segments (clockwise from top)
        angle = 90 * 16
        for label, (value, color) in self._data.items():
            span = int(round(360 * 16 * value / total))
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(rect, angle, -span)
            angle -= span

        # Inner hole
        painter.setBrush(QBrush(QColor("white")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        # Center label
        painter.setPen(QPen(QColor("#111")))
        font_size = max(9, min(18, inner_r // 3))
        painter.setFont(QFont(FONT, font_size, QFont.Weight.Bold))
        painter.drawText(
            QRect(cx - inner_r + 4, cy - inner_r + 4, (inner_r - 4) * 2, (inner_r - 4) * 2),
            Qt.AlignmentFlag.AlignCenter,
            self._center_text or str(total),
        )

        # Legend
        lx = chart_area_w + 20
        row_h = 26
        legend_total_h = len(self._data) * row_h
        ly = (h - legend_total_h) // 2
        painter.setFont(QFont(FONT, 11))
        for label, (value, color) in self._data.items():
            pct = f"{100 * value / total:.0f}%"
            # Color dot
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(lx, ly + 6, 14, 14), 3, 3)
            # Text
            painter.setPen(QPen(QColor("#333")))
            painter.drawText(
                QRect(lx + 20, ly, LEGEND_W - 24, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{label}  {value:,}  ({pct})",
            )
            ly += row_h


# ── Vertical Bar Chart ────────────────────────────────────────────────────────
class _BarChart(QWidget):
    """Vertical bar chart with value labels on top."""

    def __init__(self, height: int = 240):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[int] = []
        self._colors: list[str] = []
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, labels: list[str], values: list[int], colors: list[str] | None = None):
        self._labels = labels
        self._values = values
        self._colors = colors or [_BAR_PALETTE[i % len(_BAR_PALETTE)] for i in range(len(labels))]
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._labels:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        PAD_L, PAD_R, PAD_T, PAD_B = 52, 16, 22, 54
        W = self.width() - PAD_L - PAD_R
        H = self.height() - PAD_T - PAD_B

        max_v = max(self._values) if self._values else 1
        if max_v == 0:
            max_v = 1

        n = len(self._labels)
        slot_w = W // n
        bar_w = max(12, min(60, slot_w - 16))

        # Gridlines + y-axis labels
        painter.setFont(QFont(FONT, 9))
        GRID_STEPS = 4
        for i in range(GRID_STEPS + 1):
            gy = PAD_T + H - int(H * i / GRID_STEPS)
            painter.setPen(QPen(QColor("#f0f0f0"), 1))
            painter.drawLine(PAD_L, gy, PAD_L + W, gy)
            painter.setPen(QPen(QColor("#bbb")))
            val_str = str(int(max_v * i / GRID_STEPS))
            painter.drawText(
                QRect(0, gy - 10, PAD_L - 6, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                val_str,
            )

        # Bars
        for i, (label, value, color) in enumerate(zip(self._labels, self._values, self._colors)):
            bx = PAD_L + i * slot_w + (slot_w - bar_w) // 2
            bar_h = int(H * value / max_v)
            by = PAD_T + H - bar_h

            if bar_h > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(color)))
                path = QPainterPath()
                radius = min(5.0, bar_w / 3.0)
                # Rounded top corners only
                path.addRoundedRect(QRectF(bx, by, bar_w, bar_h), radius, radius)
                painter.fillRect(QRect(bx, by + int(radius) + 1, bar_w, max(0, bar_h - int(radius) - 1)),
                                 QColor(color))
                painter.drawPath(path)

            # Value label on top
            if value > 0:
                painter.setPen(QPen(QColor("#444")))
                painter.setFont(QFont(FONT, 9))
                painter.drawText(
                    QRect(bx - 16, by - 18, bar_w + 32, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{value:,}",
                )

            # X-axis label (truncate long names)
            short = label if len(label) <= 14 else label[:13] + "…"
            painter.setPen(QPen(QColor("#777")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(
                QRect(bx - 20, PAD_T + H + 8, bar_w + 40, 42),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                short,
            )


# ── Biểu Đồ Page ─────────────────────────────────────────────────────────────
class BieuDoPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("BieuDoPage { background: #fafafa; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 32)
        root.setSpacing(0)

        # Header
        greet = QLabel("Biểu Đồ Thống Kê")
        greet.setFont(QFont(FONT, 22, QFont.Weight.Bold))
        greet.setStyleSheet("color: #111;")
        root.addWidget(greet)

        sub = QLabel("Tổng quan hàng hóa theo chất lượng và kho lưu trữ")
        sub.setFont(QFont(FONT, 12))
        sub.setStyleSheet("color: #888; margin-top: 4px;")
        root.addWidget(sub)

        root.addSpacing(28)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #eee;")
        root.addWidget(sep)
        root.addSpacing(24)

        # Row 1 — Donut (H1-H4) | Bar (Kho Tổng)
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        self._donut = _DonutChart()
        row1.addWidget(_card("Tỉ Lệ Chất Lượng Hàng Hóa", self._donut), 2)

        self._bar_kho = _BarChart(height=240)
        row1.addWidget(_card("Hàng Tại Các Kho Tổng", self._bar_kho), 3)

        root.addLayout(row1)
        root.addSpacing(20)

        # Row 2 — Bar (Đơn Vị) full width
        self._bar_dv = _BarChart(height=260)
        root.addWidget(_card("Hàng Tại Các Đơn Vị", self._bar_dv))

        root.addStretch()

        self.refresh()

    def refresh(self):
        conn = database.get_conn()

        # ── Donut: H1/H2/H3/H4 from all inventory ────────────────────────────
        rows = conn.execute("""
            SELECT quality_level, SUM(quantity) AS qty
            FROM inventory
            WHERE quantity > 0
            GROUP BY quality_level
        """).fetchall()
        h_totals = {"H1": 0, "H2": 0, "H3": 0, "H4": 0}
        for r in rows:
            ql = r["quality_level"]
            if ql in h_totals:
                h_totals[ql] = r["qty"]
        grand_total = sum(h_totals.values())
        self._donut.load(
            {k: (v, _H_COLORS[k]) for k, v in h_totals.items()},
            center=f"{grand_total:,}\nchiếc",
        )

        # ── Bar: hàng tại Kho Tổng (top 10) ──────────────────────────────────
        kho_rows = conn.execute("""
            SELECT w.name, SUM(i.quantity) AS qty
            FROM inventory i
            JOIN warehouses w ON w.id = i.warehouse_id
            WHERE w.type = 'TONG' AND i.quantity > 0
            GROUP BY w.id
            ORDER BY qty DESC
            LIMIT 10
        """).fetchall()
        self._bar_kho.load(
            [r["name"] for r in kho_rows],
            [r["qty"] for r in kho_rows],
        )

        # ── Bar: hàng tại Đơn Vị (top 15) ────────────────────────────────────
        dv_rows = conn.execute("""
            SELECT w.name, SUM(i.quantity) AS qty
            FROM inventory i
            JOIN warehouses w ON w.id = i.warehouse_id
            WHERE w.type = 'DON_VI' AND i.quantity > 0
            GROUP BY w.id
            ORDER BY qty DESC
            LIMIT 15
        """).fetchall()
        self._bar_dv.load(
            [r["name"] for r in dv_rows],
            [r["qty"] for r in dv_rows],
        )
