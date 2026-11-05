"""通用关闭按钮（消息、通知、对话框、抽屉共用）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

from sllkgui.appcore import ColorPalette


class CCloseButton(QAbstractButton):
    """× 按钮：悬停出现淡底，颜色可随主题更新。

    ``radius`` 为 ``None``（默认）时是圆形（消息/通知/对话框用）；
    传具体圆角则画成圆角方形，用于标题栏/抽屉头部这类 30×30 的窗口控制位，
    悬停底色取 ``custom_bg_two``，与 ``CLeftColumn`` 的关闭按钮一致。
    """

    def __init__(self, color: QColor, size: int = 20, radius: int | None = None, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._radius = None if radius is None else max(0, int(radius))
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
            if self._radius is None:
                fill = QColor(self._color)
                fill.setAlpha(38)
                painter.setPen(Qt.NoPen)
                painter.setBrush(fill)
                painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(ColorPalette.custom_bg_two))
                painter.drawRoundedRect(QRectF(self.rect()), self._radius, self._radius)
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
