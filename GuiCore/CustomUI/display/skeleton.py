"""骨架屏（复刻 PrimeVue Aura Skeleton）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from .palette import tokens

_INTERVAL = 33


def _duration() -> int:
    try:
        from AppCore import AppSettings

        return max(300, int(AppSettings.feedback.skeleton_duration))
    except Exception:  # 配置上下文未就绪时不影响组件可用
        return 1400


class CSkeleton(QWidget):
    """占位骨架：矩形 / 圆形 / 文本行，带微光扫过动画。"""

    def __init__(
        self,
        width: int = 120,
        height: int = 16,
        shape: str = "rect",
        animation: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._shape = shape if shape in ("rect", "circle", "text") else "rect"
        self._animation = animation
        self._phase = 0.0
        self._duration = _duration()
        if self._shape == "circle":
            width = height
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_animation(self, enabled: bool) -> None:
        self._animation = enabled
        if enabled and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()
            self.update()

    def is_animating(self) -> bool:
        return self._timer.isActive()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self.width(), self.height())

    def _tick(self) -> None:
        self._phase = (self._phase + _INTERVAL / self._duration) % 1.0
        self.update()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        if self._animation:
            self._timer.start()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._timer.stop()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        if self._shape == "circle":
            path.addEllipse(rect)
        else:
            radius = rect.height() / 2 if self._shape == "text" else 6
            path.addRoundedRect(rect, radius, radius)
        return path

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        rect = QRectF(self.rect())
        path = self._path(rect)
        painter.fillPath(path, QColor(palette["surface_strong"]))

        if self._animation:
            band = max(48.0, rect.width() * 0.6)
            start = -band + (rect.width() + band) * self._phase
            gradient = QLinearGradient(start, 0, start + band, 0)
            dark = QColor(palette["surface_strong"]).lightness() < 128
            tone = QColor("#454e5f") if dark else QColor("#ffffff")
            highlight = QColor(tone)
            highlight.setAlpha(0)
            middle = QColor(tone)
            middle.setAlpha(170 if dark else 190)
            gradient.setColorAt(0.0, highlight)
            gradient.setColorAt(0.5, middle)
            gradient.setColorAt(1.0, highlight)
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(rect, gradient)
            painter.restore()
        painter.end()


__all__ = ["CSkeleton"]
