from __future__ import annotations
import json
import urllib.request
import urllib.error

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QScrollArea, QWidget, QFrame,
    QSizePolicy, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QCursor

import database

FONT = "Segoe UI"
OLLAMA_URL = "http://localhost:11434"


def _build_context() -> str:
    try:
        conn = database.get_conn()

        whs = conn.execute(
            "SELECT name, type FROM warehouses WHERE is_active=1 ORDER BY type, name"
        ).fetchall()
        kho_tong = [r["name"] for r in whs if r["type"] == "TONG"]
        don_vi = [r["name"] for r in whs if r["type"] == "DON_VI"]

        items = conn.execute("""
            SELECT t.name, t.unit_of_measure,
                   COALESCE(SUM(CASE WHEN i.quality_level='H1' THEN i.quantity ELSE 0 END), 0) AS h1,
                   COALESCE(SUM(CASE WHEN i.quality_level='H2' THEN i.quantity ELSE 0 END), 0) AS h2,
                   COALESCE(SUM(CASE WHEN i.quality_level='H3' THEN i.quantity ELSE 0 END), 0) AS h3,
                   COALESCE(SUM(CASE WHEN i.quality_level='H4' THEN i.quantity ELSE 0 END), 0) AS h4,
                   COALESCE(SUM(i.quantity), 0) AS total
            FROM item_types t
            LEFT JOIN inventory i ON i.item_type_id = t.id
                AND i.is_shared = 0 AND i.quantity > 0
            WHERE t.is_active = 1
            GROUP BY t.id
            ORDER BY t.name
        """).fetchall()

        lines = [
            "Bạn là trợ lý AI của hệ thống quản lý kho DCCD.",
            "Nhiệm vụ: trả lời câu hỏi về tồn kho, mặt hàng, đơn vị, quy trình nhập/xuất.",
            "Trả lời ngắn gọn, rõ ràng bằng tiếng Việt.",
            "",
        ]
        if kho_tong:
            lines.append(f"KHO TỔNG ({len(kho_tong)} kho): " + ", ".join(kho_tong))
        if don_vi:
            lines.append(f"ĐƠN VỊ ({len(don_vi)} đơn vị): " + ", ".join(don_vi[:30]))
            if len(don_vi) > 30:
                lines.append(f"  ...và {len(don_vi)-30} đơn vị khác")
        lines.append("")
        lines.append(f"MẶT HÀNG TỒN KHO ({len(items)} loại):")
        for r in items[:80]:
            total = r["total"]
            detail = f"H1={r['h1']}, H2={r['h2']}, H3={r['h3']}, H4={r['h4']}"
            lines.append(f"  {r['name']} ({r['unit_of_measure']}): tổng={total} [{detail}]")
        if len(items) > 80:
            lines.append(f"  ...và {len(items)-80} mặt hàng khác")

        return "\n".join(lines)
    except Exception:
        return "Bạn là trợ lý AI cho hệ thống quản lý kho DCCD. Trả lời bằng tiếng Việt."


