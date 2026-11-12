"""浮层卡片：圆角、描边、亚克力底色（对话框与抽屉共用）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame

from ...styles import overlay_border_color, overlay_surface_color


class COverlayCard(QFrame):
    """浮层内容卡片。

    底色与右侧设置抽屉、浮层抽屉共用 ``overlay_surface_color`` /
    ``overlay_border_color``：亚克力模式下随「质感强度」透出下层，
    实色模式下退回主题的浮层表面，避免每种浮层各写一套色值。
    """

    def __init__(self, parent=None, radius: int = 10):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WA_StyledBackground, False)

    def setRadius(self, radius: int) -> None:  # noqa: N802 - 与 Qt 命名风格一致
        self._radius = max(0, int(radius))
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(path, overlay_surface_color())
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(overlay_border_color(), 1))
        painter.drawPath(path)
        painter.end()


__all__ = ["COverlayCard"]
