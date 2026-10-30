"""选择类控件：复选框、单选按钮、开关（复刻 PrimeVue Aura）。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy


from .input_style import colors, field_font
from ..paint_utils import draw_check

BOX_SIZE = 20
LABEL_GAP = 8
_CHECK_COLOR = QColor("#ffffff")


def mix_color(start: QColor, end: QColor, ratio: float) -> QColor:
    """按比例线性混合两个颜色。"""
    ratio = max(0.0, min(1.0, ratio))
    return QColor(
        round(start.red() + (end.red() - start.red()) * ratio),
        round(start.green() + (end.green() - start.green()) * ratio),
        round(start.blue() + (end.blue() - start.blue()) * ratio),
        round(start.alpha() + (end.alpha() - start.alpha()) * ratio),
    )


class _ChoiceBase(QAbstractButton):
    """带文字的方形/圆形选择控件基类。"""

    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(field_font("md"))
        self.setText(text)
        self._hover = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        label = self.text()
        width = BOX_SIZE + (LABEL_GAP + metrics.horizontalAdvance(label) if label else 0)
        return QSize(width + 2, max(BOX_SIZE, metrics.height()) + 4)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return self.sizeHint()

    def _box_rect(self) -> QRectF:
        return QRectF(1, (self.height() - BOX_SIZE) / 2, BOX_SIZE, BOX_SIZE)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _label_offset(self) -> int:
        """文字起点（开关的轨道比方框宽，需覆盖）。"""
        return BOX_SIZE

    def _paint_label(self, painter: QPainter, palette: dict) -> None:
        label = self.text()
        if not label:
            return
        offset = self._label_offset()
        painter.setPen(QColor(palette["text"]))
        painter.drawText(
            QRectF(offset + LABEL_GAP, 0, self.width() - offset - LABEL_GAP, self.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            label,
        )

    def _paint_focus_ring(self, painter: QPainter, rect: QRectF, palette: dict) -> None:
        if not self.hasFocus():
            return
        ring = QColor(palette["focus_border"])
        ring.setAlpha(90)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ring, 2))
        painter.drawEllipse(rect.adjusted(-2, -2, 2, 2))

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        if not self.isEnabled():
            painter.setOpacity(0.5)
        self._paint_box(painter, palette)
        self._paint_label(painter, palette)
        painter.end()

    def _paint_box(self, painter: QPainter, palette: dict) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)


class CCheckbox(_ChoiceBase):
    """复选框（二态）。"""

    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(text, checked, parent)

    def _paint_box(self, painter: QPainter, palette: dict) -> None:
        rect = self._box_rect()
        accent = QColor(palette["focus_border"])
        checked = self.isChecked()
        background = accent if checked else QColor(palette["background"])
        border = accent if checked else QColor(palette["placeholder"] if self._hover else palette["control_border"])
        painter.setBrush(background)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 4, 4)

        if checked:
            draw_check(painter, rect.adjusted(4, 4, -4, -4), _CHECK_COLOR, 1.9)
        self._paint_focus_ring(painter, rect, palette)


class CRadioButton(_ChoiceBase):
    """单选按钮：同父级下自动互斥（Qt autoExclusive）。"""

    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(text, checked, parent)
        self.setAutoExclusive(True)

    def _paint_box(self, painter: QPainter, palette: dict) -> None:
        rect = self._box_rect().adjusted(1, 1, -1, -1)
        accent = QColor(palette["focus_border"])
        checked = self.isChecked()
        border = accent if checked else QColor(palette["placeholder"] if self._hover else palette["control_border"])
        painter.setBrush(QColor(palette["background"]))
        painter.setPen(QPen(border, 2 if checked else 1))
        painter.drawEllipse(rect)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(rect.center(), 5, 5)
        self._paint_focus_ring(painter, rect, palette)


class CToggleSwitch(_ChoiceBase):
    """开关：选中态滑块从左滑到右（160ms）。"""

    TRACK_WIDTH = 40
    TRACK_HEIGHT = 24
    KNOB_SIZE = 16
    DURATION = 160

    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(text, checked, parent)
        self._progress = 1.0 if checked else 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(self.DURATION)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_animated)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        label = self.text()
        width = self.TRACK_WIDTH + (LABEL_GAP + metrics.horizontalAdvance(label) if label else 0)
        return QSize(width + 2, max(self.TRACK_HEIGHT, metrics.height()) + 4)

    def _track_rect(self) -> QRectF:
        return QRectF(1, (self.height() - self.TRACK_HEIGHT) / 2, self.TRACK_WIDTH, self.TRACK_HEIGHT)

    def _label_offset(self) -> int:
        return self.TRACK_WIDTH

    def _on_animated(self, value) -> None:
        self._progress = float(value)
        self.update()

    def _animate(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        self._animation.stop()
        if not self.isVisible():
            self._progress = target
            self.update()
            return
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(target)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - 覆写 Qt 命名
        super().setChecked(checked)
        if not self.isVisible():
            self._progress = 1.0 if checked else 0.0
            self.update()

    def _paint_box(self, painter: QPainter, palette: dict) -> None:
        track = self._track_rect()
        accent = QColor(palette["focus_border"])
        off_color = QColor(palette["control_border"])
        background = mix_color(off_color, accent, self._progress)
        painter.setBrush(background)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        travel = track.width() - self.KNOB_SIZE - 4
        left = track.left() + 2 + travel * self._progress
        knob = QRectF(left, track.center().y() - self.KNOB_SIZE / 2, self.KNOB_SIZE, self.KNOB_SIZE)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(knob)

        if not self.isEnabled():
            return
        if self.hasFocus():
            ring = QColor(accent)
            ring.setAlpha(90)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(ring, 2))
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 14, 14)


__all__ = ["CCheckbox", "CRadioButton", "CToggleSwitch", "mix_color"]
