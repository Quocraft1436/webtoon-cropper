"""
Webtoon Cropper Tool (Enhanced)
- Drag files to merge vertically
- Ctrl+drag to reorder pages
- Draw rect selections with numbered labels
- Zoom (Mouse Wheel) + Pan (Middle Mouse Drag)
- Group-based cropping with auto-folder export
"""
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QMessageBox, QStatusBar,
    QSizePolicy, QToolBar, QInputDialog, QMenu
)
from PySide6.QtCore import (
    Qt, QRect, QPoint, Signal
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QPixmap,
    QMouseEvent, QPaintEvent, QFontMetrics, QWheelEvent
)

from style import MAIN_WINDOW_STYLE, CANVAS_WIDGET_STYLE
from file_open_handle import PageListWidget, CanvasScrollArea, FileOpenHandleMixin
from file_export_handle import FileExportHandleMixin


#─────────────────────────────────────────────────────────────────────────────
#Data
#─────────────────────────────────────────────────────────────────────────────
class CropRect:
    def __init__(self, rect: QRect, index: int, group: str = "Mặc định"):
        self.rect = QRect(rect)
        self.index = index  # display number
        self.group = group

    def contains(self, point: QPoint) -> bool:
        return self.rect.contains(point)

#─────────────────────────────────────────────────────────────────────────────
#Canvas: merged image + rect drawing + Zoom/Pan
#─────────────────────────────────────────────────────────────────────────────
class CanvasWidget(QWidget):
    status_msg = Signal(str)
    rect_changed = Signal()

    def __init__(self):
        super().__init__()
        self.merged: QPixmap | None = None
        self.crop_rects: list[CropRect] = []
        self.drawing = False
        self.draw_start: QPoint | None = None
        self.draw_current: QPoint | None = None
        self.hover_rect_idx: int = -1
        self.selected_rect_idx: int = -1

        self.scale = 1.0
        self.offset = QPoint(0, 0)
        self.panning = False
        self.pan_start: QPoint | None = None

        self.current_group = "Mặc định"
        self.get_groups = None  # Will be set by main window

        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(400, 300)
        self.setCursor(Qt.CrossCursor)
        self.setStyleSheet(CANVAS_WIDGET_STYLE)

    # ── image management ──────────────────────────────────────────────────
    def set_merged(self, pixmap: QPixmap):
        self.merged = pixmap
        self.crop_rects.clear()
        self.selected_rect_idx = -1
        self._fit_to_view()
        self.update()

    def clear(self):
        self.merged = None
        self.crop_rects.clear()
        self.selected_rect_idx = -1
        self.update()

    def _fit_to_view(self):
        if not self.merged:
            return
        w, h = self.width(), self.height()
        iw, ih = self.merged.width(), self.merged.height()
        self.scale = min((w - 40) / iw, (h - 40) / ih, 1.0)
        dw = int(iw * self.scale)
        dh = int(ih * self.scale)
        self.offset = QPoint((w - dw) // 2, (h - dh) // 2)

    # ── coord helpers ─────────────────────────────────────────────────────
    def _canvas_to_img(self, pt: QPoint) -> QPoint:
        return QPoint(
            int((pt.x() - self.offset.x()) / self.scale),
            int((pt.y() - self.offset.y()) / self.scale),
        )

    def _img_to_canvas(self, pt: QPoint) -> QPoint:
        return QPoint(
            int(pt.x() * self.scale + self.offset.x()),
            int(pt.y() * self.scale + self.offset.y()),
        )

    def _rect_to_canvas(self, r: QRect) -> QRect:
        tl = self._img_to_canvas(r.topLeft())
        br = self._img_to_canvas(r.bottomRight())
        return QRect(tl, br)

    def _next_index(self) -> int:
        used = {cr.index for cr in self.crop_rects}
        i = 1
        while i in used:
            i += 1
        return i

    # ── mouse & wheel ─────────────────────────────────────────────────────
    def wheelEvent(self, e: QWheelEvent):
        if not self.merged:
            return
        delta = e.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        new_scale = max(0.1, min(5.0, self.scale * factor))

        mouse_pos = e.position().toPoint()
        img_pos = self._canvas_to_img(mouse_pos)

        self.scale = new_scale
        new_canvas_pos = self._img_to_canvas(img_pos)
        self.offset += (mouse_pos - new_canvas_pos)
        self.update()

    def mousePressEvent(self, e: QMouseEvent):
        if not self.merged:
            return

        if e.button() == Qt.MiddleButton:
            self.panning = True
            self.pan_start = e.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if e.button() == Qt.LeftButton:
            img_pt = self._canvas_to_img(e.position().toPoint())
            clicked_idx = -1
            for i, cr in enumerate(self.crop_rects):
                if cr.contains(img_pt):
                    clicked_idx = i
                    break

            if clicked_idx >= 0:
                self.selected_rect_idx = clicked_idx
                cr = self.crop_rects[clicked_idx]
                self.status_msg.emit(f"Đã chọn vùng #{cr.index} (Nhóm: {cr.group}) - Chuột phải để đổi nhóm/xóa")
            else:
                self.selected_rect_idx = -1
                self.drawing = True
                self.draw_start = img_pt
                self.draw_current = img_pt
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent):
        if not self.merged:
            return

        if self.panning:
            delta = e.position().toPoint() - self.pan_start
            self.offset += delta
            self.pan_start = e.position().toPoint()
            self.update()
            return

        img_pt = self._canvas_to_img(e.position().toPoint())
        if self.drawing:
            self.draw_current = img_pt
            self.update()
        else:
            old = self.hover_rect_idx
            self.hover_rect_idx = -1
            for i, cr in enumerate(self.crop_rects):
                if cr.contains(img_pt):
                    self.hover_rect_idx = i
                    break
            if old != self.hover_rect_idx:
                self.update()

            if self.hover_rect_idx >= 0:
                self.setCursor(Qt.PointingHandCursor)
                if self.hover_rect_idx != self.selected_rect_idx:
                    cr = self.crop_rects[self.hover_rect_idx]
                    self.status_msg.emit(f"Click để chọn vùng #{cr.index} (Nhóm: {cr.group})")
            else:
                self.setCursor(Qt.CrossCursor)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if not self.merged:
            return

        if e.button() == Qt.MiddleButton:
            self.panning = False
            self.setCursor(Qt.CrossCursor)
            return

        if e.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            end_pt = self._canvas_to_img(e.position().toPoint())
            rect = QRect(self.draw_start, end_pt).normalized()

            if rect.width() > 5 and rect.height() > 5:
                img_rect = QRect(0, 0, self.merged.width(), self.merged.height())
                rect = rect.intersected(img_rect)
                cr = CropRect(rect, self._next_index(), self.current_group)
                self.crop_rects.append(cr)
                self.selected_rect_idx = len(self.crop_rects) - 1
                self.status_msg.emit(f"Đã thêm vùng #{cr.index} vào nhóm '{cr.group}'. Tổng: {len(self.crop_rects)} vùng.")

            self.draw_start = None
            self.draw_current = None
            self.update()
            self.rect_changed.emit()

    def contextMenuEvent(self, e):
        if not self.merged:
            return
        img_pt = self._canvas_to_img(e.pos())
        for i, cr in enumerate(self.crop_rects):
            if cr.contains(img_pt):
                menu = QMenu(self)

                del_action = menu.addAction("Xóa vùng này")
                del_action.triggered.connect(lambda: self._delete_rect(i))

                if self.get_groups:
                    groups = self.get_groups()
                    if groups:
                        group_menu = menu.addMenu("Chuyển sang nhóm")
                        for g in groups:
                            action = group_menu.addAction(g)
                            action.triggered.connect(lambda checked, idx=i, grp=g: self._change_rect_group(idx, grp))

                menu.exec(e.globalPos())
                return

    def _delete_rect(self, idx):
        self.crop_rects.pop(idx)
        self._renumber()
        self.selected_rect_idx = -1
        self.status_msg.emit(f"Đã xóa vùng. Còn {len(self.crop_rects)} vùng.")
        self.update()
        self.rect_changed.emit()

    def _change_rect_group(self, idx, new_group):
        self.crop_rects[idx].group = new_group
        self.status_msg.emit(f"Đã chuyển vùng #{self.crop_rects[idx].index} sang nhóm '{new_group}'.")
        self.update()
        self.rect_changed.emit()

    def _renumber(self):
        for i, cr in enumerate(self.crop_rects):
            cr.index = i + 1

    def resizeEvent(self, e):
        self._fit_to_view()
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────
    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#11111b"))

        if not self.merged:
            p.setPen(QColor("#45475a"))
            p.setFont(QFont("monospace", 12))
            p.drawText(self.rect(), Qt.AlignCenter, "Kéo thả ảnh vào đây\nhoặc dùng bảng bên trái")
            return

        iw, ih = self.merged.width(), self.merged.height()
        dw, dh = int(iw * self.scale), int(ih * self.scale)
        dst = QRect(self.offset.x(), self.offset.y(), dw, dh)
        p.drawPixmap(dst, self.merged)

        for i, cr in enumerate(self.crop_rects):
            cr_canvas = self._rect_to_canvas(cr.rect)
            is_hover = (i == self.hover_rect_idx)
            is_selected = (i == self.selected_rect_idx)

            if is_selected:
                fill_color = QColor(249, 226, 175, 60)
            elif is_hover:
                fill_color = QColor(239, 83, 80, 50)
            else:
                fill_color = QColor(137, 180, 250, 35)
            p.fillRect(cr_canvas, fill_color)

            if is_selected:
                border_color = QColor("#f9e2af")
                pen = QPen(border_color, 3, Qt.SolidLine)
            elif is_hover:
                border_color = QColor("#f38ba8")
                pen = QPen(border_color, 2, Qt.SolidLine)
            else:
                border_color = QColor("#89b4fa")
                pen = QPen(border_color, 2, Qt.SolidLine)
            p.setPen(pen)
            p.drawRect(cr_canvas)

            label = str(cr.index)
            font = QFont("monospace", 10, QFont.Bold)
            p.setFont(font)
            fm = QFontMetrics(font)
            tw = fm.horizontalAdvance(label) + 10
            th = fm.height() + 6
            badge = QRect(cr_canvas.left(), cr_canvas.top() - th if cr_canvas.top() > th else cr_canvas.top(), tw, th)
            p.fillRect(badge, border_color)
            p.setPen(QColor("#1e1e2e"))
            p.drawText(badge, Qt.AlignCenter, label)

        if self.drawing and self.draw_start and self.draw_current:
            r = QRect(self.draw_start, self.draw_current).normalized()
            cr = self._rect_to_canvas(r)
            p.fillRect(cr, QColor(166, 227, 161, 50))
            pen = QPen(QColor("#a6e3a1"), 2, Qt.DashLine)
            p.setPen(pen)
            p.drawRect(cr)
            p.setPen(QColor("#a6e3a1"))
            p.setFont(QFont("monospace", 9))
            p.drawText(cr.topLeft() + QPoint(4, 14), f"{r.width()}×{r.height()}")


