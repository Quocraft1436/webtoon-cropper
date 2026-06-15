#!/usr/bin/env python3
"""
char_finder_gui.py — GUI frontend cho char_finder.py
Yêu cầu: char_finder.py phải nằm cùng thư mục.

pip install PySide6 torch torchvision tqdm Pillow
python char_finder_gui.py
"""

import sys
import os
import json
import shutil
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
    QProgressBar, QTextEdit, QFileDialog, QFrame, QGridLayout,
    QSplitter, QScrollArea, QSizePolicy, QStackedWidget,
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QObject, QTimer, QPropertyAnimation,
    QEasingCurve, QRect, QSize,
)
from PySide6.QtGui import (
    QPixmap, QImage, QFont, QColor, QPalette, QDragEnterEvent,
    QDropEvent, QPainter, QPen, QBrush, QLinearGradient, QIcon,
    QFontDatabase,
)


# ── Colour tokens ──────────────────────────────────────────────────────────────

BG0  = "#0e0f13"   # deepest background
BG1  = "#14161c"   # panel background
BG2  = "#1c1f28"   # card / widget background
BG3  = "#252935"   # hover / raised
ACC  = "#7c6af7"   # purple accent (primary)
ACC2 = "#a78bfa"   # lighter purple
ACE  = "#34d399"   # emerald green (success / match)
ACW  = "#f59e0b"   # amber (warning / training)
ACR  = "#f87171"   # red (error)
TXT  = "#e2e8f0"   # primary text
TXT2 = "#8892a4"   # secondary text
BOR  = "#2a2f3e"   # border


