"""图片缩略图按钮：圆角裁切、选中描边、点击回调。

用于「最近使用的背景」「插件截图」等场景。解码阶段就按目标尺寸缩放，
避免把 4K 原图整张读进内存。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QImageReader, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from sllkgui.appcore import get_design_tokens


def load_scaled_pixmap(path: str, width: int, height: int) -> QPixmap:
    """按目标逻辑尺寸的 2 倍解码图片（兼顾高 DPI 与内存）。"""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    natural = reader.size()
    if natural.isValid() and natural.width() > 0 and natural.height() > 0:
        target = QSize(max(1, width) * 2, max(1, height) * 2)
        reader.setScaledSize(natural.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding))
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


class CThumbnail(QWidget):
    """固定尺寸缩略图；``path`` 为空时显示占位底色。"""

    clicked = Signal(str)

    def __init__(
        self,
        path: str = "",
        *,
        width: int = 64,
        height: int = 40,
        selected: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._path = str(path)
        self._selected = bool(selected)
        self._hover = False
        self._size = QSize(max(8, int(width)), max(8, int(height)))
        self._pixmap = load_scaled_pixmap(self._path, self._size.width(), self._size.height()) if self._path else QPixmap()
        self.setFixedSize(self._size)
        self.setCursor(Qt.PointingHandCursor)
        if self._path:
            self.setToolTip(self._path)

    # ------------------------------------------------------------------
    def path(self) -> str:
        return self._path

    def set_selected(self, selected: bool) -> None:
        value = bool(selected)
        if value != self._selected:
            self._selected = value
            self.update()

    def is_selected(self) -> bool:
        return self._selected

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._size)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._size)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        tokens = get_design_tokens()
        colors = tokens.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, tokens.radius.control, tokens.radius.control)
        painter.fillPath(path, colors.surface_interactive_pressed)
        if not self._pixmap.isNull():
            painter.save()
            painter.setClipPath(path)
            scaled = self._pixmap.scaled(
                rect.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.left() + (rect.width() - scaled.width()) / 2
            y = rect.top() + (rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()
        border = colors.border_context if self._selected else colors.surface_interactive_pressed
        if self._hover and not self._selected:
            border = colors.border_soft
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 2 if self._selected else 1))
        painter.drawPath(path)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._path)
            event.accept()
            return
        super().mouseReleaseEvent(event)


__all__ = ["CThumbnail", "load_scaled_pixmap"]
