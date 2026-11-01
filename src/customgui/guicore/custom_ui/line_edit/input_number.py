"""数字输入框（复刻 PrimeVue Aura InputNumber，含步进按钮）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDoubleValidator, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QWidget

from .input_style import RADIUS, colors, rounded_path, size_spec
from .input_text import CInputText


class _SpinButtons(QWidget):
    """输入框右侧的上下步进按钮（自绘，颜色实时读主题）。"""

    upClicked = Signal()
    downClicked = Signal()

    def __init__(self, size: str = "md", corners=None, parent=None):
        super().__init__(parent)
        self.setObjectName("CInputNumber_SpinButtons")
        spec = size_spec(size)
        self._corners = corners
        self._hover = None
        self.setFixedSize(24, spec.height)
        self.setCursor(Qt.PointingHandCursor)

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        self._corners = corners
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        palette = colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillPath(rounded_path(rect, RADIUS, self._corners), QColor(palette["addon_background"]))

        painter.setPen(QPen(QColor(palette["border"]), 1))
        middle = self.height() / 2
        painter.drawLine(0, 0, 0, self.height())
        painter.drawLine(1, int(middle), self.width(), int(middle))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(palette["text"]))
        width, height = 8.0, 4.5
        center_x = self.width() / 2
        upper_y = middle / 2
        lower_y = middle + middle / 2
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center_x - width / 2, upper_y + height / 2),
                    QPointF(center_x + width / 2, upper_y + height / 2),
                    QPointF(center_x, upper_y - height / 2),
                ]
            )
        )
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center_x - width / 2, lower_y - height / 2),
                    QPointF(center_x + width / 2, lower_y - height / 2),
                    QPointF(center_x, lower_y + height / 2),
                ]
            )
        )
        painter.end()

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
