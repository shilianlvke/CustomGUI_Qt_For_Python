"""浮层卡片：圆角、描边、主题底色（对话框与抽屉共用）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame

from AppCore import ColorPalette

from ..display.palette import tokens


class COverlayCard(QFrame):
    """浮层内容卡片。"""

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
        palette = tokens()
        dark = QColor(palette["surface"]).lightness() < 128
        background = QColor(ColorPalette.custom_bg_one if dark else "#ffffff")
        border = QColor(palette["border"])

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(path, background)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        painter.end()


__all__ = ["COverlayCard"]