class _OllamaWorker(QThread):
    token_ready = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model: str, messages: list):
        super().__init__()
        self._model = model
        self._messages = messages
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            payload = json.dumps({
                "model": self._model,
                "messages": self._messages,
                "stream": True,
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    if self._stopped:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        token = obj.get("message", {}).get("content", "")
                        if token:
                            self.token_ready.emit(token)
                        if obj.get("done"):
                            break
                    except json.JSONDecodeError:
                        pass
        except urllib.error.URLError:
            self.error_occurred.emit(
                f"Không kết nối được Ollama ({OLLAMA_URL}).\n"
                "Hãy cài và chạy Ollama trước:\n"
                "  1. Tải tại ollama.com\n"
                "  2. Chạy: ollama run llama3.2"
            )
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()


class _Bubble(QFrame):
    def __init__(self, is_user: bool, parent=None):
        super().__init__(parent)
        self._text = ""
        self._lbl = QLabel()
        self._lbl.setWordWrap(True)
        self._lbl.setFont(QFont(FONT, 12))
        self._lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 8)
        v.addWidget(self._lbl)
        self.setMaximumWidth(420)

        if is_user:
            self.setStyleSheet(
                "QFrame { background: #111; border-radius: 10px; }"
                " QLabel { color: white; }"
            )
        else:
            self.setStyleSheet(
                "QFrame { background: #f0f0f0; border-radius: 10px; }"
                " QLabel { color: #111; }"
            )

    def set_text(self, text: str):
        self._text = text
        self._lbl.setText(text)

    def append_token(self, token: str):
        self._text += token
        self._lbl.setText(self._text)

    def get_text(self) -> str:
        return self._text


class AIChatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat với AI Trợ Lý Kho")
        self.setMinimumSize(500, 620)
        self.resize(540, 700)
        self.setStyleSheet("background: white;")

        self._messages: list[dict] = []
        self._worker: _OllamaWorker | None = None
        self._cur_bubble: _Bubble | None = None
        self._model = "llama3.2"
        self._context = ""

        self._build_ui()
        QTimer.singleShot(200, self._load_context)

    def _load_context(self):
        self._context = _build_context()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header
        top = QHBoxLayout()
        title = QLabel("AI Trợ Lý Kho")
        title.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #111;")
        top.addWidget(title)
        top.addStretch()

        mdl_lbl = QLabel("Model:")
        mdl_lbl.setFont(QFont(FONT, 11))
        mdl_lbl.setStyleSheet("color: #555;")
        top.addWidget(mdl_lbl)

        self._mdl_combo = QComboBox()
        self._mdl_combo.setFont(QFont(FONT, 11))
        self._mdl_combo.setFixedWidth(150)
        self._mdl_combo.setEditable(True)
        self._mdl_combo.addItems([
            "llama3.2", "llama3.1", "llama3.2:1b",
            "mistral", "qwen2.5", "gemma2",
        ])
        self._mdl_combo.setStyleSheet("""
            QComboBox { border: 1px solid #e0e0e0; border-radius: 6px;
                padding: 2px 8px; background: white; color: #111; }
        """)
        self._mdl_combo.currentTextChanged.connect(
            lambda t: setattr(self, "_model", t.strip() or "llama3.2")
        )
        top.addWidget(self._mdl_combo)

        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.setToolTip("Cập nhật dữ liệu kho")
        btn_refresh.setFont(QFont(FONT, 13))
        btn_refresh.setStyleSheet(
            "QPushButton { border: 1px solid #e0e0e0; border-radius: 6px;"
            " background: white; color: #555; }"
            " QPushButton:hover { background: #f5f5f5; }"
        )
        btn_refresh.clicked.connect(self._load_context)
        top.addWidget(btn_refresh)
        root.addLayout(top)

        # Messages area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #fafafa; border: 1px solid #efefef;"
            " border-radius: 10px; }"
        )

        self._msg_widget = QWidget()
        self._msg_widget.setStyleSheet("background: #fafafa;")
        self._msg_layout = QVBoxLayout(self._msg_widget)
        self._msg_layout.setContentsMargins(12, 12, 12, 12)
        self._msg_layout.setSpacing(10)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_widget)
        root.addWidget(self._scroll, 1)

        # Input
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setFont(QFont(FONT, 12))
        self._input.setFixedHeight(76)
        self._input.setPlaceholderText(
            "Hỏi về tồn kho, mặt hàng, đơn vị...  (Ctrl+Enter để gửi)"
        )
        self._input.setStyleSheet("""
            QTextEdit { border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 6px 10px; background: white; color: #111; }
            QTextEdit:focus { border-color: #999; }
        """)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Gửi")
        self._send_btn.setFixedSize(76, 76)
        self._send_btn.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        self._send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._send_btn.setStyleSheet("""
            QPushButton { background: #111; color: white; border-radius: 8px; border: none; }
            QPushButton:hover { background: #333; }
            QPushButton:disabled { background: #ccc; color: #888; }
        """)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)
        root.addLayout(input_row)

        hint = QLabel("Cần Ollama đang chạy  •  ollama.com")
        hint.setFont(QFont(FONT, 10))
        hint.setStyleSheet("color: #aaa;")
        root.addWidget(hint)

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._on_send()
        else:
            super().keyPressEvent(event)

    def _add_bubble(self, is_user: bool) -> _Bubble:
        bubble = _Bubble(is_user)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_user:
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()
        self._msg_layout.insertLayout(self._msg_layout.count() - 1, row)
        QTimer.singleShot(30, self._scroll_bottom)
        return bubble

    def _scroll_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()

        user_bubble = self._add_bubble(is_user=True)
        user_bubble.set_text(text)
        self._messages.append({"role": "user", "content": text})

        ai_bubble = self._add_bubble(is_user=False)
        ai_bubble.set_text("...")
        self._cur_bubble = ai_bubble
        self._send_btn.setEnabled(False)

        full_msgs = [{"role": "system", "content": self._context}] + self._messages
        self._worker = _OllamaWorker(self._model, full_msgs)
        self._worker.token_ready.connect(self._on_token)
        self._worker.finished.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_token(self, token: str):
        if self._cur_bubble:
            if self._cur_bubble.get_text() == "...":
                self._cur_bubble.set_text("")
            self._cur_bubble.append_token(token)
            QTimer.singleShot(20, self._scroll_bottom)

    def _on_done(self):
        if self._cur_bubble:
            self._messages.append({
                "role": "assistant",
                "content": self._cur_bubble.get_text(),
            })
        self._worker = None
        self._cur_bubble = None
        self._send_btn.setEnabled(True)

    def _on_error(self, msg: str):
        if self._cur_bubble:
            self._cur_bubble.set_text(msg)
            self._cur_bubble.setStyleSheet(
                "QFrame { background: #fff3f3; border-radius: 10px; border: 1px solid #ffcccc; }"
                " QLabel { color: #c00; }"
            )
        self._worker = None
        self._cur_bubble = None
        self._send_btn.setEnabled(True)

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        super().closeEvent(event)
