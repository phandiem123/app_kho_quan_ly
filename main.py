#!/usr/bin/env python3
"""DCCD - Hệ thống Quản lý Kho, Đơn vị & Niên hạn Hàng hóa"""

import sys
import json
import time
import subprocess
import urllib.request
from threading import Thread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QFrame, QStackedWidget, QScrollArea,
    QProxyStyle, QStyle, QPushButton,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QCursor
import database
from ui.sidebar import Sidebar
from ui.pages.trang_chu import TrangChuPage

FONT = "Segoe UI"
_DEFAULT_MODEL = "llama3.2:1b"   # model nhỏ ~800 MB, tải nhanh
_PLATFORM: str = sys.platform    # tránh Pylance đánh giá tĩnh nhánh Windows

# Trạng thái toàn cục của Ollama: "starting" | "installing" | "pulling" | "ready" | "error"
ollama_status: str = "starting"
ollama_status_msg: str = "Đang khởi động Ollama..."


def _is_ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _find_ollama() -> str | None:
    """Tìm ollama binary trong PATH và các vị trí mặc định trên từng OS."""
    # Thử PATH trước
    which_cmd = "where" if _PLATFORM == "win32" else "which"
    r = subprocess.run([which_cmd, "ollama"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().splitlines()[0]

    # Windows: thư mục cài mặc định
    if _PLATFORM == "win32":
        import os
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Ollama", "ollama.exe"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p

    return None


def _install_ollama_windows() -> bool:
    """Cài Ollama trên Windows qua winget hoặc tải installer trực tiếp."""
    global ollama_status_msg
    import os, tempfile

    # Thử winget
    wg = subprocess.run(["winget", "--version"], capture_output=True, text=True)
    if wg.returncode == 0:
        ollama_status_msg = "Đang cài Ollama qua winget..."
        r = subprocess.run(
            ["winget", "install", "Ollama.Ollama",
             "--accept-source-agreements", "--accept-package-agreements", "-h"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return True

    # Fallback: tải installer .exe
    ollama_status_msg = "Đang tải Ollama installer..."
    url = "https://ollama.com/download/OllamaSetup.exe"
    tmp = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
    try:
        urllib.request.urlretrieve(url, tmp)
        ollama_status_msg = "Đang cài Ollama (silent)..."
        r = subprocess.run([tmp, "/S"], capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def _ensure_ollama():
    global ollama_status, ollama_status_msg

    # Đã chạy rồi?
    if _is_ollama_up():
        ollama_status = "ready"
        return

    cmd = _find_ollama()

    # Chưa cài → cài theo nền tảng
    if not cmd:
        if _PLATFORM == "win32":
            ollama_status = "installing"
            if not _install_ollama_windows():
                ollama_status = "error"
                ollama_status_msg = "Cài Ollama thất bại. Tải tại ollama.com/download"
                return
            # Sau khi cài, refresh PATH bằng cách tìm lại
            time.sleep(3)
            cmd = _find_ollama()
        else:
            # macOS / Linux: dùng Homebrew
            brew = subprocess.run(["which", "brew"], capture_output=True, text=True)
            if brew.returncode != 0:
                ollama_status = "error"
                ollama_status_msg = "Ollama chưa cài. Tải tại ollama.com/download"
                return
            ollama_status = "installing"
            ollama_status_msg = "Đang cài Ollama qua Homebrew..."
            r = subprocess.run(
                [brew.stdout.strip(), "install", "ollama"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                ollama_status = "error"
                ollama_status_msg = "Cài Ollama thất bại. Tải tại ollama.com/download"
                return
            cmd = _find_ollama()

        if not cmd:
            ollama_status = "error"
            ollama_status_msg = "Không tìm thấy ollama sau khi cài."
            return

    # Khởi động ollama serve
    ollama_status_msg = "Đợi Ollama khởi động..."
    try:
        kwargs = {}
        if _PLATFORM == "win32":
            # Ẩn cửa sổ console trên Windows
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [cmd, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
    except Exception as e:
        ollama_status = "error"
        ollama_status_msg = f"Không start được Ollama: {e}"
        return

    # Chờ server sẵn sàng (tối đa 30 giây)
    for _ in range(30):
        time.sleep(1)
        if _is_ollama_up():
            break
    else:
        ollama_status = "error"
        ollama_status_msg = "Ollama không phản hồi sau 30 giây."
        return

    # Kiểm tra model có chưa, nếu chưa thì pull model nhỏ
    try:
        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        data = json.loads(resp.read())
        if not data.get("models"):
            ollama_status = "pulling"
            ollama_status_msg = f"Đang tải model {_DEFAULT_MODEL} (~800 MB)..."
            subprocess.run([cmd, "pull", _DEFAULT_MODEL], capture_output=True)
    except Exception:
        pass

    ollama_status = "ready"
    ollama_status_msg = "Ollama sẵn sàng"


class _FastTipStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 200
        return super().styleHint(hint, option, widget, returnData)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DCCD")
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)
        self.setStyleSheet("background: white;")

        central = QWidget()
        self.setCentralWidget(central)

        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── Sidebar cố định, không co giãn ───────────────────────────────────
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav)
        h.addWidget(self.sidebar)
        h.setStretchFactor(self.sidebar, 0)   # sidebar không stretch

        # Đường kẻ dọc phân cách
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #efefef; border: none;")
        h.addWidget(sep)

        # ── Vùng nội dung (stack các trang) ──────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: white;")
        h.addWidget(self.stack)
        h.setStretchFactor(self.stack, 1)     # content chiếm hết phần còn lại

        # Đăng ký trang
        self._pages: dict[str, int] = {}
        self._add_page("trang_chu", TrangChuPage())

        # Mặc định hiển thị Trang Chủ
        self.stack.setCurrentIndex(self._pages["trang_chu"])

        # ── Nút Chat AI nổi góc phải dưới ───────────────────────────────────
        self._ai_btn = QPushButton("💬 AI", central)
        self._ai_btn.setFixedSize(QSize(72, 48))
        self._ai_btn.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        self._ai_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._ai_btn.setStyleSheet("""
            QPushButton {
                background: #111; color: white;
                border-radius: 24px; border: none;
                font-size: 13px;
            }
            QPushButton:hover { background: #333; }
        """)
        self._ai_btn.setToolTip("Chat với AI Trợ Lý Kho")
        self._ai_btn.clicked.connect(self._open_ai_chat)
        self._ai_btn.raise_()
        self._ai_dlg = None

        # Poll trạng thái Ollama mỗi 2 giây để cập nhật nút
        self._ollama_timer = QTimer(self)
        self._ollama_timer.timeout.connect(self._update_ai_btn)
        self._ollama_timer.start(2000)

    def _update_ai_btn(self):
        status = ollama_status
        if status == "ready":
            self._ai_btn.setText("💬 AI")
            self._ai_btn.setStyleSheet("""
                QPushButton {
                    background: #111; color: white;
                    border-radius: 24px; border: none; font-size: 13px;
                }
                QPushButton:hover { background: #333; }
            """)
            self._ai_btn.setToolTip("Chat với AI Trợ Lý Kho")
            self._ollama_timer.stop()
        elif status == "error":
            self._ai_btn.setText("⚠️ AI")
            self._ai_btn.setStyleSheet("""
                QPushButton {
                    background: #b71c1c; color: white;
                    border-radius: 24px; border: none; font-size: 13px;
                }
                QPushButton:hover { background: #d32f2f; }
            """)
            self._ai_btn.setToolTip(ollama_status_msg)
            self._ollama_timer.stop()
        else:
            dots = ["⏳", "⌛"][int(time.time()) % 2]
            self._ai_btn.setText(dots)
            self._ai_btn.setToolTip(ollama_status_msg)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_ai_btn"):
            cw = self.centralWidget()
            if cw:
                btn = self._ai_btn
                margin = 20
                btn.move(
                    cw.width() - btn.width() - margin,
                    cw.height() - btn.height() - margin,
                )

    def _open_ai_chat(self):
        from ui.ai_chat import AIChatDialog
        if self._ai_dlg is None or not self._ai_dlg.isVisible():
            self._ai_dlg = AIChatDialog(self)
        self._ai_dlg.show()
        self._ai_dlg.raise_()
        self._ai_dlg.activateWindow()

    def _add_page(self, key: str, widget: QWidget):
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        idx = self.stack.addWidget(scroll)
        self._pages[key] = idx

    # Factory dict: key → callable trả về QWidget, import xảy ra lúc gọi
    _LAZY: "dict[str, Callable[[], QWidget]]" = {}

    def _on_nav(self, key: str):
        if key not in self._pages:
            factory = self._LAZY.get(key)
            if factory is None:
                return
            self._add_page(key, factory())
        scroll = self.stack.widget(self._pages[key])
        # _add_page wraps every page in a QScrollArea — get the actual inner widget
        page = scroll.widget() if hasattr(scroll, "widget") else scroll
        if hasattr(page, "refresh"):
            page.refresh()
        self.stack.setCurrentIndex(self._pages[key])


def _register_lazy_pages():
    from ui.pages.nhap_kho import NhapKhoPage
    from ui.pages.xuat_kho import XuatKhoPage
    from ui.pages.luan_chuyen import LuanChuyenPage
    from ui.pages.export_import import ExportImportPage
    from ui.pages.txl import TxlKhoPage, TxlDonViPage
    from ui.pages.thong_ke import ThongKeKhoPage, ThongKeDonViPage, ThongKeSharedPage
    MainWindow._LAZY["kho"] = ThongKeKhoPage
    MainWindow._LAZY["don_vi"] = ThongKeDonViPage
    MainWindow._LAZY["txl_chung"] = ThongKeSharedPage
    MainWindow._LAZY["nhap_kho"] = NhapKhoPage
    MainWindow._LAZY["xuat_kho"] = XuatKhoPage
    MainWindow._LAZY["luan_chuyen"] = LuanChuyenPage
    MainWindow._LAZY["export_import"] = ExportImportPage
    MainWindow._LAZY["txl_kho"] = TxlKhoPage
    MainWindow._LAZY["txl_don_vi"] = TxlDonViPage
    from ui.pages.bieu_do import BieuDoPage
    MainWindow._LAZY["bieu_do"] = BieuDoPage


_register_lazy_pages()


def main():
    # Khởi tạo DB ngay khi app start
    database.get_conn()
    Thread(target=_ensure_ollama, daemon=True).start()

    app = QApplication(sys.argv)
    app.setStyle(_FastTipStyle("Fusion"))
    app.setFont(QFont(FONT, 12))
    app.setStyleSheet("""
        QToolTip {
            background: white;
            color: #111;
            border: 1px solid #ddd;
            border-radius: 12px;
            padding: 14px 18px;
            font-family: "Segoe UI";
            font-size: 13px;
        }
    """)

    window = MainWindow()
    window.show()

    ret = app.exec()
    database.close()
    sys.exit(ret)


if __name__ == "__main__":
    main()
