"""旋钮（复刻 PrimeVue Aura Knob）。"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from AppCore import AppSettings

from .input_style import colors

RING_WIDTH = 9
START_ANGLE = 225.0
SWEEP = 270.0
PIXELS_PER_STEP = 3


class CKnob(QWidget):
    """圆形旋钮：拖动上下改变值，按 step 量化。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        value: int = 0,
        minimum: int = 0,
        maximum: int = 100,
        step: int = 1,
        size: int = 120,
        parent=None,
    ):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = max(minimum + 1, maximum)
        self._step = max(1, step)
        self._value = self._clamp(value)
        self._drag_origin: tuple[int, int] | None = None
        self._drag_value = self._value
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.SizeVerCursor)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _clamp(self, value) -> int:
        return int(max(self._minimum, min(self._maximum, value)))

    def _quantize(self, value: float) -> int:
        steps = round((value - self._minimum) / self._step)
        return self._clamp(self._minimum + steps * self._step)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int, emit: bool = True) -> None:  # noqa: N802 - 覆写 Qt 命名
        value = self._quantize(value)
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.valueChanged.emit(value)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self.width(), self.height())

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------
    def _ratio(self) -> float:
        return (self._value - self._minimum) / (self._maximum - self._minimum)

    def _ring_rect(self) -> QRectF:
        inset = RING_WIDTH / 2 + 4
        return QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)

    def _handle_center(self) -> QPointF:
        rect = self._ring_rect()
        angle = math.radians(START_ANGLE - SWEEP * self._ratio())
        return QPointF(
            rect.center().x() + rect.width() / 2 * math.cos(angle),
            rect.center().y() - rect.height() / 2 * math.sin(angle),
        )

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        accent = QColor(palette["focus_border"])
        rect = self._ring_rect()

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["control_border"]), RING_WIDTH, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, int(START_ANGLE * 16), int(-SWEEP * 16))

        if self._value > self._minimum:
            painter.setPen(QPen(accent, RING_WIDTH, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(rect, int(START_ANGLE * 16), int(-SWEEP * 16 * self._ratio()))

        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(self._handle_center(), 5.5, 5.5)

        font = QFont(AppSettings.family)
        font.setPixelSize(20)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(palette["text"]))
        painter.drawText(QRectF(self.rect()), Qt.AlignCenter, str(self._value))
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        self._drag_origin = (event.globalPosition().x(), event.globalPosition().y())
        self._drag_value = self._value

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._drag_origin is None:
            return
        delta = self._drag_origin[1] - event.globalPosition().y()
        steps = round(delta / PIXELS_PER_STEP)
        self.setValue(self._drag_value + steps * self._step)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._drag_origin = None

    def wheelEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        direction = 1 if event.angleDelta().y() > 0 else -1
        self.setValue(self._value + direction * self._step)


__all__ = ["CKnob"]
