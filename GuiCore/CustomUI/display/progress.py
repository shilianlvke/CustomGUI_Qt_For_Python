"""进度条（复刻 PrimeVue Aura ProgressBar）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..button.severity import contrast_text
from .palette import tokens

_INTERVAL = 33


class CProgressBar(QWidget):
    """进度条：确定进度 / 不确定扫描 / 内嵌百分比文字。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        value: int = 0,
        maximum: int = 100,
        show_value: bool = False,
        indeterminate: bool = False,
        height: int = 6,
        parent=None,
    ):
        super().__init__(parent)
        self._maximum = max(1, maximum)
        self._value = max(0, min(self._maximum, value))
        self._show_value = show_value
        self._indeterminate = indeterminate
        self._bar_height = 20 if show_value else max(3, height)
        self._phase = 0.0
        self.setFixedHeight(self._bar_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def value(self) -> int:
        return self._value

    def maximum(self) -> int:
        return self._maximum

    def setValue(self, value: int, emit: bool = True) -> None:  # noqa: N802 - 覆写 Qt 命名
        value = max(0, min(self._maximum, int(value)))
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.valueChanged.emit(value)

    def setMaximum(self, maximum: int) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._maximum = max(1, int(maximum))
        self.setValue(self._value)

    def set_indeterminate(self, indeterminate: bool) -> None:
        self._indeterminate = indeterminate
        if indeterminate and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def is_indeterminate(self) -> bool:
        return self._indeterminate

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(220, self._bar_height)

    # ------------------------------------------------------------------
    # 动画与生命周期
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        self._phase = (self._phase + _INTERVAL / 1300) % 1.0
        self.update()

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        if self._indeterminate:
            self._timer.start()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.stop()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        return path

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        accent = QColor(palette["accent"])
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        painter.fillPath(self._path(rect), QColor(palette["surface_strong"]))

        if self._indeterminate:
            segment_width = max(40.0, rect.width() * 0.32)
            start = -segment_width + (rect.width() + segment_width) * self._phase
            segment = QRectF(start, rect.top(), segment_width, rect.height())
            painter.save()
            painter.setClipPath(self._path(rect))
            painter.fillPath(self._path(segment), accent)
            painter.restore()
        elif self._value > 0:
            ratio = self._value / self._maximum
            fill = QRectF(rect.left(), rect.top(), max(rect.height(), rect.width() * ratio), rect.height())
            painter.fillPath(self._path(fill), accent)

        if self._show_value and not self._indeterminate:
            ratio = self._value / self._maximum
            color = contrast_text(accent) if ratio > 0.55 else QColor(palette["text"])
            painter.setPen(color)
            font = self.font()
            font.setPixelSize(12)
            font.setWeight(font.Weight.DemiBold)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, f"{round(ratio * 100)}%")
        painter.end()


__all__ = ["CProgressBar"]
