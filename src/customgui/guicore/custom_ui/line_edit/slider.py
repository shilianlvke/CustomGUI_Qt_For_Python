"""滑块（复刻 PrimeVue Aura Slider）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from customgui.appcore import AppSettings

from .input_style import colors

#: 轨道高度的兼容兜底值（运行时以配置为准）
TRACK_HEIGHT = 4
#: 手柄半径的兼容兜底值（运行时以配置为准）
HANDLE_RADIUS = 9
#: 左右留白的兼容兜底值（运行时以配置为准）
MARGIN = 12


class CSlider(QWidget):
    """水平滑块：点击跳转、拖动改值，按 step 量化。"""

    valueChanged = Signal(int)
    #: 拖动结束（松开鼠标）后发出最终值，供宿主做落盘等一次性动作
    sliderReleased = Signal(int)

    def __init__(self, value: int = 0, minimum: int = 0, maximum: int = 100, step: int = 1, parent=None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = max(minimum, maximum)
        self._step = max(1, step)
        self._value = self._clamp(value)
        self._dragging = False
        self._hover = False
        self._track_height = int(AppSettings.input.slider_track_height)
        self._handle_radius = int(AppSettings.input.slider_handle_radius)
        self._margin = int(AppSettings.input.slider_margin)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

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

    def setRange(self, minimum: int, maximum: int) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._minimum, self._maximum = minimum, max(minimum, maximum)
        self.setValue(self._value)

    def setStep(self, step: int) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._step = max(1, step)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(200, 32)

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------
    def _ratio(self) -> float:
        span = self._maximum - self._minimum
        return 0.0 if span <= 0 else (self._value - self._minimum) / span

    def _track_rect(self) -> QRectF:
        return QRectF(
            self._margin,
            (self.height() - self._track_height) / 2,
            self.width() - self._margin * 2,
            self._track_height,
        )

    def _handle_center(self) -> QPointF:
        track = self._track_rect()
        return QPointF(track.left() + track.width() * self._ratio(), self.height() / 2)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        accent = QColor(palette["focus_border"])
        track = self._track_rect()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(palette["control_border"]))
        painter.drawRoundedRect(track, self._track_height / 2, self._track_height / 2)

        filled = QRectF(track.left(), track.top(), track.width() * self._ratio(), track.height())
        painter.setBrush(accent)
        painter.drawRoundedRect(filled, self._track_height / 2, self._track_height / 2)

        center = self._handle_center()
        radius = self._handle_radius + (1 if (self._hover or self._dragging) else 0)
        painter.setBrush(QColor(palette["background"]))
        painter.setPen(QPen(accent, 2))
        painter.drawEllipse(center, radius, radius)
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _value_at(self, x: float) -> int:
        track = self._track_rect()
        ratio = 0.0 if track.width() <= 0 else (x - track.left()) / track.width()
        ratio = max(0.0, min(1.0, ratio))
        return self._quantize(self._minimum + (self._maximum - self._minimum) * ratio)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        self._dragging = True
        self.setValue(self._value_at(event.position().x()))

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._dragging:
            self.setValue(self._value_at(event.position().x()))

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        was_dragging = self._dragging
        self._dragging = False
        self.update()
        if was_dragging and event.button() == Qt.LeftButton:
            self.sliderReleased.emit(self._value)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        direction = 1 if event.angleDelta().y() > 0 else -1
        self.setValue(self._value + direction * self._step)


__all__ = ["CSlider"]
