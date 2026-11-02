"""浮层卡片：圆角、描边、主题底色（对话框与抽屉共用）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame

from customgui.appcore import get_design_tokens

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
        # 底色取主题的 surface_app：深色主题下与旧的 custom_bg_one 完全等价，
        # 浅色主题（如 eye/bright）则跟随主题，不再是一张突兀的纯白卡片。
        background = QColor(get_design_tokens().colors.surface_app)
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
