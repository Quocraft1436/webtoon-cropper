"""
Style module
- Chứa toàn bộ stylesheet (QSS) dùng trong ứng dụng Webtoon Cropper.
"""

# ── PageThumb ───────────────────────────────────────────────────────────────
PAGE_THUMB_STYLE = """
    QLabel {
        border: 2px solid #3a3a4a;
        border-radius: 4px;
        background: #1e1e2e;
        padding: 4px;
        color: #cdd6f4;
        font-size: 9px;
    }
    QLabel:hover { border-color: #89b4fa; }
"""

# ── PageListWidget ────────────────────────────────────────────────────────
PAGE_LIST_STYLE = """
    QListWidget {
        background: #181825;
        border: 1px solid #313244;
        border-radius: 6px;
        padding: 4px;
    }
    QListWidget::item {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 4px;
        color: #cdd6f4;
        padding: 4px;
        margin: 2px;
        font-size: 10px;
    }
    QListWidget::item:selected {
        background: #313244;
        border-color: #89b4fa;
    }
    QListWidget::item:hover {
        border-color: #6c7086;
    }
"""

# ── CanvasWidget ──────────────────────────────────────────────────────────
CANVAS_WIDGET_STYLE = "background: #11111b;"

# ── CanvasScrollArea ──────────────────────────────────────────────────────
CANVAS_SCROLL_STYLE = """
    QScrollArea { border: none; background: #11111b; }
    QScrollBar:vertical { background: #1e1e2e; width: 8px; }
    QScrollBar::handle:vertical { background: #45475a; border-radius: 4px; }
    QScrollBar:horizontal { background: #1e1e2e; height: 8px; }
    QScrollBar::handle:horizontal { background: #45475a; border-radius: 4px; }
"""

# ── WebtoonCropper (main window) ─────────────────────────────────────────
MAIN_WINDOW_STYLE = """
    QMainWindow { background: #11111b; }
    QWidget { background: #11111b; color: #cdd6f4; font-family: 'JetBrains Mono', monospace; }
    QPushButton {
        background: #1e1e2e;
        color: #cdd6f4;
        border: 1px solid #313244;
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 12px;
    }
    QPushButton:hover { background: #313244; border-color: #89b4fa; }
    QPushButton:pressed { background: #45475a; }
    QPushButton:disabled { color: #45475a; border-color: #1e1e2e; }
    QPushButton#crop_btn {
        background: #1e3a5f;
        border-color: #89b4fa;
        color: #89b4fa;
        font-weight: bold;
    }
    QPushButton#crop_btn:hover { background: #89b4fa; color: #1e1e2e; }
    QLabel#section_label {
        color: #6c7086;
        font-size: 10px;
        padding: 4px 0;
        letter-spacing: 1px;
        font-weight: bold;
    }
    QStatusBar { background: #181825; color: #6c7086; font-size: 11px; }
    QSplitter::handle { background: #313244; width: 1px; }
    QToolBar { background: #181825; border-bottom: 1px solid #313244; spacing: 4px; padding: 4px; }
"""
