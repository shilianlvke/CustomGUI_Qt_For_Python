"""浮动标签输入框（复刻 PrimeVue Aura FloatLabel）。"""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, Qt, QVariantAnimation
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from .input_style import colors, size_spec
from .input_text import CInputText

#: 标签上浮后占用的高度
_LABEL_BAND = 14
#: 上浮后的字号
_FLOAT_FONT_PX = 11


class CFloatLabel(QWidget):
    """标签置于输入框内，聚焦或有内容时上浮到输入框上方的窄带里。"""

    def __init__(self, label: str, size: str = "md", parent=None):
        super().__init__(parent)
        self.setObjectName("CFloatLabel_Widget")
        self._size = size
        self._spec = size_spec(size)
        self.setFixedHeight(self._spec.height + _LABEL_BAND)

        self._input = CInputText(size=size, parent=self)
        self._label = QLabel(label, self)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._progress = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(0.0)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(lambda value: self._apply_progress(float(value)))

        self._input.textChanged.connect(self._sync)
        self._input.installEventFilter(self)
        self._apply_progress(0.0)

    # ------------------------------------------------------------------
    def input(self) -> CInputText:
        return self._input

    def text(self) -> str:
        return self._input.text()

    def setText(self, text: str) -> None:  # noqa: N802 - 对齐 Qt 命名
        self._input.setText(text)
        self._sync(animate=False)

    def set_placeholder(self, text: str) -> None:
        self._input.setPlaceholderText(text)

    # ------------------------------------------------------------------
    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._input.setGeometry(0, _LABEL_BAND, self.width(), self._spec.height)
        self._apply_progress(self._progress)
        super().resizeEvent(event)

    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if obj is self._input and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self._sync()
        return False

    def _sync(self, animate: bool = True) -> None:
        target = 1.0 if (self._input.hasFocus() or self._input.text()) else 0.0
        if not animate:
            self._apply_progress(target)
            return
        end = self._animation.endValue() or 0.0
        if abs(end - target) < 1e-3 and self._animation.state() == QAbstractAnimation.State.Running:
            return
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(target)
        self._animation.start()

    def _apply_progress(self, progress: float) -> None:
        self._progress = progress
        spec = self._spec
        font = QFont(self._label.font())
        font.setPixelSize(max(_FLOAT_FONT_PX, round(spec.font_px + (_FLOAT_FONT_PX - spec.font_px) * progress)))
        self._label.setFont(font)
        self._label.adjustSize()

        x = spec.padding_x + round(4 * (1 - progress))
        if progress >= 1.0:
            y = 0
        else:
            y = _LABEL_BAND + round((spec.height - self._label.height()) / 2 * (1 - progress))
        self._label.move(x, y)

        palette = colors()
        color = palette["placeholder"] if progress < 0.5 else palette["text"]
        self._label.setStyleSheet(f"color: {color}; background: transparent;")


__all__ = ["CFloatLabel"]
