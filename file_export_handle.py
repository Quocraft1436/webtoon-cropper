"""
File Export Handling
- FileExportHandleMixin: crop ảnh đã ghép theo từng vùng (CropRect) và
  xuất ra thư mục theo nhóm.
"""
import os
from collections import defaultdict
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtGui import QImage


class FileExportHandleMixin:
    # ── crop & export by group ────────────────────────────────────────────
    def _do_crop(self):
        if not self.canvas.merged or not self.canvas.crop_rects:
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục gốc để lưu crop")
        if not out_dir:
            return

        merged_img: QImage = self.canvas.merged.toImage()

        grouped_rects = defaultdict(list)
        for cr in self.canvas.crop_rects:
            grouped_rects[cr.group].append(cr)

        total_saved = 0
        errors = []

        for group_name, rects in grouped_rects.items():
            group_dir = os.path.join(out_dir, group_name)
            os.makedirs(group_dir, exist_ok=True)

            rects.sort(key=lambda x: x.index)

            for cr in rects:
                r = cr.rect
                cropped = merged_img.copy(r)
                if cropped.isNull():
                    errors.append(f"{group_name}/#{cr.index}")
                    continue

                out_path = os.path.join(group_dir, f"crop_{cr.index:03d}.png")
                ok = cropped.save(out_path, "PNG")
                if ok:
                    total_saved += 1
                else:
                    errors.append(f"{group_name}/#{cr.index}")

        msg = f"✓ Đã lưu {total_saved}/{len(self.canvas.crop_rects)} vùng vào:\n{out_dir}"
        if errors:
            msg += f"\n✗ Lỗi: {', '.join(errors)}"
        QMessageBox.information(self, "Crop xong", msg)
        self.status.showMessage(f"Đã crop {total_saved} vùng vào {len(grouped_rects)} thư mục nhóm.")