STYLE = f"""
QMainWindow, QWidget {{
    background: {BG0};
    color: {TXT};
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
}}

/* ── Drop zones ── */
DropZone {{
    background: {BG2};
    border: 2px dashed {BOR};
    border-radius: 12px;
    color: {TXT2};
}}
DropZone[active=true] {{
    border-color: {ACC};
    background: #1e1c3a;
}}
DropZone[filled=true] {{
    border-color: {ACE};
    border-style: solid;
    background: #0f2420;
}}

/* ── Buttons ── */
QPushButton {{
    background: {BG3};
    color: {TXT};
    border: 1px solid {BOR};
    border-radius: 8px;
    padding: 8px 18px;
    font-family: inherit;
    font-size: 13px;
}}
QPushButton:hover {{
    background: #2e3448;
    border-color: {ACC};
    color: {ACC2};
}}
QPushButton:pressed {{
    background: {ACC};
    color: #fff;
    border-color: {ACC};
}}
QPushButton:disabled {{
    color: #444;
    border-color: #222;
    background: {BG1};
}}

QPushButton#primary {{
    background: {ACC};
    color: #fff;
    border: none;
    font-size: 13px;
    padding: 10px 24px;
}}
QPushButton#primary:hover {{
    background: {ACC2};
    color: #fff;
}}
QPushButton#primary:disabled {{
    background: #2d2d45;
    color: #555;
}}

QPushButton#danger {{
    background: transparent;
    color: {ACR};
    border: 1px solid {ACR};
}}
QPushButton#danger:hover {{
    background: {ACR};
    color: #fff;
}}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BG3};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: {ACC};
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {ACC};
    border-radius: 2px;
}}

/* ── Spinboxes ── */
QSpinBox, QDoubleSpinBox {{
    background: {BG2};
    border: 1px solid {BOR};
    border-radius: 6px;
    padding: 4px 8px;
    color: {TXT};
    font-family: inherit;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACC};
}}

/* ── Progress bar ── */
QProgressBar {{
    background: {BG2};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACC}, stop:1 {ACE});
    border-radius: 4px;
}}

/* ── Log textarea ── */
QTextEdit {{
    background: {BG1};
    border: 1px solid {BOR};
    border-radius: 8px;
    color: {TXT2};
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
    padding: 8px;
    selection-background-color: {ACC};
}}

/* ── Labels ── */
QLabel {{
    color: {TXT};
    background: transparent;
}}
QLabel#heading {{
    font-size: 18px;
    color: {TXT};
    font-weight: bold;
    letter-spacing: 1px;
}}
QLabel#sub {{
    color: {TXT2};
    font-size: 12px;
}}
QLabel#stat {{
    color: {ACE};
    font-size: 22px;
    font-weight: bold;
}}
QLabel#statLabel {{
    color: {TXT2};
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

/* ── Frames / dividers ── */
QFrame[role=divider] {{
    color: {BOR};
    background: {BOR};
    max-height: 1px;
}}
QFrame[role=card] {{
    background: {BG2};
    border: 1px solid {BOR};
    border-radius: 10px;
}}

/* ── Scroll ── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
}}
QScrollBar::handle:vertical {{
    background: {BOR};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


# ── Drop zone widget ───────────────────────────────────────────────────────────

class DropZone(QFrame):
    path_changed = Signal(str)

    def __init__(self, label: str, accept_dir: bool = True, parent=None):
        super().__init__(parent)
        self.accept_dir = accept_dir
        self._path = ""
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("active", False)
        self.setProperty("filled", False)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(4)

        self.icon_lbl = QLabel("📂" if accept_dir else "📄")
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("font-size: 26px; background: transparent;")

        self.main_lbl = QLabel(label)
        self.main_lbl.setAlignment(Qt.AlignCenter)
        self.main_lbl.setStyleSheet(f"color: {TXT2}; font-size: 12px; background: transparent;")

        self.path_lbl = QLabel("")
        self.path_lbl.setAlignment(Qt.AlignCenter)
        self.path_lbl.setWordWrap(True)
        self.path_lbl.setStyleSheet(f"color: {ACE}; font-size: 11px; background: transparent;")

        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.main_lbl)
        lay.addWidget(self.path_lbl)

    def mousePressEvent(self, event):
        if self.accept_dir:
            p = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            p, _ = QFileDialog.getOpenFileName(self, "Select file", filter="Model (*.pth)")
        if p:
            self.set_path(p)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("active", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("active", False)
        urls = event.mimeData().urls()
        if urls:
            p = urls[0].toLocalFile()
            self.set_path(p)

    def set_path(self, p: str):
        self._path = p
        name = Path(p).name
        self.path_lbl.setText(name)
        self.main_lbl.setStyleSheet(f"color: {TXT2}; font-size: 11px; background: transparent;")
        self.setProperty("filled", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self.path_changed.emit(p)

    def clear(self):
        self._path = ""
        self.path_lbl.setText("")
        self.setProperty("filled", False)
        self.style().unpolish(self)
        self.style().polish(self)

    @property
    def path(self) -> str:
        return self._path


# ── Worker thread ──────────────────────────────────────────────────────────────

class Worker(QObject):
    log       = Signal(str)
    progress  = Signal(int, int)   # current, total
    finished  = Signal(dict)       # result dict
    error     = Signal(str)

    def __init__(self, mode: str, kwargs: dict):
        super().__init__()
        self.mode   = mode
        self.kwargs = kwargs
        self._stop  = False

    def run(self):
        try:
            if self.mode == "train":
                self._train()
            elif self.mode == "scan":
                self._scan()
            elif self.mode == "run":
                self._train()
                if not self._stop:
                    self._scan()
        except Exception as e:
            self.error.emit(str(e))

    # ── redirect char_finder internals ──

    def _train(self):
        # Import lazily so GUI starts fast
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "char_finder", Path(__file__).parent / "char_finder.py")
        cf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cf)

        # Monkey-patch tqdm to emit progress signals
        import tqdm as tqdm_mod
        orig_tqdm = tqdm_mod.tqdm

        worker_ref = self

        class SigTqdm(orig_tqdm):
            def update(self, n=1):
                super().update(n)
                worker_ref.progress.emit(self.n, self.total or 1)

        tqdm_mod.tqdm = SigTqdm

        # Patch print to log signal
        import builtins
        orig_print = builtins.print
        def sig_print(*args, **kw):
            msg = " ".join(str(a) for a in args)
            worker_ref.log.emit(msg)
            orig_print(*args, **kw)
        builtins.print = sig_print

        try:
            k = self.kwargs
            cf.train(
                ref_dir    = Path(k["ref"]),
                source_dir = Path(k["source"]) if k.get("source") else None,
                model_path = Path(k["model"]),
                epochs     = k.get("epochs", 15),
            )
        finally:
            builtins.print = orig_print
            tqdm_mod.tqdm = orig_tqdm

    def _scan(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "char_finder", Path(__file__).parent / "char_finder.py")
        cf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cf)

        import tqdm as tqdm_mod
        orig_tqdm = tqdm_mod.tqdm
        worker_ref = self

        class SigTqdm(orig_tqdm):
            def update(self, n=1):
                super().update(n)
                worker_ref.progress.emit(self.n, self.total or 1)

        tqdm_mod.tqdm = SigTqdm

        import builtins
        orig_print = builtins.print
        matched_count = [0]

        def sig_print(*args, **kw):
            msg = " ".join(str(a) for a in args)
            worker_ref.log.emit(msg)
            if "Matched" in msg:
                try:
                    matched_count[0] = int(msg.split(":")[1].strip().split()[0].replace(",",""))
                except Exception:
                    pass
            orig_print(*args, **kw)
        builtins.print = sig_print

        try:
            k = self.kwargs
            cf.scan(
                model_path = Path(k["model"]),
                source_dir = Path(k["source"]),
                output_dir = Path(k["output"]),
                threshold  = k.get("threshold", 0.75),
                dry_run    = k.get("dry_run", False),
            )
            self.finished.emit({"matched": matched_count[0]})
        finally:
            builtins.print = orig_print
            tqdm_mod.tqdm = orig_tqdm


# ── Stat card ──────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, label: str, value: str = "—", color: str = ACE):
        super().__init__()
        self.setProperty("role", "card")
        lay = QVBoxLayout(self)
        lay.setSpacing(2)
        lay.setContentsMargins(16, 12, 16, 12)

        self.val_lbl = QLabel(value)
        self.val_lbl.setObjectName("stat")
        self.val_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; background: transparent;")
        self.val_lbl.setAlignment(Qt.AlignCenter)

        lbl = QLabel(label.upper())
        lbl.setObjectName("statLabel")
        lbl.setAlignment(Qt.AlignCenter)

        lay.addWidget(self.val_lbl)
        lay.addWidget(lbl)

    def set_value(self, v: str):
        self.val_lbl.setText(v)


# ── Main window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("char_finder  ·  Anime Character Scanner")
        self.setMinimumSize(880, 660)
        self.resize(1020, 720)
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Left sidebar ──
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"background: {BG1}; border-right: 1px solid {BOR};")
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(16, 24, 16, 24)
        sb_lay.setSpacing(8)

        logo = QLabel("⬡ CHAR\nFINDER")
        logo.setStyleSheet(f"""
            color: {ACC2}; font-size: 20px; font-weight: bold;
            letter-spacing: 3px; line-height: 1.3;
            background: transparent;
        """)
        sb_lay.addWidget(logo)

        div = QFrame(); div.setProperty("role", "divider")
        div.setFixedHeight(1); div.setStyleSheet(f"background: {BOR};")
        sb_lay.addWidget(div)
        sb_lay.addSpacing(8)

        # Mode buttons
        self.btn_train = self._mode_btn("TRAIN",  "🧠")
        self.btn_scan  = self._mode_btn("SCAN",   "🔍")
        self.btn_run   = self._mode_btn("RUN ALL","⚡")
        for b in [self.btn_train, self.btn_scan, self.btn_run]:
            sb_lay.addWidget(b)
            b.clicked.connect(self._on_mode_click)

        sb_lay.addStretch()

        # ── Stats in sidebar ──
        sb_lay.addWidget(QLabel("RESULTS").setObjectName("statLabel") or QLabel(""))
        self.stat_matched = StatCard("matched", "—", ACE)
        self.stat_scanned = StatCard("scanned", "—", TXT2)
        sb_lay.addWidget(self.stat_matched)
        sb_lay.addWidget(self.stat_scanned)

        main.addWidget(sidebar)

        # ── Right content ──
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(28, 24, 28, 20)
        content_lay.setSpacing(16)

        # Heading
        self.heading = QLabel("Train — Teach the character")
        self.heading.setObjectName("heading")
        content_lay.addWidget(self.heading)

        sub = QLabel("Drag folders onto the drop zones, or click to browse.")
        sub.setObjectName("sub")
        content_lay.addWidget(sub)

        # ── Stacked panels for different modes ──
        self.stack = QStackedWidget()

        # Panel 0: Train
        self.stack.addWidget(self._build_train_panel())
        # Panel 1: Scan
        self.stack.addWidget(self._build_scan_panel())
        # Panel 2: Run all
        self.stack.addWidget(self._build_run_panel())

        content_lay.addWidget(self.stack)

        # ── Progress ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        content_lay.addWidget(self.progress_bar)

        # ── Log ──
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(180)
        self.log.setPlaceholderText("Logs will appear here…")
        content_lay.addWidget(self.log)

        # ── Action buttons ──
        btn_row = QHBoxLayout()
        self.btn_go   = QPushButton("▶  Run")
        self.btn_go.setObjectName("primary")
        self.btn_clear = QPushButton("Clear log")
        self.btn_go.clicked.connect(self._run)
        self.btn_clear.clicked.connect(self.log.clear)
        btn_row.addWidget(self.btn_go)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        content_lay.addLayout(btn_row)

        main.addWidget(content, 1)

        # Default mode: train
        self._activate_mode(0)

    def _mode_btn(self, text: str, icon: str) -> QPushButton:
        b = QPushButton(f"  {icon}  {text}")
        b.setCheckable(True)
        b.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: transparent;
                border: none;
                color: {TXT2};
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {BG3};
                color: {TXT};
            }}
            QPushButton:checked {{
                background: {BG3};
                color: {ACC2};
                border-left: 3px solid {ACC};
            }}
        """)
        return b

    def _on_mode_click(self):
        sender = self.sender()
        for i, b in enumerate([self.btn_train, self.btn_scan, self.btn_run]):
            b.setChecked(b is sender)
            if b is sender:
                self._activate_mode(i)

    def _activate_mode(self, idx: int):
        self.stack.setCurrentIndex(idx)
        heads = [
            "Train — Teach the character",
            "Scan — Find in large dataset",
            "Run All — Train then scan",
        ]
        self.heading.setText(heads[idx])
        [self.btn_train, self.btn_scan, self.btn_run][idx].setChecked(True)

    # ── Panel builders ─────────────────────────────────────────────────────────

    def _build_train_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(0,0,0,0)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.dz_ref    = DropZone("Drop reference image folder here\n(positive samples — your character)")
        self.dz_src_tr = DropZone("Drop large image folder here\n(used for negative sampling)")
        self.dz_model_out = DropZone("Drop output model path here\n(or set save location)", accept_dir=True)

        grid.addWidget(self._zone_wrap("Reference images", self.dz_ref), 0, 0)
        grid.addWidget(self._zone_wrap("Source (negatives)", self.dz_src_tr), 0, 1)
        grid.addWidget(self._zone_wrap("Model save folder", self.dz_model_out), 1, 0)

        # Epochs control
        epoch_w = QFrame(); epoch_w.setProperty("role", "card")
        ep_lay = QVBoxLayout(epoch_w)
        ep_lay.setContentsMargins(14,12,14,12)
        ep_lay.addWidget(QLabel("Epochs"))
        row = QHBoxLayout()
        self.epoch_slider = QSlider(Qt.Horizontal)
        self.epoch_slider.setRange(5, 50)
        self.epoch_slider.setValue(15)
        self.epoch_val = QLabel("15")
        self.epoch_val.setStyleSheet(f"color: {ACW}; font-weight: bold; background:transparent;")
        self.epoch_slider.valueChanged.connect(lambda v: self.epoch_val.setText(str(v)))
        row.addWidget(self.epoch_slider)
        row.addWidget(self.epoch_val)
        ep_lay.addLayout(row)
        grid.addWidget(epoch_w, 1, 1)

        lay.addLayout(grid)
        lay.addStretch()
        return w

    def _build_scan_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(0,0,0,0)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.dz_model_in = DropZone("Drop trained model (.pth) here", accept_dir=False)
        self.dz_src_sc   = DropZone("Drop source image folder here\n(the 15k images)")
        self.dz_out_sc   = DropZone("Drop output folder here\n(matched images will be moved here)")

        grid.addWidget(self._zone_wrap("Trained model", self.dz_model_in), 0, 0)
        grid.addWidget(self._zone_wrap("Source folder", self.dz_src_sc), 0, 1)
        grid.addWidget(self._zone_wrap("Output folder", self.dz_out_sc), 1, 0)

        # Threshold control
        thresh_w = QFrame(); thresh_w.setProperty("role", "card")
        th_lay = QVBoxLayout(thresh_w)
        th_lay.setContentsMargins(14,12,14,12)
        th_lay.addWidget(QLabel("Confidence threshold"))
        row = QHBoxLayout()
        self.thresh_slider = QSlider(Qt.Horizontal)
        self.thresh_slider.setRange(0, 100)
        self.thresh_slider.setValue(75)
        self.thresh_val = QLabel("0.75")
        self.thresh_val.setStyleSheet(f"color: {ACE}; font-weight: bold; background:transparent;")
        self.thresh_slider.valueChanged.connect(
            lambda v: self.thresh_val.setText(f"{v/100:.2f}"))
        row.addWidget(self.thresh_slider)
        row.addWidget(self.thresh_val)
        th_lay.addLayout(row)

        dry_row = QHBoxLayout()
        self.dry_btn = QPushButton("Dry run (preview only, no move)")
        self.dry_btn.setCheckable(True)
        self.dry_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {BOR};
                border-radius: 6px; padding: 6px 14px;
                color: {TXT2}; font-size: 12px;
            }}
            QPushButton:checked {{
                background: #2a1f3d; border-color: {ACC};
                color: {ACC2};
            }}
        """)
        dry_row.addWidget(self.dry_btn)
        dry_row.addStretch()
        th_lay.addLayout(dry_row)

        grid.addWidget(thresh_w, 1, 1)
        lay.addLayout(grid)
        lay.addStretch()
        return w

    def _build_run_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(0,0,0,0)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.dz_ref_r   = DropZone("Reference images\n(character to learn)")
        self.dz_src_r   = DropZone("Source folder\n(15k images to scan)")
        self.dz_out_r   = DropZone("Output folder\n(matched images moved here)")

        grid.addWidget(self._zone_wrap("Reference images", self.dz_ref_r), 0, 0)
        grid.addWidget(self._zone_wrap("Source folder", self.dz_src_r), 0, 1)
        grid.addWidget(self._zone_wrap("Output folder", self.dz_out_r), 1, 0)

        # Params card
        params_w = QFrame(); params_w.setProperty("role", "card")
        p_lay = QGridLayout(params_w)
        p_lay.setContentsMargins(14,12,14,12)
        p_lay.setSpacing(8)

        p_lay.addWidget(QLabel("Epochs"), 0, 0)
        self.run_epoch_slider = QSlider(Qt.Horizontal)
        self.run_epoch_slider.setRange(5, 50)
        self.run_epoch_slider.setValue(15)
        self.run_epoch_val = QLabel("15")
        self.run_epoch_val.setStyleSheet(f"color: {ACW}; font-weight: bold; background:transparent;")
        self.run_epoch_slider.valueChanged.connect(lambda v: self.run_epoch_val.setText(str(v)))
        p_lay.addWidget(self.run_epoch_slider, 0, 1)
        p_lay.addWidget(self.run_epoch_val, 0, 2)

        p_lay.addWidget(QLabel("Threshold"), 1, 0)
        self.run_thresh_slider = QSlider(Qt.Horizontal)
        self.run_thresh_slider.setRange(0, 100)
        self.run_thresh_slider.setValue(75)
        self.run_thresh_val = QLabel("0.75")
        self.run_thresh_val.setStyleSheet(f"color: {ACE}; font-weight: bold; background:transparent;")
        self.run_thresh_slider.valueChanged.connect(
            lambda v: self.run_thresh_val.setText(f"{v/100:.2f}"))
        p_lay.addWidget(self.run_thresh_slider, 1, 1)
        p_lay.addWidget(self.run_thresh_val, 1, 2)

        grid.addWidget(params_w, 1, 1)
        lay.addLayout(grid)
        lay.addStretch()
        return w

    def _zone_wrap(self, label: str, zone: DropZone) -> QFrame:
        f = QFrame()
        lay = QVBoxLayout(f)
        lay.setSpacing(4)
        lay.setContentsMargins(0,0,0,0)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TXT2}; font-size: 11px; letter-spacing: 1px; background: transparent;")
        lay.addWidget(lbl)
        lay.addWidget(zone)
        return f

    # ── Runner ─────────────────────────────────────────────────────────────────

    def _run(self):
        if self._thread and self._thread.isRunning():
            self._append_log("[WARN]  Already running.")
            return

        mode = ["train", "scan", "run"][self.stack.currentIndex()]
        kwargs = {}

        if mode == "train":
            if not self.dz_ref.path:
                self._append_log("[ERROR] Reference folder required.")
                return
            kwargs = {
                "ref":    self.dz_ref.path,
                "source": self.dz_src_tr.path or None,
                "model":  str(Path(self.dz_model_out.path or ".") / "char_model.pth"),
                "epochs": self.epoch_slider.value(),
            }
        elif mode == "scan":
            if not self.dz_model_in.path or not self.dz_src_sc.path or not self.dz_out_sc.path:
                self._append_log("[ERROR] Model, source, and output folders required.")
                return
            kwargs = {
                "model":     self.dz_model_in.path,
                "source":    self.dz_src_sc.path,
                "output":    self.dz_out_sc.path,
                "threshold": self.thresh_slider.value() / 100,
                "dry_run":   self.dry_btn.isChecked(),
            }
        elif mode == "run":
            if not self.dz_ref_r.path or not self.dz_src_r.path or not self.dz_out_r.path:
                self._append_log("[ERROR] All three folders required for Run All.")
                return
            kwargs = {
                "ref":       self.dz_ref_r.path,
                "source":    self.dz_src_r.path,
                "output":    self.dz_out_r.path,
                "model":     str(Path(self.dz_src_r.path).parent / "char_model.pth"),
                "epochs":    self.run_epoch_slider.value(),
                "threshold": self.run_thresh_slider.value() / 100,
            }

        self.log.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_go.setEnabled(False)
        self.btn_go.setText("⏳  Running…")
        self.stat_matched.set_value("—")
        self.stat_scanned.set_value("—")

        self._worker = Worker(mode, kwargs)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)
        self._thread.start()

    def _append_log(self, msg: str):
        colors = {
            "[ERROR]": ACR, "[WARN]": ACW, "[INFO]": TXT2,
            "[SAVED]": ACE, "[TRAIN]": ACC2, "[DEVICE]": ACC,
            "Matched": ACE,
        }
        color = TXT2
        for k, c in colors.items():
            if k in msg:
                color = c
                break
        self.log.append(f'<span style="color:{color};">{msg}</span>')

    def _on_progress(self, cur: int, total: int):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(cur)
            self.stat_scanned.set_value(f"{cur:,}")

    def _on_finished(self, result: dict):
        matched = result.get("matched", 0)
        self.stat_matched.set_value(str(matched))
        self._append_log(f"[DONE]  Finished. Matched: {matched}")

    def _on_error(self, msg: str):
        self._append_log(f"[ERROR] {msg}")

    def _on_thread_done(self):
        self.btn_go.setEnabled(True)
        self.btn_go.setText("▶  Run")
        self.progress_bar.setVisible(False)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setApplicationName("char_finder")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
