"""Trang Biểu Đồ Thống Kê"""
from __future__ import annotations
import math
import datetime
import database
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy,
    QComboBox, QScrollArea, QLineEdit, QToolTip,
)
from PyQt6.QtCore import Qt, QRect, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath

FONT = "Segoe UI"

# Pie chart — blue tones (matches reference image)
_PIE_COLORS = {"H1": "#1a5fa8", "H2": "#4a90d9", "H3": "#8ab4e8", "H4": "#c5d8f0"}
# Stacked bar / line — semantic aging colors
_AGE_COLORS = {"H1": "#4caf50", "H2": "#2196f3", "H3": "#ff9800", "H4": "#e53935"}
_LINE_PALETTE = [
    "#4361ee", "#f72585", "#06d6a0", "#e63946",
    "#ffd166", "#7209b7", "#118ab2", "#ef476f",
]
_BAR_PALETTE = [
    "#4361ee", "#7209b7", "#3a86ff", "#f72585",
    "#4cc9f0", "#560bad", "#06d6a0", "#e63946",
    "#ffd166", "#118ab2", "#ef476f", "#073b4c",
]
_NHAP_COLOR   = "#2563eb"
_XUAT_COLOR   = "#f59e0b"
_PARETO_BAR   = "#4361ee"
_PARETO_LINE  = "#e53935"

_COMBO_STYLE = """
    QComboBox {
        border: 1px solid #e0e0e0; border-radius: 7px;
        padding: 0 28px 0 10px; background: white; color: #111;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding; subcontrol-position: center right;
        width: 24px; border-left: 1px solid #e0e0e0;
        border-top-right-radius: 7px; border-bottom-right-radius: 7px;
        background: white;
    }
    QComboBox::down-arrow {
        width: 8px; height: 8px; image: none;
        border-top: 4px solid #555;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
    }
    QComboBox QAbstractItemView {
        border: 1px solid #e0e0e0; border-radius: 6px;
        background: white; color: #111;
        selection-background-color: #f0f0f0;
    }
"""
_SEARCH_STYLE = """
    QLineEdit { border: 1px solid #e0e0e0; border-radius: 7px;
        padding: 0 10px; background: white; color: #111; }
    QLineEdit:focus { border-color: #bbb; }
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ellipse_pt(cx, cy, rx, ry, deg):
    a = math.radians(deg)
    return cx + rx * math.cos(a), cy - ry * math.sin(a)


def _darken(color: QColor, amount: int = 50) -> QColor:
    return QColor(
        max(0, color.red()   - amount),
        max(0, color.green() - amount),
        max(0, color.blue()  - amount),
    )


def _card_frame(title: str) -> tuple[QFrame, QVBoxLayout]:
    """Return (frame, body_layout) — header label already added."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background: white; border: 1px solid #efefef; border-radius: 12px; }"
    )
    v = QVBoxLayout(frame)
    v.setContentsMargins(20, 16, 20, 20)
    v.setSpacing(10)
    lbl = QLabel(title)
    lbl.setFont(QFont(FONT, 12, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #111; border: none;")
    v.addWidget(lbl)
    return frame, v


def _card(title: str, widget: QWidget) -> QFrame:
    frame, v = _card_frame(title)
    v.addWidget(widget)
    return frame


# ── 3D Pie Chart ──────────────────────────────────────────────────────────────
class _Pie3DChart(QWidget):
    def __init__(self):
        super().__init__()
        self._data: dict[str, tuple[int, str]] = {}
        self.setFixedHeight(270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, data: dict[str, tuple[int, str]]):
        self._data = {k: v for k, v in data.items() if v[0] > 0}
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

        W, H = self.width(), self.height()
        LEGEND_W = 185
        chart_w = W - LEGEND_W - 24
        DEPTH = max(14, int(min(chart_w, H) * 0.09))
        rx = chart_w // 2 - 18
        ry = int(rx * 0.47)
        cx = chart_w // 2
        cy = (H - DEPTH) // 2 + 6

        start = 90.0
        segments: list[tuple] = []
        for label, (value, color) in self._data.items():
            span = 360.0 * value / total
            segments.append((label, value, color, start, span))
            start -= span

        def back_first(seg):
            _, _, _, sa, sp = seg
            return math.sin(math.radians(sa - sp / 2))

        ordered = sorted(segments, key=back_first, reverse=True)
        for seg in ordered:
            self._draw_depth(painter, cx, cy, rx, ry, DEPTH, seg[3], seg[4], seg[2])
        for seg in ordered:
            self._draw_top(painter, cx, cy, rx, ry, seg[3], seg[4], seg[2])

        painter.setFont(QFont(FONT, 11, QFont.Weight.Bold))
        for label, value, color_hex, start_a, span_a in segments:
            pct = 100 * value / total
            if pct < 5:
                continue
            mid_a = start_a - span_a / 2
            lx, ly = _ellipse_pt(cx, cy, rx * 0.60, ry * 0.60, mid_a)
            if ly > cy:
                ly += DEPTH * 0.35
            painter.setPen(QPen(QColor("white")))
            painter.drawText(QRect(int(lx) - 34, int(ly) - 14, 68, 28),
                             Qt.AlignmentFlag.AlignCenter, f"{pct:.0f}%")

        lx = chart_w + 24
        row_h = 28
        ly = (H - len(self._data) * row_h) // 2
        painter.setFont(QFont(FONT, 11))
        for label, (value, color_hex) in self._data.items():
            pct_str = f"{100 * value / total:.1f}%"
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.drawRoundedRect(QRect(lx, ly + 7, 14, 14), 3, 3)
            painter.setPen(QPen(QColor("#333")))
            painter.drawText(QRect(lx + 20, ly, LEGEND_W - 24, row_h),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             f"{label}  {value:,}  ({pct_str})")
            ly += row_h

    def _draw_depth(self, painter, cx, cy, rx, ry, depth, start_a, span_a, color_hex):
        base = QColor(color_hex)
        dark = _darken(base, 55)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dark))
        N = max(16, int(abs(span_a) / 2))
        all_pts = [_ellipse_pt(cx, cy, rx, ry, start_a - span_a * i / N) for i in range(N + 1)]
        lower = [(x, y) for x, y in all_pts if y >= cy - 1]
        if len(lower) >= 2:
            path = QPainterPath()
            path.moveTo(*lower[0])
            for x, y in lower[1:]:
                path.lineTo(x, y)
            for x, y in reversed(lower):
                path.lineTo(x, y + depth)
            path.closeSubpath()
            painter.drawPath(path)
        for x1, y1 in [all_pts[0], all_pts[-1]]:
            if y1 >= cy - 1:
                path2 = QPainterPath()
                path2.moveTo(cx, cy)
                path2.lineTo(x1, y1)
                path2.lineTo(x1, y1 + depth)
                path2.lineTo(cx, cy + depth)
                path2.closeSubpath()
                painter.drawPath(path2)

    def _draw_top(self, painter, cx, cy, rx, ry, start_a, span_a, color_hex):
        N = max(16, int(abs(span_a) / 2))
        path = QPainterPath()
        path.moveTo(cx, cy)
        for i in range(N + 1):
            x, y = _ellipse_pt(cx, cy, rx, ry, start_a - span_a * i / N)
            path.lineTo(x, y)
        path.closeSubpath()
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(QPen(QColor("white"), 1.5))
        painter.drawPath(path)


