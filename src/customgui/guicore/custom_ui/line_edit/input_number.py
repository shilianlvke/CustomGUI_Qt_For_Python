"""数字输入框（复刻 PrimeVue Aura InputNumber，含步进按钮）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDoubleValidator, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..paint_utils import draw_chevron
from .input_style import RADIUS, colors, rounded_path, size_spec
from .input_text import CInputText


class _SpinButtons(QWidget):
    """输入框右侧的上下步进按钮（自绘，颜色实时读主题）。

    视觉对齐 Aura ``.p-inputnumber-button``：底色跟输入框一致（看上去是一整块），
    左边缘不描边（由左侧输入框的右边框充当分隔线），上下两个按钮之间画一条分隔线，
    箭头用 chevron 而不是实心三角。
    """

    upClicked = Signal()
    downClicked = Signal()

    def __init__(self, size: str = "md", corners=None, parent=None):
        super().__init__(parent)
        self.setObjectName("CInputNumber_SpinButtons")
        spec = size_spec(size)
        self._corners = corners
        self._icon_px = spec.icon_px
        self._hover = 0  # 0 无、1 上、2 下
        self.setFixedSize(26, spec.height)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        self._corners = corners
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        palette = colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(self.rect())
        middle = body.height() / 2

        painter.fillPath(rounded_path(body, RADIUS, self._corners), QColor(palette["background"]))

        # hover 半区高亮（Aura: button.hover.background）
        if self._hover and self.isEnabled():
            zone = QRectF(0, 0, body.width(), middle) if self._hover == 1 else QRectF(0, middle, body.width(), middle)
            highlight = QColor(palette["hover_border"])
            highlight.setAlpha(28)
            painter.setClipPath(rounded_path(body, RADIUS, self._corners))
            painter.fillRect(zone, highlight)
            painter.setClipping(False)

        # 轮廓：左边缘交给左边输入框的右边框，其余三边自己画
        stroke = rounded_path(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, self._corners)
        painter.setClipRect(QRectF(1.0, 0.0, body.width() - 1.0, body.height()))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(stroke)
        painter.setClipping(False)

        # 上下按钮之间的分隔线
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawLine(1, int(middle), int(body.width()), int(middle))

        icon_color = QColor(palette["icon"])
        center_x = body.width() / 2
        draw_chevron(painter, QPointF(center_x, middle / 2), icon_color, 6.0, "up", 1.4)
        draw_chevron(painter, QPointF(center_x, middle + middle / 2), icon_color, 6.0, "down", 1.4)
        painter.end()

    def _zone_at(self, y: float) -> int:
        return 1 if y < self.height() / 2 else 2

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        zone = self._zone_at(event.position().y())
        if zone != self._hover:
            self._hover = zone
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._hover:
            self._hover = 0
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            if event.position().y() < self.height() / 2:
                self.upClicked.emit()
            else:
                self.downClicked.emit()


class CInputNumber(QWidget):
    """数字输入：输入框 + 可选步进按钮，支持取值范围与小数位。"""

    valueChanged = Signal(float)

    def __init__(
        self,
        value: float = 0,
        minimum: float = 0,
        maximum: float = 100,
        step: float = 1,
        decimals: int = 0,
        show_buttons: bool = True,
        size: str = "md",
        placeholder: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CInputNumber_Widget")
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._decimals = max(0, decimals)
        self._value = self._clamp(float(value))

        spec = size_spec(size)
        self.setFixedHeight(spec.height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = CInputText(
            size=size,
            corners=(True, False, False, True) if show_buttons else None,
        )
        if placeholder:
            self._input.setPlaceholderText(placeholder)
        layout.addWidget(self._input)

        self._spins = None
        if show_buttons:
            self._spins = _SpinButtons(size, corners=(False, True, True, False))
            layout.addWidget(self._spins)
            self._spins.upClicked.connect(lambda: self._step_by(1))
            self._spins.downClicked.connect(lambda: self._step_by(-1))

        validator = QDoubleValidator(self._minimum, self._maximum, self._decimals, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self._input.setValidator(validator)
        self._input.setText(self._format(self._value))
        self._input.editingFinished.connect(self._commit)

    # ------------------------------------------------------------------
    def value(self) -> float:
        return self._value

    def setValue(self, value: float) -> None:  # noqa: N802 - 对齐 Qt 命名
        value = self._clamp(float(value))
        changed = abs(value - self._value) > 1e-9
        self._value = value
        self._input.setText(self._format(value))
        if changed:
            self.valueChanged.emit(value)

    def setRange(self, minimum: float, maximum: float) -> None:  # noqa: N802 - 对齐 Qt 命名
        self._minimum = minimum
        self._maximum = maximum
        self.setValue(self._value)

    def set_decimals(self, decimals: int) -> None:
        self._decimals = max(0, decimals)
        self._value = self._clamp(self._value)
        self._input.setText(self._format(self._value))

    def input(self) -> CInputText:
        return self._input

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        """供输入框组拼接：左半边是输入框、右半边是步进块，各自只保留外侧圆角。"""
        self._input.set_corners((corners[0], False, False, corners[3]))
        if self._spins is not None:
            self._spins.set_corners((False, corners[1], corners[2], False))

    # ------------------------------------------------------------------
    def _clamp(self, value: float) -> float:
        return max(self._minimum, min(self._maximum, value))

    def _format(self, value: float) -> str:
        return f"{value:.{self._decimals}f}" if self._decimals > 0 else str(int(round(value)))

    def _step_by(self, direction: int) -> None:
        self.setValue(self._value + direction * self._step)

    def _commit(self) -> None:
        text = self._input.text().strip()
        if not text:
            self.setValue(self._minimum)
            return
        try:
            value = float(text)
        except ValueError:
            self._input.setText(self._format(self._value))
            return
        self.setValue(value)


__all__ = ["CInputNumber"]
