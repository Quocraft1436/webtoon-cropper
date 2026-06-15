"""
File Open & Drag Handling
- PageThumb: widget hiển thị thumbnail của 1 trang
- PageListWidget: panel trái, danh sách trang, hỗ trợ kéo để sắp xếp lại
- CanvasScrollArea: vùng scroll cho canvas, hỗ trợ kéo-thả file ảnh
- FileOpenHandleMixin: các xử lý mở/thêm/xóa trang & kéo-thả file cho main window
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QLabel, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QScrollArea, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from style import PAGE_THUMB_STYLE, PAGE_LIST_STYLE, CANVAS_SCROLL_STYLE


# ─────────────────────────────────────────────────────────────────────────────
# Page list (left panel) with drag-to-reorder
# ─────────────────────────────────────────────────────────────────────────────
class PageThumb(QLabel):
    def __init__(self, pixmap: QPixmap, filename: str):
        super().__init__()
        self.filename = filename
        self.full_pixmap = pixmap
        thumb = pixmap.scaledToWidth(100, Qt.SmoothTransformation)
        self.setPixmap(thumb)
        self.setFixedSize(110, thumb.height() + 20)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(filename)
        self.setStyleSheet(PAGE_THUMB_STYLE)


class PageListWidget(QListWidget):
    pages_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(4)
        self.setFixedWidth(140)
        self.setStyleSheet(PAGE_LIST_STYLE)
        self.model().rowsMoved.connect(self.pages_changed)

    def add_page(self, pixmap: QPixmap, filename: str):
        item = QListWidgetItem()
        name = Path(filename).name
        short = name[:14] + "…" if len(name) > 15 else name
        item.setText(short)
        item.setData(Qt.UserRole, {"pixmap": pixmap, "filename": filename})
        item.setSizeHint(QSize(130, 80))
        scaled = pixmap.scaledToWidth(50, Qt.SmoothTransformation)
        item.setData(Qt.DecorationRole, scaled)
        self.addItem(item)
        self.pages_changed.emit()

    def get_pixmaps(self) -> list:
        result = []
        for i in range(self.count()):
            data = self.item(i).data(Qt.UserRole)
            result.append(data["pixmap"])
        return result

    def remove_selected(self):
        row = self.currentRow()
        if row >= 0:
            self.takeItem(row)
            self.pages_changed.emit()

    def clear_all(self):
        self.clear()
        self.pages_changed.emit()


# ─────────────────────────────────────────────────────────────────────────────
# Scroll canvas wrapper (kéo-thả file ảnh)
# ─────────────────────────────────────────────────────────────────────────────
class CanvasScrollArea(QScrollArea):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet(CANVAS_SCROLL_STYLE)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
        if paths:
            self.files_dropped.emit(paths)


# ─────────────────────────────────────────────────────────────────────────────
# Mixin: xử lý mở file ảnh / kéo-thả cho main window
# ─────────────────────────────────────────────────────────────────────────────
class FileOpenHandleMixin:
    # ── drag-drop onto page list ──────────────────────────────────────────
    def _list_drag_enter(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            QListWidget.dragEnterEvent(self.page_list, e)

    def _list_drop(self, e: QDropEvent):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls()
                     if u.toLocalFile().lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
            if paths:
                self._add_files(paths)
        else:
            QListWidget.dropEvent(self.page_list, e)

    # ── file operations ───────────────────────────────────────────────────
    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if paths:
            self._add_files(sorted(paths))

    def _add_files(self, paths: list):
        added = 0
        for path in sorted(paths):
            px = QPixmap(path)
            if px.isNull():
                continue
            self.page_list.add_page(px, path)
            added += 1
        if added:
            self.status.showMessage(f"Đã thêm {added} trang.")

    def _remove_page(self):
        self.page_list.remove_selected()

    def _clear_all(self):
        reply = QMessageBox.question(self, "Xóa tất cả", "Xóa tất cả trang và vùng crop?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.page_list.clear_all()
            self.canvas.clear()
            self.btn_crop.setEnabled(False)
            self.rect_count_lbl.setText("0 vùng")