# ── Vertical Bar Chart ────────────────────────────────────────────────────────
class _BarChart(QWidget):
    def __init__(self, height: int = 240):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[int] = []
        self._colors: list[str] = []
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, labels, values, colors=None):
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
        painter.setFont(QFont(FONT, 9))
        for i in range(5):
            gy = PAD_T + H - int(H * i / 4)
            painter.setPen(QPen(QColor("#f0f0f0"), 1))
            painter.drawLine(PAD_L, gy, PAD_L + W, gy)
            painter.setPen(QPen(QColor("#bbb")))
            painter.drawText(QRect(0, gy - 10, PAD_L - 6, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_v * i / 4)))
        for i, (label, value, color) in enumerate(zip(self._labels, self._values, self._colors)):
            bx = PAD_L + i * slot_w + (slot_w - bar_w) // 2
            bar_h = int(H * value / max_v)
            by = PAD_T + H - bar_h
            if bar_h > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(color)))
                path = QPainterPath()
                r = min(5.0, bar_w / 3.0)
                path.addRoundedRect(QRectF(bx, by, bar_w, bar_h), r, r)
                painter.fillRect(QRect(bx, by + int(r) + 1, bar_w, max(0, bar_h - int(r) - 1)), QColor(color))
                painter.drawPath(path)
            if value > 0:
                painter.setPen(QPen(QColor("#444")))
                painter.setFont(QFont(FONT, 9))
                painter.drawText(QRect(bx - 16, by - 18, bar_w + 32, 16), Qt.AlignmentFlag.AlignCenter, f"{value:,}")
            short = label if len(label) <= 14 else label[:13] + "…"
            painter.setPen(QPen(QColor("#777")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(bx - 20, PAD_T + H + 8, bar_w + 40, 42),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, short)


# ── Stacked Bar Chart ─────────────────────────────────────────────────────────
class _StackedBarChart(QWidget):
    """H1/H2/H3/H4 stacked bars per item type."""
    _SLOT_W = 58
    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 56, 20, 24, 64
    _LEGEND_H = 28

    def __init__(self, height: int = 310):
        super().__init__()
        self._items: list[tuple[str, str, int, int, int, int]] = []  # (code, name, h1,h2,h3,h4)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)

    def load(self, items: list[tuple[str, str, int, int, int, int]]):
        self._items = items
        min_w = self._PAD_L + self._PAD_R + max(1, len(items)) * self._SLOT_W
        self.setMinimumWidth(max(400, min_w))
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._items:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        PL, PR, PT, PB = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        LH = self._LEGEND_H
        W = self.width() - PL - PR
        H = self.height() - PT - PB - LH

        n = len(self._items)
        slot_w = max(self._SLOT_W, W // n)
        bar_w = max(18, min(48, slot_w - 14))

        vals_list = [(h1, h2, h3, h4) for _, _, h1, h2, h3, h4 in self._items]
        max_total = max((sum(v) for v in vals_list), default=1) or 1

        h_keys = ["H1", "H2", "H3", "H4"]
        h_colors = [_AGE_COLORS[k] for k in h_keys]

        # Grid
        STEPS = 4
        for i in range(STEPS + 1):
            gy = PT + H - int(H * i / STEPS)
            painter.setPen(QPen(QColor("#f0f0f0"), 1))
            painter.drawLine(PL, gy, PL + W, gy)
            painter.setPen(QPen(QColor("#bbb")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(0, gy - 10, PL - 6, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_total * i / STEPS)))

        # Bars
        for i, (code, name, h1, h2, h3, h4) in enumerate(self._items):
            bx = PL + i * slot_w + (slot_w - bar_w) // 2
            vals = [h1, h2, h3, h4]
            total = sum(vals)
            if total == 0:
                continue

            y_bot = PT + H
            # Determine topmost non-zero index for rounded corners
            top_idx = max((j for j, v in enumerate(vals) if v > 0), default=0)

            for j, (val, color_hex) in enumerate(zip(vals, h_colors)):
                if val == 0:
                    continue
                seg_h = max(2, int(H * val / max_total))
                by = y_bot - seg_h
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(color_hex)))

                if j == top_idx:
                    r = min(5.0, bar_w / 4.0)
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(bx, by, bar_w, seg_h), r, r)
                    painter.fillRect(QRect(bx, by + int(r) + 1, bar_w, max(0, seg_h - int(r) - 1)),
                                     QColor(color_hex))
                    painter.drawPath(path)
                else:
                    painter.drawRect(bx, by, bar_w, seg_h)

                # Value label inside segment
                if seg_h >= 16 and val > 0:
                    painter.setPen(QPen(QColor("white")))
                    painter.setFont(QFont(FONT, 8, QFont.Weight.Bold))
                    painter.drawText(QRect(bx, by, bar_w, seg_h),
                                     Qt.AlignmentFlag.AlignCenter, str(val))
                y_bot = by

            # Total label on top
            painter.setPen(QPen(QColor("#444")))
            painter.setFont(QFont(FONT, 8))
            painter.drawText(QRect(bx - 10, PT + H - int(H * total / max_total) - 16,
                                   bar_w + 20, 14),
                             Qt.AlignmentFlag.AlignCenter, f"{total:,}")

            # X-axis label (item code, rotated 30°)
            short = code if len(code) <= 10 else code[:9] + "…"
            painter.setPen(QPen(QColor("#555")))
            painter.setFont(QFont(FONT, 8))
            painter.save()
            painter.translate(bx + bar_w // 2, PT + H + 8)
            painter.rotate(30)
            painter.drawText(0, 0, 100, 14, Qt.AlignmentFlag.AlignLeft, short)
            painter.restore()

        # Legend
        ly = self.height() - LH + 4
        lx = PL
        for key, color in zip(h_keys, h_colors):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawRoundedRect(QRect(lx, ly + 8, 12, 12), 2, 2)
            painter.setPen(QPen(QColor("#555")))
            painter.setFont(QFont(FONT, 10))
            painter.drawText(QRect(lx + 16, ly, 40, LH),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, key)
            lx += 56


# ── Line Chart ────────────────────────────────────────────────────────────────
class _LineChart(QWidget):
    """Multi-series line chart for H4 forecast."""
    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 58, 24, 26, 58

    def __init__(self, height: int = 290):
        super().__init__()
        self._series: dict[str, list[tuple[str, int]]] = {}
        self._colors: list[str] = _LINE_PALETTE
        self._x_labels: list[str] = []
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, series: dict[str, list[tuple[str, int]]], colors: list[str] | None = None):
        self._series = series
        self._colors = colors or _LINE_PALETTE
        all_dates: list[str] = sorted({d for pts in series.values() for d, _ in pts})
        # Fill in gaps between first and last date (monthly)
        if len(all_dates) >= 2:
            first = datetime.date.fromisoformat(all_dates[0] + "-01")
            last  = datetime.date.fromisoformat(all_dates[-1] + "-01")
            filled: list[str] = []
            cur = first
            while cur <= last:
                filled.append(cur.strftime("%Y-%m"))
                # next month
                m = cur.month + 1
                y = cur.year + (1 if m > 12 else 0)
                cur = datetime.date(y, m % 12 or 12, 1)
            self._x_labels = filled
        else:
            self._x_labels = all_dates
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._series or not self._x_labels:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        PL, PR, PT, PB = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        W = self.width() - PL - PR
        H = self.height() - PT - PB

        n_x = len(self._x_labels)
        max_v = max((v for pts in self._series.values() for _, v in pts), default=1) or 1

        # Grid
        STEPS = 5
        for i in range(STEPS + 1):
            gy = PT + H - int(H * i / STEPS)
            painter.setPen(QPen(QColor("#f0f0f0" if i > 0 else "#e0e0e0"), 1))
            painter.drawLine(PL, gy, PL + W, gy)
            painter.setPen(QPen(QColor("#bbb")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(0, gy - 10, PL - 6, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_v * i / STEPS)))

        def x_pos(xi):
            return PL + int(W * xi / max(1, n_x - 1)) if n_x > 1 else PL + W // 2

        # Series lines
        for si, (series_name, pts) in enumerate(self._series.items()):
            color = QColor(self._colors[si % len(self._colors)])
            pt_map = {d: v for d, v in pts}

            screen_pts: list[tuple[int, int]] = []
            for xi, date in enumerate(self._x_labels):
                v = pt_map.get(date, 0)
                px = x_pos(xi)
                py = PT + H - int(H * v / max_v)
                screen_pts.append((px, py))

            # Draw line
            for i in range(1, len(screen_pts)):
                painter.setPen(QPen(color, 2))
                painter.drawLine(screen_pts[i-1][0], screen_pts[i-1][1],
                                 screen_pts[i][0], screen_pts[i][1])

            # Draw dots only at non-zero points
            for xi, (px, py) in enumerate(screen_pts):
                v = pt_map.get(self._x_labels[xi], 0)
                if v > 0:
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor("white"), 1.5))
                    painter.drawEllipse(px - 4, py - 4, 8, 8)
                    # Value label
                    painter.setPen(QPen(color))
                    painter.setFont(QFont(FONT, 8, QFont.Weight.Bold))
                    painter.drawText(QRect(px - 20, py - 20, 40, 14),
                                     Qt.AlignmentFlag.AlignCenter, str(v))

        # X-axis labels — show at most every Nth label to avoid crowding
        max_show = max(2, W // 56)
        step = max(1, math.ceil(n_x / max_show))
        today_str = datetime.date.today().strftime("%Y-%m")
        for xi, date in enumerate(self._x_labels):
            if xi % step != 0 and xi != n_x - 1:
                continue
            px = x_pos(xi)
            label = date[2:4] + "/" + date[5:7]  # "YY/MM"
            painter.setPen(QPen(QColor("#e53935") if date == today_str else QColor("#777")))
            painter.setFont(QFont(FONT, 8))
            painter.save()
            painter.translate(px, PT + H + 10)
            painter.rotate(30)
            painter.drawText(0, 0, label)
            painter.restore()

        # Legend (bottom-right area)
        legend_x = PL
        legend_y = self.height() - 20
        for si, name in enumerate(self._series.keys()):
            color = QColor(self._colors[si % len(self._colors)])
            painter.setPen(QPen(color, 2))
            painter.drawLine(legend_x, legend_y, legend_x + 18, legend_y)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(legend_x + 5, legend_y - 4, 8, 8)
            painter.setPen(QPen(QColor("#444")))
            painter.setFont(QFont(FONT, 9))
            short = name if len(name) <= 20 else name[:19] + "…"
            tw = len(short) * 6 + 10
            painter.drawText(legend_x + 22, legend_y - 8, tw, 18,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, short)
            legend_x += tw + 28


# ── Grouped Bar Chart (Nhập vs Xuất theo tháng) ──────────────────────────────
class _GroupedBarChart(QWidget):
    """Two bars per month: Nhập Kho vs Xuất Kho."""
    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 56, 20, 24, 52
    _GAP = 3   # gap between pair bars

    def __init__(self, height: int = 270):
        super().__init__()
        # {month_str: (nhap_qty, xuat_qty)}
        self._data: dict[str, tuple[int, int]] = {}
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, data: dict[str, tuple[int, int]]):
        self._data = data
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._data:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        PL, PR, PT, PB = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        W = self.width() - PL - PR
        H = self.height() - PT - PB
        months = sorted(self._data.keys())
        n = len(months)
        max_v = max((max(a, b) for a, b in self._data.values()), default=1) or 1

        slot_w = W // n if n else W
        pair_w = min(slot_w - 12, 70)
        single_w = (pair_w - self._GAP) // 2

        # Grid
        for i in range(5):
            gy = PT + H - int(H * i / 4)
            painter.setPen(QPen(QColor("#f0f0f0"), 1))
            painter.drawLine(PL, gy, PL + W, gy)
            painter.setPen(QPen(QColor("#bbb")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(0, gy - 10, PL - 6, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_v * i / 4)))

        for i, month in enumerate(months):
            nhap, xuat = self._data[month]
            cx_pair = PL + i * slot_w + (slot_w - pair_w) // 2

            for val, color_hex, bx in [
                (nhap, _NHAP_COLOR, cx_pair),
                (xuat, _XUAT_COLOR, cx_pair + single_w + self._GAP),
            ]:
                bar_h = int(H * val / max_v)
                by = PT + H - bar_h
                if bar_h > 0:
                    r = min(4.0, single_w / 4.0)
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(bx, by, single_w, bar_h), r, r)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(color_hex)))
                    painter.fillRect(QRect(bx, by + int(r) + 1, single_w,
                                          max(0, bar_h - int(r) - 1)), QColor(color_hex))
                    painter.drawPath(path)
                if val > 0:
                    painter.setPen(QPen(QColor("#444")))
                    painter.setFont(QFont(FONT, 8))
                    painter.drawText(QRect(bx - 8, by - 14, single_w + 16, 12),
                                     Qt.AlignmentFlag.AlignCenter, f"{val:,}")

            # X label (YY/MM)
            label = month[2:4] + "/" + month[5:7]
            painter.setPen(QPen(QColor("#777")))
            painter.setFont(QFont(FONT, 8))
            painter.drawText(QRect(cx_pair - 8, PT + H + 6, pair_w + 16, 20),
                             Qt.AlignmentFlag.AlignCenter, label)

        # Legend
        legend_y = self.height() - 16
        for lx, color, label in [
            (PL,      _NHAP_COLOR, "Nhập Kho"),
            (PL + 90, _XUAT_COLOR, "Xuất Kho"),
        ]:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawRoundedRect(QRect(lx, legend_y - 5, 12, 12), 2, 2)
            painter.setPen(QPen(QColor("#555")))
            painter.setFont(QFont(FONT, 10))
            painter.drawText(QRect(lx + 16, legend_y - 8, 80, 18),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)


