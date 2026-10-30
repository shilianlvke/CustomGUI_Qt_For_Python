"""星级评分（复刻 PrimeVue Aura Rating）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from .input_style import colors
from ..paint_utils import star_path

STAR_SIZE = 24
STAR_GAP = 6


class CRating(QWidget):
    """五星评分：悬停预览、点击落值。"""

    valueChanged = Signal(int)

    def __init__(self, value: int = 0, maximum: int = 5, parent=None):
        super().__init__(parent)
        self._maximum = max(1, maximum)
        self._value = max(0, min(self._maximum, value))
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self._maximum * (STAR_SIZE + STAR_GAP) - STAR_GAP + 2, STAR_SIZE + 6)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def value(self) -> int:
        return self._value

    def setValue(self, value: int, emit: bool = True) -> None:  # noqa: N802 - 覆写 Qt 命名
        value = max(0, min(self._maximum, value))
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.valueChanged.emit(value)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self.width(), self.height())

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        accent = QColor(palette["focus_border"])
        empty = QColor(palette["border"])
        active = self._hover if self._hover >= 0 else self._value

        for index in range(self._maximum):
            center = QPointF(
                1 + STAR_SIZE / 2 + index * (STAR_SIZE + STAR_GAP),
                self.height() / 2,
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent if index < active else empty)
            painter.drawPath(star_path(center, STAR_SIZE / 2 - 1))
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, x: float) -> int:
        index = int(x // (STAR_SIZE + STAR_GAP))
        return max(0, min(self._maximum - 1, index))

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position().x())
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        self.setValue(self._index_at(event.position().x()) + 1)


__all__ = ["CRating"]