#─────────────────────────────────────────────────────────────────────────────
#Main window
#─────────────────────────────────────────────────────────────────────────────
class WebtoonCropper(QMainWindow, FileOpenHandleMixin, FileExportHandleMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Webtoon Cropper Pro")
        self.setMinimumSize(950, 700)
        self.resize(1200, 800)

        self.groups = ["Mặc định"]
        self.current_group = "Mặc định"

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        self.setStyleSheet(MAIN_WINDOW_STYLE)

    def _build_ui(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_add = QPushButton("+ Thêm ảnh")
        self.btn_add.clicked.connect(self._open_files)
        tb.addWidget(self.btn_add)

        tb.addSeparator()

        self.btn_remove = QPushButton("✕ Xóa trang")
        self.btn_remove.clicked.connect(self._remove_page)
        tb.addWidget(self.btn_remove)

        self.btn_clear_pages = QPushButton("⊘ Xóa tất cả")
        self.btn_clear_pages.clicked.connect(self._clear_all)
        tb.addWidget(self.btn_clear_pages)

        tb.addSeparator()

        self.btn_clear_rects = QPushButton("↺ Xóa vùng")
        self.btn_clear_rects.clicked.connect(self._clear_rects)
        tb.addWidget(self.btn_clear_rects)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.btn_crop = QPushButton("✂  Crop & Export Groups")
        self.btn_crop.setObjectName("crop_btn")
        self.btn_crop.setFixedHeight(32)
        self.btn_crop.clicked.connect(self._do_crop)
        self.btn_crop.setEnabled(False)
        tb.addWidget(self.btn_crop)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Left panel
        left = QWidget()
        left.setFixedWidth(160)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl = QLabel("TRANG (kéo để sắp xếp)")
        lbl.setObjectName("section_label")
        lbl.setWordWrap(True)
        left_layout.addWidget(lbl)

        self.page_list = PageListWidget()
        self.page_list.pages_changed.connect(self._rebuild_merged)
        self.page_list.setAcceptDrops(True)
        self.page_list.dragEnterEvent = self._list_drag_enter
        self.page_list.dropEvent = self._list_drop
        left_layout.addWidget(self.page_list)

        lbl_group = QLabel("NHÓM CROP")
        lbl_group.setObjectName("section_label")
        left_layout.addWidget(lbl_group)

        self.group_list = QListWidget()
        self.group_list.setFixedHeight(120)
        self.group_list.currentRowChanged.connect(self._on_group_selected)
        left_layout.addWidget(self.group_list)

        group_btn_layout = QHBoxLayout()
        group_btn_layout.setSpacing(2)

        self.btn_add_group = QPushButton("+")
        self.btn_add_group.setToolTip("Thêm nhóm mới")
        self.btn_add_group.clicked.connect(self._add_group)

        self.btn_remove_group = QPushButton("✕")
        self.btn_remove_group.setToolTip("Xóa nhóm đang chọn")
        self.btn_remove_group.clicked.connect(self._remove_group)

        self.btn_rename_group = QPushButton("✎")
        self.btn_rename_group.setToolTip("Đổi tên nhóm")
        self.btn_rename_group.clicked.connect(self._rename_group)

        group_btn_layout.addWidget(self.btn_add_group)
        group_btn_layout.addWidget(self.btn_remove_group)
        group_btn_layout.addWidget(self.btn_rename_group)
        left_layout.addLayout(group_btn_layout)

        hint = QLabel("Chuột giữa: Kéo canvas\nCuộn chuột: Zoom\nChuột phải: Đổi nhóm/xóa vùng")
        hint.setStyleSheet("color: #45475a; font-size: 9px; padding: 4px; line-height: 1.4;")
        hint.setWordWrap(True)
        left_layout.addWidget(hint)

        main_layout.addWidget(left)

        # Right: canvas
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        rect_bar = QHBoxLayout()
        lbl2 = QLabel("CANVAS — Kéo chuột để tạo vùng, Chuột phải để quản lý")
        lbl2.setObjectName("section_label")
        rect_bar.addWidget(lbl2)
        rect_bar.addStretch()
        self.rect_count_lbl = QLabel("0 vùng")
        self.rect_count_lbl.setStyleSheet("color: #89b4fa; font-size: 10px;")
        rect_bar.addWidget(self.rect_count_lbl)
        right_layout.addLayout(rect_bar)

        self.canvas_scroll = CanvasScrollArea()
        self.canvas_scroll.files_dropped.connect(self._add_files)

        self.canvas = CanvasWidget()
        self.canvas.status_msg.connect(self._on_canvas_status)
        self.canvas.rect_changed.connect(self._update_rect_count)
        self.canvas.get_groups = lambda: self.groups  # Link group provider
        self.canvas_scroll.setWidget(self.canvas)
        right_layout.addWidget(self.canvas_scroll)

        main_layout.addWidget(right)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Kéo thả ảnh vào bảng trái hoặc canvas để bắt đầu.")

        self._refresh_groups()

    # ── Group Management ──────────────────────────────────────────────────
    def _refresh_groups(self):
        self.group_list.clear()
        self.group_list.addItems(self.groups)

        items = self.group_list.findItems(self.current_group, Qt.MatchExactly)
        if items:
            row = self.group_list.row(items[0])
            self.group_list.setCurrentRow(row)

    def _on_group_selected(self, row):
        if row >= 0:
            self.current_group = self.groups[row]
            self.canvas.current_group = self.current_group

    def _add_group(self):
        name, ok = QInputDialog.getText(self, "Thêm nhóm", "Tên nhóm mới:")
        if ok and name.strip():
            name = name.strip()
            if name not in self.groups:
                self.groups.append(name)
                self._refresh_groups()
                self.current_group = name
                self.canvas.current_group = name
                self.status.showMessage(f"Đã thêm nhóm '{name}'")

    def _remove_group(self):
        row = self.group_list.currentRow()
        if row >= 0:
            name = self.groups[row]
            if name == "Mặc định":
                QMessageBox.warning(self, "Lỗi", "Không thể xóa nhóm 'Mاặc định'.")
                return
            reply = QMessageBox.question(self, "Xóa nhóm", f"Xóa nhóm '{name}'?\nCác vùng trong nhóm này sẽ chuyển về 'Mặc định'.", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                for cr in self.canvas.crop_rects:
                    if cr.group == name:
                        cr.group = "Mặc định"
                self.groups.remove(name)
                self._refresh_groups()
                self.canvas.update()
                self.status.showMessage(f"Đã xóa nhóm '{name}'")

    def _rename_group(self):
        row = self.group_list.currentRow()
        if row >= 0:
            old_name = self.groups[row]
            if old_name == "Mặc định":
                QMessageBox.warning(self, "Lỗi", "Không thể đổi tên nhóm 'Mặc định'.")
                return
            new_name, ok = QInputDialog.getText(self, "Đổi tên nhóm", "Tên mới:", text=old_name)
            if ok and new_name.strip() and new_name.strip() != old_name:
                new_name = new_name.strip()
                if new_name in self.groups:
                    QMessageBox.warning(self, "Lỗi", "Tên nhóm đã tồn tại.")
                    return
                for cr in self.canvas.crop_rects:
                    if cr.group == old_name:
                        cr.group = new_name
                self.groups[row] = new_name
                self.current_group = new_name
                self.canvas.current_group = new_name
                self._refresh_groups()
                self.canvas.update()
                self.status.showMessage(f"Đã đổi tên nhóm thành '{new_name}'")

    # ── rebuild merged image ──────────────────────────────────────────────
    def _rebuild_merged(self):
        pixmaps = self.page_list.get_pixmaps()
        if not pixmaps:
            self.canvas.clear()
            self.btn_crop.setEnabled(False)
            return

        total_w = max(px.width() for px in pixmaps)
        total_h = sum(px.height() for px in pixmaps)

        merged = QPixmap(total_w, total_h)
        merged.fill(Qt.white)
        painter = QPainter(merged)
        y = 0
        for px in pixmaps:
            painter.drawPixmap(0, y, px)
            y += px.height()
        painter.end()

        self.canvas.set_merged(merged)
        self.status.showMessage(f"Ghép {len(pixmaps)} trang — {total_w}×{total_h}px. Vẽ vùng crop trên canvas.")

    # ── rect operations ────────────────────────────────────────────────────
    def _clear_rects(self):
        self.canvas.crop_rects.clear()
        self.canvas.selected_rect_idx = -1
        self.canvas.update()
        self.rect_count_lbl.setText("0 vùng")
        self.btn_crop.setEnabled(False)
        self.status.showMessage("Đã xóa tất cả vùng crop.")

    # ── helpers ───────────────────────────────────────────────────────────
    def _on_canvas_status(self, msg: str):
        self.status.showMessage(msg)

    def _update_rect_count(self, _=None):
        n = len(self.canvas.crop_rects)
        self.rect_count_lbl.setText(f"{n} vùng")
        self.btn_crop.setEnabled(n > 0 and self.canvas.merged is not None)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = WebtoonCropper()
    win.show()
    sys.exit(app.exec())