# ── Horizontal Bar Chart (Top-N H4) ──────────────────────────────────────────
class _HBarChart(QWidget):
    """Horizontal bar chart — ideal for ranked unit comparison."""
    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 16, 70, 16, 16
    _ROW_H = 38

    def __init__(self, max_bars: int = 5):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[int] = []
        self._colors: list[str] = []
        self._max_bars = max_bars
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(
            self._PAD_T + self._PAD_B + max_bars * self._ROW_H
        )

    def load(self, labels: list[str], values: list[int], colors: list[str] | None = None):
        self._labels = labels[:self._max_bars]
        self._values = values[:self._max_bars]
        self._colors = (colors or [_BAR_PALETTE[i % len(_BAR_PALETTE)]
                                    for i in range(len(self._labels))])[:self._max_bars]
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._labels:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        PL, PR, PT, PB = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        NAME_W = 150
        W = self.width() - PL - PR - NAME_W
        max_v = max(self._values) if self._values else 1

        for i, (label, value, color) in enumerate(
                zip(self._labels, self._values, self._colors)):
            y = PT + i * self._ROW_H
            bar_h = 22
            by = y + (self._ROW_H - bar_h) // 2

            # Name label
            short = label if len(label) <= 20 else label[:19] + "…"
            painter.setPen(QPen(QColor("#333")))
            painter.setFont(QFont(FONT, 10))
            painter.drawText(QRect(PL, by, NAME_W - 8, bar_h),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             short)

            # Bar
            bar_w = int(W * value / max_v)
            bx = PL + NAME_W
            if bar_w > 0:
                r = min(5.0, bar_h / 4.0)
                path = QPainterPath()
                path.addRoundedRect(QRectF(bx, by, bar_w, bar_h), r, r)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(color)))
                painter.fillRect(QRect(bx, by + 1, max(0, bar_w - int(r)), bar_h - 2),
                                 QColor(color))
                painter.drawPath(path)

            # Value label right of bar
            painter.setPen(QPen(QColor("#444")))
            painter.setFont(QFont(FONT, 10, QFont.Weight.Bold))
            painter.drawText(QRect(bx + bar_w + 6, by, PR + 60, bar_h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:,}")


# ── Heatmap Grid ─────────────────────────────────────────────────────────────
class _HeatmapGrid(QWidget):
    """Y = items, X = H1/H2/H3/H4; cell color intensity proportional to quantity."""

    HEADER_H = 34
    ROW_H    = 28
    NAME_W   = 200
    CELL_W   = 88
    PAD_L    = 10

    _PALETTES = {
        "H1": ("#e8f5e9", "#1b5e20"),
        "H2": ("#e3f2fd", "#0d47a1"),
        "H3": ("#fff3e0", "#bf360c"),
        "H4": ("#ffebee", "#b71c1c"),
    }
    _LEVELS = ["H1", "H2", "H3", "H4"]

    def __init__(self):
        super().__init__()
        self._items: list[tuple] = []   # (code, name, h1, h2, h3, h4)
        self._col_max: list[int] = [1, 1, 1, 1]
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def load(self, items: list[tuple]):
        self._items = items
        self._col_max = [
            max((row[2 + j] for row in items), default=0) or 1
            for j in range(4)
        ]
        self.setMinimumHeight(self.HEADER_H + len(items) * self.ROW_H)
        self.update()

    def _cell_color(self, col: int, value: int) -> QColor:
        if value == 0:
            return QColor("#f2f2f2")
        light_hex, dark_hex = self._PALETTES[self._LEVELS[col]]
        t = min(1.0, value / self._col_max[col]) ** 0.6
        l, d = QColor(light_hex), QColor(dark_hex)
        return QColor(
            int(l.red()   + t * (d.red()   - l.red())),
            int(l.green() + t * (d.green() - l.green())),
            int(l.blue()  + t * (d.blue()  - l.blue())),
        )

    def _hit(self, x, y):
        row = (y - self.HEADER_H) // self.ROW_H
        col = (x - self.PAD_L - self.NAME_W) // self.CELL_W
        if 0 <= row < len(self._items) and 0 <= col < 4:
            item = self._items[row]
            return item[1], self._LEVELS[col], item[2 + col]
        return None

    def mouseMoveEvent(self, event):
        info = self._hit(event.pos().x(), event.pos().y())
        if info:
            name, level, value = info
            tip = f"{name}\n{level}: {value:,}" if value else f"{name}\n{level}: —"
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()
        x_div = self.PAD_L + self.NAME_W

        if not self._items:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(QRect(0, 0, W, 120),
                             Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        # Header row
        painter.fillRect(QRect(0, 0, W, self.HEADER_H), QColor("#f5f5f5"))
        painter.setPen(QPen(QColor("#ddd"), 1))
        painter.drawLine(0, self.HEADER_H - 1, W, self.HEADER_H - 1)
        painter.setFont(QFont(FONT, 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#555")))
        painter.drawText(QRect(self.PAD_L, 0, self.NAME_W - 4, self.HEADER_H),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         "Mặt Hàng")
        for j, level in enumerate(self._LEVELS):
            cx = x_div + j * self.CELL_W
            _, dark_hex = self._PALETTES[level]
            painter.setPen(QPen(QColor(dark_hex)))
            painter.setFont(QFont(FONT, 10, QFont.Weight.Bold))
            painter.drawText(QRect(cx, 0, self.CELL_W, self.HEADER_H),
                             Qt.AlignmentFlag.AlignCenter, level)

        # Vertical divider after name column
        painter.setPen(QPen(QColor("#ddd"), 1))
        painter.drawLine(x_div, 0, x_div, self.height())

        # Data rows
        for i, (code, name, h1, h2, h3, h4) in enumerate(self._items):
            y = self.HEADER_H + i * self.ROW_H
            vals = [h1, h2, h3, h4]

            # Alternating row background for name column
            painter.fillRect(
                QRect(0, y, x_div, self.ROW_H),
                QColor("#fafafa") if i % 2 == 0 else QColor("white"),
            )

            # Item name
            short = name if len(name) <= 24 else name[:23] + "…"
            painter.setPen(QPen(QColor("#333")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(self.PAD_L, y, self.NAME_W - 6, self.ROW_H),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             short)

            # Heat cells
            for j, val in enumerate(vals):
                cx = x_div + j * self.CELL_W
                painter.fillRect(
                    QRect(cx + 1, y + 1, self.CELL_W - 2, self.ROW_H - 2),
                    self._cell_color(j, val),
                )
                if val > 0:
                    t = val / self._col_max[j]
                    painter.setPen(QPen(QColor("white") if t > 0.45 else QColor("#333")))
                    painter.setFont(QFont(FONT, 9))
                    painter.drawText(QRect(cx, y, self.CELL_W, self.ROW_H),
                                     Qt.AlignmentFlag.AlignCenter, f"{val:,}")

            # Row separator
            painter.setPen(QPen(QColor("#eeeeee"), 1))
            painter.drawLine(0, y + self.ROW_H, W, y + self.ROW_H)

        # Vertical separators between quality columns
        painter.setPen(QPen(QColor("#e0e0e0"), 1))
        for j in range(1, 4):
            x = x_div + j * self.CELL_W
            painter.drawLine(x, 0, x, self.height())


# ── Donut Chart (H4 tại các đơn vị) ──────────────────────────────────────────
_DONUT_PALETTE = [
    "#4361ee", "#f72585", "#06d6a0", "#e63946", "#ffd166",
    "#7209b7", "#118ab2", "#ef476f", "#2ec4b6", "#e9c46a",
    "#264653", "#2a9d8f", "#e76f51", "#a8dadc", "#457b9d",
    "#6a4c93", "#c77dff", "#48cae4", "#ff9f1c", "#f4a261",
]


class _DonutChart(QWidget):
    """Donut chart with outward callout lines — H4 distribution across units."""

    def __init__(self, height: int = 340):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[int] = []
        self._colors: list[str] = []
        self.setFixedHeight(height)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, labels: list[str], values: list[int], colors: list[str] | None = None):
        self._labels = labels
        self._values = values
        self._colors = colors or [_DONUT_PALETTE[i % len(_DONUT_PALETTE)]
                                   for i in range(len(labels))]
        self.update()

    def _geom(self):
        W, H = self.width(), self.height()
        size = min(W - 280, H - 20)
        size = max(size, 60)
        R  = size // 2
        ri = int(R * 0.52)
        return W // 2, H // 2, R, ri

    def _hit_segment(self, pos) -> int | None:
        total = sum(self._values) or 1
        cx, cy, R, ri = self._geom()
        dx, dy = pos.x() - cx, pos.y() - cy
        dist = math.sqrt(dx * dx + dy * dy)
        if not (ri < dist <= R + 4):
            return None
        norm = (90 - math.degrees(math.atan2(-dy, dx))) % 360
        start = 0.0
        for i, value in enumerate(self._values):
            span = 360.0 * value / total
            if start <= norm < start + span:
                return i
            start += span
        return None

    def mouseMoveEvent(self, event):
        idx = self._hit_segment(event.pos())
        if idx is not None:
            name   = self._labels[idx]
            value  = self._values[idx]
            total  = sum(self._values) or 1
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{name}\n{value:,}  ({100 * value / total:.1f}%)",
                self,
            )
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        if not self._labels:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        total = sum(self._values) or 1
        cx, cy, R, ri = self._geom()
        ARM     = 20    # radial arm length (px)
        ELBOW   = 16    # horizontal elbow (px)
        MIN_DEG = 5     # skip callout for segments < 5°

        # ── Segments ─────────────────────────────────────────────────────────
        qt_start = 90 * 16
        segs: list[tuple] = []
        for label, value, color in zip(self._labels, self._values, self._colors):
            span = int(360 * 16 * value / total)
            if span == 0:
                continue
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor("white"), 1.2))
            painter.drawPie(QRect(cx - R, cy - R, 2 * R, 2 * R), qt_start, -span)
            segs.append((qt_start - span // 2, span, label, value, color))
            qt_start -= span

        # ── Center hole ───────────────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("white")))
        painter.drawEllipse(QRect(cx - ri, cy - ri, 2 * ri, 2 * ri))

        # ── Center text ───────────────────────────────────────────────────────
        painter.setPen(QPen(QColor("#111")))
        painter.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        painter.drawText(QRect(cx - ri, cy - 22, 2 * ri, 26),
                         Qt.AlignmentFlag.AlignCenter, f"{total:,}")
        painter.setFont(QFont(FONT, 9))
        painter.setPen(QPen(QColor("#888")))
        painter.drawText(QRect(cx - ri, cy + 6, 2 * ri, 18),
                         Qt.AlignmentFlag.AlignCenter, "tổng H4")

        # ── Callout lines + labels ────────────────────────────────────────────
        for mid_qt, span, label, value, color in segs:
            if span / 16 < MIN_DEG:
                continue

            rad = math.radians(mid_qt / 16)
            x1 = cx + R * math.cos(rad)
            y1 = cy - R * math.sin(rad)
            x2 = cx + (R + ARM) * math.cos(rad)
            y2 = cy - (R + ARM) * math.sin(rad)
            right = x2 >= cx
            x3 = x2 + (ELBOW if right else -ELBOW)
            y3 = y2

            c = QColor(color)
            painter.setPen(QPen(c, 1.3))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            painter.drawLine(int(x2), int(y2), int(x3), int(y3))

            TW, TH = 130, 34
            pct   = 100 * value / total
            short = label if len(label) <= 14 else label[:13] + "…"
            tx = int(x3) + 3 if right else int(x3) - TW - 3
            ty = int(y3) - TH // 2
            tx = max(2, min(W - TW - 2, tx))
            ty = max(2, min(H - TH - 2, ty))

            a = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            painter.setPen(QPen(QColor("#333")))
            painter.setFont(QFont(FONT, 8))
            painter.drawText(QRect(tx, ty, TW, 16), a, short)
            painter.setPen(QPen(c))
            painter.setFont(QFont(FONT, 8, QFont.Weight.Bold))
            painter.drawText(QRect(tx, ty + 17, TW, 16), a,
                             f"{value:,}  ({pct:.0f}%)")


# ── Pareto Chart ─────────────────────────────────────────────────────────────
class _ParetoChart(QWidget):
    """Bars sorted desc + cumulative % line + 80% reference marker."""
    _SLOT_W = 62
    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 56, 64, 28, 60

    def __init__(self, height: int = 290):
        super().__init__()
        self._labels: list[str] = []
        self._values: list[int] = []
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)

    def load(self, labels: list[str], values: list[int]):
        self._labels = labels
        self._values = values
        min_w = self._PAD_L + self._PAD_R + max(1, len(labels)) * self._SLOT_W
        self.setMinimumWidth(max(500, min_w))
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._labels:
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return

        PL, PR, PT, PB = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        W = self.width() - PL - PR
        H = self.height() - PT - PB
        total = sum(self._values) or 1
        n = len(self._labels)
        slot_w = max(self._SLOT_W, W // n)
        bar_w = max(14, min(48, slot_w - 14))
        max_v = self._values[0] if self._values else 1

        # Grid + left Y-axis (count)
        STEPS = 4
        painter.setFont(QFont(FONT, 9))
        for i in range(STEPS + 1):
            gy = PT + H - int(H * i / STEPS)
            painter.setPen(QPen(QColor("#f0f0f0"), 1))
            painter.drawLine(PL, gy, PL + W, gy)
            painter.setPen(QPen(QColor("#bbb")))
            painter.drawText(QRect(0, gy - 10, PL - 4, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_v * i / STEPS)))

        # Right Y-axis (cumulative %)
        for i in range(STEPS + 1):
            gy = PT + H - int(H * i / STEPS)
            painter.setPen(QPen(QColor("#aaa")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(PL + W + 6, gy - 10, PR - 8, 20),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{i * 100 // STEPS}%")

        # 80% dashed horizontal reference line
        y80 = PT + H - int(H * 0.8)
        painter.setPen(QPen(QColor(_PARETO_LINE), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(PL, y80, PL + W, y80)
        painter.setPen(QPen(QColor(_PARETO_LINE)))
        painter.setFont(QFont(FONT, 8, QFont.Weight.Bold))
        painter.drawText(QRect(PL + W + 6, y80 - 10, PR - 8, 20),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "80%")

        # Bars + collect cumulative points
        cum_pts: list[tuple[int, int]] = []
        cumulative = 0
        for i, (label, value) in enumerate(zip(self._labels, self._values)):
            bx = PL + i * slot_w + (slot_w - bar_w) // 2
            bar_h = int(H * value / max_v) if max_v else 0
            by = PT + H - bar_h

            if bar_h > 0:
                r = min(5.0, bar_w / 4.0)
                path = QPainterPath()
                path.addRoundedRect(QRectF(bx, by, bar_w, bar_h), r, r)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(_PARETO_BAR)))
                painter.fillRect(QRect(bx, by + int(r) + 1, bar_w,
                                       max(0, bar_h - int(r) - 1)), QColor(_PARETO_BAR))
                painter.drawPath(path)

            if value > 0:
                painter.setPen(QPen(QColor("#444")))
                painter.setFont(QFont(FONT, 8))
                painter.drawText(QRect(bx - 10, by - 14, bar_w + 20, 12),
                                 Qt.AlignmentFlag.AlignCenter, f"{value:,}")

            cumulative += value
            cx_pt = PL + i * slot_w + slot_w // 2
            cy_pt = PT + H - int(H * cumulative / total)
            cum_pts.append((cx_pt, cy_pt))

            # X-axis label (rotated)
            short = label if len(label) <= 12 else label[:11] + "…"
            painter.setPen(QPen(QColor("#777")))
            painter.setFont(QFont(FONT, 8))
            painter.save()
            painter.translate(PL + i * slot_w + slot_w // 2, PT + H + 8)
            painter.rotate(30)
            painter.drawText(0, 0, 130, 14, Qt.AlignmentFlag.AlignLeft, short)
            painter.restore()

        # Cumulative line
        if len(cum_pts) >= 2:
            painter.setPen(QPen(QColor(_PARETO_LINE), 2))
            for i in range(1, len(cum_pts)):
                painter.drawLine(cum_pts[i-1][0], cum_pts[i-1][1],
                                 cum_pts[i][0], cum_pts[i][1])

        # Dots + mark 80% cutoff vertical line
        cumulative = 0
        cutoff_drawn = False
        for i, (px, py) in enumerate(cum_pts):
            painter.setBrush(QBrush(QColor(_PARETO_LINE)))
            painter.setPen(QPen(QColor("white"), 1.5))
            painter.drawEllipse(px - 4, py - 4, 8, 8)
            cumulative += self._values[i]
            if not cutoff_drawn and cumulative / total >= 0.8:
                painter.setPen(QPen(QColor(_PARETO_LINE), 1.5, Qt.PenStyle.DotLine))
                painter.drawLine(px, PT, px, PT + H)
                cutoff_drawn = True

        # Legend
        legend_y = self.height() - 18
        for lx, color, lbl in [
            (PL, _PARETO_BAR, "Số lượng mượn"),
            (PL + 120, _PARETO_LINE, "Tích lũy (%)"),
        ]:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawRoundedRect(QRect(lx, legend_y - 5, 12, 12), 2, 2)
            painter.setPen(QPen(QColor("#555")))
            painter.setFont(QFont(FONT, 9))
            painter.drawText(QRect(lx + 16, legend_y - 8, 100, 18),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)


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

        # ── Row 1: 3D Pie (with unit filter) | Top-5 H4 Horizontal Bar ────────
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        pie_frame, pie_v = _card_frame("Tỉ Lệ Chất Lượng Hàng Hóa Đơn Vị")
        pie_header = QHBoxLayout()
        pie_header.setSpacing(8)
        pie_header.addStretch()
        self._pie_combo = self._make_combo(min_w=165)
        self._pie_combo.currentIndexChanged.connect(self._reload_pie)
        pie_header.addWidget(self._pie_combo)
        pie_v.addLayout(pie_header)
        self._pie = _Pie3DChart()
        pie_v.addWidget(self._pie)
        row1.addWidget(pie_frame, 5)

        self._hbar = _DonutChart()
        row1.addWidget(_card("Tồn Hàng H4 Tại Các Đơn Vị", self._hbar), 5)
        root.addLayout(row1)
        root.addSpacing(20)

        # ── Row 2: Line Chart – full width ──────────────────────────────────
        line_frame, line_v = _card_frame("Dự Báo Hàng Chuyển Thành H4 Theo Thời Gian")
        line_header = QHBoxLayout()
        line_header.setSpacing(8)
        line_header.addStretch()
        self._line_combo = self._make_combo(min_w=150)
        self._line_combo.currentIndexChanged.connect(self._reload_line)
        line_header.addWidget(self._line_combo)
        line_v.addLayout(line_header)
        self._line_chart = _LineChart(height=240)
        line_v.addWidget(self._line_chart)
        root.addWidget(line_frame)
        root.addSpacing(20)

        # ── Row 3: Pareto Chart – full width ────────────────────────────────
        pareto_frame, pareto_v = _card_frame(
            "Phân Tích Pareto – Mặt Hàng Mượn Nhiều Nhất (Quy Tắc 80/20)"
        )
        pareto_header = QHBoxLayout()
        pareto_header.setSpacing(8)
        pareto_header.addStretch()
        self._pareto_combo = self._make_combo(min_w=165)
        self._pareto_combo.currentIndexChanged.connect(self._reload_pareto)
        pareto_header.addWidget(self._pareto_combo)
        pareto_v.addLayout(pareto_header)

        self._pareto = _ParetoChart(height=290)
        pareto_scroll = QScrollArea()
        pareto_scroll.setWidgetResizable(True)
        pareto_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pareto_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pareto_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pareto_scroll.setFixedHeight(300)
        pareto_scroll.setWidget(self._pareto)
        pareto_v.addWidget(pareto_scroll)
        root.addWidget(pareto_frame)
        root.addSpacing(20)

        # ── Row 4: Full-Width Heatmap (toàn cảnh 200 mặt hàng) ─────────────
        fh_frame, fh_v = _card_frame("Tổng Quan Lão Hóa Tất Cả Mặt Hàng")
        fh_filter = QHBoxLayout()
        fh_filter.setSpacing(8)
        fh_filter.addStretch()

        self._fhmap_search = QLineEdit()
        self._fhmap_search.setPlaceholderText("Tìm mặt hàng…")
        self._fhmap_search.setFixedSize(180, 28)
        self._fhmap_search.setFont(QFont(FONT, 10))
        self._fhmap_search.setStyleSheet(_SEARCH_STYLE)
        self._fhmap_search.textChanged.connect(self._reload_full_heatmap)
        fh_filter.addWidget(self._fhmap_search)

        self._fhmap_combo = self._make_combo(min_w=190)
        self._fhmap_combo.currentIndexChanged.connect(self._reload_full_heatmap)
        fh_filter.addWidget(self._fhmap_combo)
        fh_v.addLayout(fh_filter)

        self._full_heatmap = _HeatmapGrid()
        fhmap_scroll = QScrollArea()
        fhmap_scroll.setWidgetResizable(True)
        fhmap_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        fhmap_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        fhmap_scroll.setFrameShape(QFrame.Shape.NoFrame)
        fhmap_scroll.setFixedHeight(540)
        fhmap_scroll.setWidget(self._full_heatmap)
        fh_v.addWidget(fhmap_scroll)
        root.addWidget(fh_frame)
        root.addSpacing(20)

        # ── Row 5: Grouped Bar (Nhập vs Xuất) – full width ─────────────────
        self._grouped = _GroupedBarChart(height=270)
        root.addWidget(_card("So Sánh Nhập / Xuất Theo Tháng (12 tháng gần nhất)",
                             self._grouped))
        root.addSpacing(8)
        root.addStretch()

        self.refresh()

    # ── Shared combo factory ─────────────────────────────────────────────────

    def _make_combo(self, min_w: int = 160) -> QComboBox:
        cb = QComboBox()
        cb.setFixedHeight(28)
        cb.setFont(QFont(FONT, 10))
        cb.setMinimumWidth(min_w)
        cb.setStyleSheet(_COMBO_STYLE)
        return cb

    # ── Refresh ──────────────────────────────────────────────────────────────

    def refresh(self):
        conn = database.get_conn()
        wh_rows = conn.execute(
            "SELECT id, code, name, type FROM warehouses WHERE is_active=1 ORDER BY type DESC, name"
        ).fetchall()

        for combo in (self._pie_combo, self._line_combo, self._pareto_combo):
            prev = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Tất cả", None)
            for r in wh_rows:
                prefix = "Kho" if r["type"] == "TONG" else "ĐV"
                combo.addItem(f"[{prefix}] {r['name']}", r["id"])
            for i in range(combo.count()):
                if combo.itemData(i) == prev:
                    combo.setCurrentIndex(i)
                    break
            combo.blockSignals(False)

        # Full heatmap combo: includes special "Tổng tất cả đơn vị" option
        prev_fh = self._fhmap_combo.currentData()
        self._fhmap_combo.blockSignals(True)
        self._fhmap_combo.clear()
        self._fhmap_combo.addItem("Tất cả", None)
        self._fhmap_combo.addItem("Tổng tất cả đơn vị", "ALL_DON_VI")
        for r in wh_rows:
            prefix = "Kho" if r["type"] == "TONG" else "ĐV"
            self._fhmap_combo.addItem(f"[{prefix}] {r['name']}", r["id"])
        for i in range(self._fhmap_combo.count()):
            if self._fhmap_combo.itemData(i) == prev_fh:
                self._fhmap_combo.setCurrentIndex(i)
                break
        self._fhmap_combo.blockSignals(False)

        self._reload_pie()
        self._reload_line()
        self._reload_grouped()
        self._reload_hbar()
        self._reload_pareto()
        self._reload_full_heatmap()

    # ── Reload helpers ────────────────────────────────────────────────────────

    def _reload_pie(self):
        conn = database.get_conn()
        wh_id = self._pie_combo.currentData()
        params: list = []
        where = "WHERE quantity > 0"
        if wh_id:
            where += " AND warehouse_id = ?"
            params.append(wh_id)
        rows = conn.execute(
            f"SELECT quality_level, SUM(quantity) AS qty FROM inventory {where} GROUP BY quality_level",
            params,
        ).fetchall()
        h: dict[str, int] = {"H1": 0, "H2": 0, "H3": 0, "H4": 0}
        for r in rows:
            if r["quality_level"] in h:
                h[r["quality_level"]] = r["qty"]
        self._pie.load({k: (v, _PIE_COLORS[k]) for k, v in h.items()})

    def _reload_line(self):
        conn = database.get_conn()
        wh_id = self._line_combo.currentData()

        if wh_id:
            # Single unit: one series
            rows = conn.execute("""
                SELECT
                    strftime('%Y-%m',
                        date(i.received_at_unit_date, '+' || t.total_lifespan_months || ' months')
                    ) AS h4_month,
                    SUM(i.quantity) AS qty,
                    w.name AS wh_name
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t ON t.id = i.item_type_id
                WHERE i.is_shared = 0
                  AND i.quality_level IN ('H1','H2','H3')
                  AND i.received_at_unit_date IS NOT NULL
                  AND t.total_lifespan_months > 0
                  AND i.warehouse_id = ?
                GROUP BY h4_month
                ORDER BY h4_month
            """, (wh_id,)).fetchall()
            if rows:
                name = rows[0]["wh_name"]
                series = {name: [(r["h4_month"], r["qty"]) for r in rows if r["h4_month"]]}
            else:
                series = {}
        else:
            # All units: one line per unit (limit to top 8 by total qty)
            rows = conn.execute("""
                SELECT
                    w.id AS wh_id, w.name AS wh_name,
                    strftime('%Y-%m',
                        date(i.received_at_unit_date, '+' || t.total_lifespan_months || ' months')
                    ) AS h4_month,
                    SUM(i.quantity) AS qty
                FROM inventory i
                JOIN warehouses w ON w.id = i.warehouse_id
                JOIN item_types t ON t.id = i.item_type_id
                WHERE i.is_shared = 0
                  AND w.type = 'DON_VI'
                  AND i.quality_level IN ('H1','H2','H3')
                  AND i.received_at_unit_date IS NOT NULL
                  AND t.total_lifespan_months > 0
                GROUP BY w.id, h4_month
                ORDER BY w.name, h4_month
            """).fetchall()

            # Build per-unit series; keep top-8 units by total
            from collections import defaultdict
            unit_data: dict[str, list] = defaultdict(list)
            unit_total: dict[str, int] = defaultdict(int)
            for r in rows:
                if r["h4_month"]:
                    unit_data[r["wh_name"]].append((r["h4_month"], r["qty"]))
                    unit_total[r["wh_name"]] += r["qty"]
            top8 = sorted(unit_total, key=lambda k: unit_total[k], reverse=True)[:8]
            series = {name: unit_data[name] for name in top8 if unit_data[name]}

        self._line_chart.load(series)

    def _reload_grouped(self):
        conn = database.get_conn()
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', t.transaction_date) AS month,
                CASE
                    WHEN t.type IN ('NHAP_KHO', 'NHAP_CHUNG') THEN 'nhap'
                    WHEN t.type IN ('XUAT_KHO', 'MUON') THEN 'xuat'
                    ELSE NULL
                END AS direction,
                SUM(tl.quantity) AS qty
            FROM transactions t
            JOIN transaction_lines tl ON tl.transaction_id = t.id
            WHERE t.type IN ('NHAP_KHO','NHAP_CHUNG','XUAT_KHO','MUON')
              AND t.transaction_date >= date('now', '-12 months')
            GROUP BY month, direction
            ORDER BY month
        """).fetchall()

        # Collect all months in range
        today = datetime.date.today()
        months: list[str] = []
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            months.append(f"{y:04d}-{m:02d}")

        data: dict[str, tuple[int, int]] = {m: (0, 0) for m in months}
        for r in rows:
            mo = r["month"]
            if mo not in data:
                continue
            nhap, xuat = data[mo]
            if r["direction"] == "nhap":
                nhap += r["qty"]
            elif r["direction"] == "xuat":
                xuat += r["qty"]
            data[mo] = (nhap, xuat)

        self._grouped.load(data)

    def _reload_hbar(self):
        conn = database.get_conn()
        rows = conn.execute("""
            SELECT w.name, SUM(i.quantity) AS h4_qty
            FROM inventory i
            JOIN warehouses w ON w.id = i.warehouse_id
            WHERE i.quality_level = 'H4'
              AND i.quantity > 0
            GROUP BY w.id
            ORDER BY h4_qty DESC
            LIMIT 20
        """).fetchall()
        self._hbar.load(
            [r["name"] for r in rows],
            [r["h4_qty"] for r in rows],
        )

    def _reload_full_heatmap(self):
        conn = database.get_conn()
        wh_filter = self._fhmap_combo.currentData()
        q = self._fhmap_search.text().strip().lower()
        params: list = []
        where_parts = ["i.quantity > 0"]
        if wh_filter == "ALL_DON_VI":
            where_parts.append("w.type = 'DON_VI'")
        elif wh_filter is not None:
            where_parts.append("i.warehouse_id = ?")
            params.append(wh_filter)
        where = "WHERE " + " AND ".join(where_parts)
        rows = conn.execute(f"""
            SELECT t.code AS item_code, t.name AS item_name,
                   SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END) AS h1,
                   SUM(CASE WHEN i.quality_level='H2' THEN i.quantity ELSE 0 END) AS h2,
                   SUM(CASE WHEN i.quality_level='H3' THEN i.quantity ELSE 0 END) AS h3,
                   SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END) AS h4
            FROM inventory i
            JOIN item_types t ON t.id = i.item_type_id
            JOIN warehouses w ON w.id = i.warehouse_id
            {where}
            GROUP BY t.id
            HAVING (h1+h2+h3+h4) > 0
            ORDER BY h4 DESC, h3 DESC, (h1+h2+h3+h4) DESC
        """, params).fetchall()
        if q:
            rows = [r for r in rows
                    if q in r["item_name"].lower() or q in r["item_code"].lower()]
        items = [(r["item_code"], r["item_name"], r["h1"], r["h2"], r["h3"], r["h4"])
                 for r in rows]
        self._full_heatmap.load(items)

    def _reload_pareto(self):
        conn = database.get_conn()
        wh_id = self._pareto_combo.currentData()
        params: list = []
        where_parts = ["tx.type = 'MUON'"]
        if wh_id:
            where_parts.append("tx.from_warehouse_id = ?")
            params.append(wh_id)
        where = "WHERE " + " AND ".join(where_parts)
        rows = conn.execute(f"""
            SELECT it.name AS item_name, SUM(tl.quantity) AS qty
            FROM transaction_lines tl
            JOIN transactions tx ON tx.id = tl.transaction_id
            JOIN item_types it ON it.id = tl.item_type_id
            {where}
            GROUP BY it.id
            HAVING qty > 0
            ORDER BY qty DESC
        """, params).fetchall()
        self._pareto.load(
            [r["item_name"] for r in rows],
            [r["qty"] for r in rows],
        )
