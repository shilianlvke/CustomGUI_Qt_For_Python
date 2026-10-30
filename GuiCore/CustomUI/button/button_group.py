"""按钮组：同一行内合并边框与圆角的按钮集合（对应 Sakai 的 ButtonGroup）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from .button import CButton
from .severity import Variant, colors_for


class CButtonGroup(QWidget):
    """横向按钮组。

    组内按钮只负责各自的背景与内容，外框（outlined 变体）由组统一绘制，
    因此相邻边不会出现双线；首尾按钮保留外侧圆角，中间按钮为直角。
    """

    def __init__(self, buttons: list[CButton] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("CButtonGroup_Widget")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._buttons: list[CButton] = []
        for button in buttons or []:
            self.add_button(button)

    def add_button(self, button: CButton) -> None:
        button.set_border_visible(False)
        self._layout.addWidget(button)
        self._buttons.append(button)
        self._refresh_corners()

    def buttons(self) -> list[CButton]:
        return list(self._buttons)

    def _refresh_corners(self) -> None:
        count = len(self._buttons)
        for index, button in enumerate(self._buttons):
            first, last = index == 0, index == count - 1
            button.set_corners((first, last, last, first))

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self._buttons:
            return
        first = self._buttons[0]
        if first.variant() is not Variant.OUTLINED:
            return
        colors = colors_for(first.severity(), first.variant())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(colors.border, 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        painter.end()


__all__ = ["CButtonGroup"]
