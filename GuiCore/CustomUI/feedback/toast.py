"""浮出通知（复刻 PrimeVue Aura Toast，带堆叠与自动消失）。"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import ColorPalette

from ..button.severity import normalize_severity
from ..display.palette import tokens
from ..close_button import CCloseButton as _CloseButton
from .message import _MessageIcon

_WIDTH = 340
_SHADOW = 5


def _settings() -> tuple[int, int, int, int, int]:
    """(life, max, duration, margin, spacing)，配置缺失时回落到默认值。"""
    try:
        from AppCore import AppSettings

        cfg = AppSettings.feedback
        return (
            int(cfg.toast_life),
            max(1, int(cfg.toast_max)),
            int(cfg.toast_duration),
            int(cfg.toast_margin),
            int(cfg.toast_spacing),
        )
    except Exception:
        return 3000, 4, 180, 20, 8


class CToast(QFrame):
    """右上角通知条：滑入淡入、定时消失、同窗口自动堆叠。"""

    closed = Signal()

    _stacks: dict[int, list[CToast]] = {}

    def __init__(
        self,
        parent: QWidget,
        text: str = "",
        title: str = "",
        severity: str = "info",
        life: int | None = None,
        offset_top: int = 0,
    ):
        super().__init__(parent)
        self._severity = normalize_severity(severity)
        self._closing = False
        self._offset_top = max(0, int(offset_top))
        self._life, _, self._duration, self._margin, self._spacing = _settings()
        if life is not None:
            self._life = max(0, int(life))

        self.setFixedWidth(_WIDTH + _SHADOW * 2)
        self.setAttribute(Qt.WA_StyledBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14 + _SHADOW, 12 + _SHADOW // 2, 10 + _SHADOW, 12 + _SHADOW)
        layout.setSpacing(10)

        self._icon = _MessageIcon(self._severity, parent=self)
        layout.addWidget(self._icon, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_label = QLabel(title, self)
        title_font = QFont(self.font())
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        self._title_label.setVisible(bool(title))
        text_layout.addWidget(self._title_label)

        self._text_label = QLabel(text, self)
        self._text_label.setWordWrap(True)
        text_font = QFont(self.font())
        text_font.setPixelSize(12)
        self._text_label.setFont(text_font)
        self._text_label.setVisible(bool(text))
        text_layout.addWidget(self._text_label)
        layout.addLayout(text_layout, 1)

        palette = tokens()
        self._close_button = _CloseButton(QColor(palette["muted"]), parent=self)
        self._close_button.clicked.connect(self.dismiss)
        layout.addWidget(self._close_button, 0, Qt.AlignTop)

        self._apply_colors()
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade: QPropertyAnimation | None = None
        self._slide: QPropertyAnimation | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        if self._life > 0:
            self._timer.start(self._life)

        parent.installEventFilter(self)

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def _apply_colors(self) -> None:
        # 构造期间 QFrame 会先收到 StyleChange/PaletteChange，此时标签还没建好
        if not hasattr(self, "_title_label"):
            return
        palette = tokens()
        dark = QColor(palette["surface"]).lightness() < 128
        self._title_label.setStyleSheet(f"color: {palette['text']}; background: transparent;")
        self._text_label.setStyleSheet(f"color: {palette['muted']}; background: transparent;")
        self._card = QColor(ColorPalette.custom_bg_one if dark else "#ffffff")
        self._border = QColor(palette["border"])

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._apply_colors()
            self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        card = QRectF(_SHADOW, _SHADOW // 2, _WIDTH, self.height() - _SHADOW * 2)

        for offset, alpha in ((4, 18), (2, 26), (1, 34)):
            shadow = QPainterPath()
            shadow.addRoundedRect(card.translated(0, offset), 6, 6)
            painter.fillPath(shadow, QColor(0, 0, 0, alpha))

        path = QPainterPath()
        path.addRoundedRect(card, 6, 6)
        painter.fillPath(path, self._card)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._border, 1))
        painter.drawPath(path)
        painter.end()

    # ------------------------------------------------------------------
    # 显示 / 消失
    # ------------------------------------------------------------------
    @classmethod
    def show_message(
        cls,
        parent: QWidget,
        text: str,
        title: str = "",
        severity: str = "info",
        life: int | None = None,
        offset_top: int = 0,
    ) -> CToast:
        """在 ``parent`` 右上角弹出一条通知（最新的排在最上面）。

        ``offset_top`` 用于避开标题栏等顶部区域。
        """
        _, limit, _, _, _ = _settings()
        key = id(parent)
        if key not in cls._stacks:
            # 父窗口销毁时清掉分组，避免 id 复用后串栈
            parent.destroyed.connect(lambda *_: cls._stacks.pop(key, None))
        stack = cls._stacks.setdefault(key, [])
        while len(stack) >= limit:
            stack[-1].dismiss(immediate=True)

        toast = cls(parent, text, title, severity, life, offset_top)
        toast.adjustSize()
        stack.insert(0, toast)
        toast.show()
        toast.raise_()
        cls._reflow(parent)

        target = toast.pos()
        toast.move(target.x() + 20, target.y())
        toast._opacity.setOpacity(0.0)

        fade = QPropertyAnimation(toast._opacity, b"opacity", toast)
        fade.setDuration(toast._duration)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.start()
        toast._fade = fade

        slide = QPropertyAnimation(toast, b"pos", toast)
        slide.setDuration(toast._duration)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.setStartValue(QPoint(target.x() + 20, target.y()))
        slide.setEndValue(target)
        slide.start()
        toast._slide = slide
        return toast

    @classmethod
    def clear(cls, parent: QWidget) -> None:
        for toast in list(cls._stacks.get(id(parent), [])):
            toast.dismiss(immediate=True)

    def dismiss(self, immediate: bool = False) -> None:
        if self._closing:
            return
        self._closing = True
        self._timer.stop()
        if immediate or self._duration <= 0 or not self.isVisible():
            self._finish()
            return
        self._timer.stop()
        fade = QPropertyAnimation(self._opacity, b"opacity", self)
        fade.setDuration(self._duration)
        fade.setStartValue(self._opacity.opacity())
        fade.setEndValue(0.0)
        fade.finished.connect(self._finish)
        fade.start()
        self._fade = fade

    def _finish(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            stack = self._stacks.get(id(parent), [])
            if self in stack:
                stack.remove(self)
            if not stack:
                self._stacks.pop(id(parent), None)
            else:
                self._reflow(parent)
        self.closed.emit()
        self.hide()
        self.deleteLater()

    @classmethod
    def _reflow(cls, parent: QWidget) -> None:
        stack = cls._stacks.get(id(parent), [])
        _, _, _, margin, spacing = _settings()
        y = margin
        for toast in stack:
            y = max(y, margin + toast._offset_top)
            # 新通知插入时，旧通知的滑入动画终点已过期，先停掉再重新落位
            if toast._slide is not None and toast._slide.state() == QAbstractAnimation.State.Running:
                toast._slide.stop()
            toast.move(parent.width() - toast.width() - margin, y)
            y += toast.height() + spacing

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self._reflow(watched)
        return super().eventFilter(watched, event)

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._life > 0 and not self._closing:
            self._timer.start(self._life)
        super().leaveEvent(event)


__all__ = ["CToast"]
