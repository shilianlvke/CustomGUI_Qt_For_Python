"""通用圆形关闭按钮（消息、通知、对话框、抽屉共用）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton


class CCloseButton(QAbstractButton):
    """20×20 的 × 按钮：悬停出现淡底，颜色可随主题更新。"""

    def __init__(self, color: QColor, size: int = 20, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._hover:
            fill = QColor(self._color)
            fill.setAlpha(38)
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        inset = self.width() * 0.3
        painter.setPen(QPen(self._color, 1.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(inset, inset, self.width() - inset, self.height() - inset)
        painter.drawLine(self.width() - inset, inset, inset, self.height() - inset)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


__all__ = ["CCloseButton"]
