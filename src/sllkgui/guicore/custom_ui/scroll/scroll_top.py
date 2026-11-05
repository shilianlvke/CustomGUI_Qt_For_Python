"""滚动回顶按钮（Windows Fluent Design ScrollTop，带淡入淡出）。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QGraphicsOpacityEffect, QScrollArea

from sllkgui.appcore import AppSettings

from ...acrylic import glass_surface
from ..display.palette import tokens
from ..paint_utils import draw_chevron


class CScrollTop(QAbstractButton):
    """浮动回顶按钮：点击后带动画回到绑定的 ``QScrollArea`` 顶部。"""

    def __init__(
        self,
        scroll_area: QScrollArea,
        size: int | None = None,
        margin: int | None = None,
        parent=None,
    ):
        super().__init__(scroll_area if parent is None else parent)
        # 几何与动画参数来自 settings（构造时读取，避免导入期触发配置加载）
        config = AppSettings.scroll_top
        if size is None:
            size = int(config.size)
        if margin is None:
            margin = int(config.margin)
        self._threshold = int(config.threshold)
        self._fade_ms = int(config.fade_duration)
        self._scroll_ms = int(config.scroll_duration)

        self._scroll_area = scroll_area
        self._margin = max(0, int(margin))
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("回到顶部")

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(self._fade_ms)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(self._hide_if_transparent)
        self._scroll_animation: QPropertyAnimation | None = None

        bar = self._scroll_area.verticalScrollBar()
        bar.valueChanged.connect(self._on_scroll)
        self._scroll_area.installEventFilter(self)
        self.clicked.connect(self.scroll_to_top)
        self._reposition()
        self.hide()
        self._on_scroll(bar.value())

    # ------------------------------------------------------------------
    # 绑定与定位
    # ------------------------------------------------------------------
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    def _reposition(self) -> None:
        viewport = self._scroll_area.viewport().geometry()
        self.move(
            viewport.right() - self.width() - self._margin,
            viewport.bottom() - self.height() - self._margin,
        )

    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if watched is self._scroll_area and event.type() in (QEvent.Resize, QEvent.Show):
            self._reposition()
            if self.isVisible():
                self.raise_()
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # 显隐
    # ------------------------------------------------------------------
    def _on_scroll(self, value: int) -> None:
        bar = self._scroll_area.verticalScrollBar()
        target = 1.0 if value > bar.minimum() + self._threshold else 0.0
        self._fade_to(target)

    def _fade_to(self, target: float) -> None:
        current = self._effect.opacity()
        if target > 0 and not self.isVisible():
            self.show()
            self.raise_()
            current = 0.0
        self._fade.stop()
        self._fade.setStartValue(current)
        self._fade.setEndValue(target)
        self._fade.start()

    def _hide_if_transparent(self) -> None:
        if self._effect.opacity() <= 0.01:
            self.hide()

    def is_at_top(self) -> bool:
        return self._scroll_area.verticalScrollBar().value() <= self._threshold

    # ------------------------------------------------------------------
    # 回顶
    # ------------------------------------------------------------------
    def scroll_to_top(self) -> None:
        bar = self._scroll_area.verticalScrollBar()
        if bar.value() <= bar.minimum():
            return
        if self._scroll_animation is not None:
            self._scroll_animation.stop()
        animation = QPropertyAnimation(bar, b"value", self)
        animation.setDuration(self._scroll_ms)
        animation.setStartValue(bar.value())
        animation.setEndValue(bar.minimum())
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._scroll_animation = animation

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        # 浮在内容之上的按钮也跟随亚克力强度，保留最小不透明度避免文字干扰
        fill = glass_surface(palette["surface_strong"], AppSettings.glass.control, minimum=0.20)
        if self._hover:
            # 悬停用强调色淡底：旧实现取 border 色，和常态底色几乎同值，
            # 深色主题下几乎看不出悬停反馈。
            fill = glass_surface(palette["accent"], 0.18, minimum=0.18)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.setBrush(fill)
        painter.drawEllipse(rect)
        draw_chevron(painter, QPointF(rect.center()), palette["text"], 9, "up", 1.8)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


__all__ = ["CScrollTop"]
