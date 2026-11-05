"""折叠动画：手风琴与可折叠面板共用。

对内容容器做 ``maximumHeight`` 动画，并给出 0→1 的展开进度，
供标题栏的 chevron 同步旋转。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QObject, QVariantAnimation, Signal
from PySide6.QtWidgets import QWidget

from .style import panel_settings

_EXPANDED_MAX = 16777215


class CollapseAnimator(QObject):
    """驱动一个内容容器的展开/收起。"""

    #: 展开进度（0 = 完全收起，1 = 完全展开）
    progressChanged = Signal(float)
    #: 动画结束（参数为最终展开状态）
    finished = Signal(bool)

    def __init__(self, wrapper: QWidget, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._wrapper = wrapper
        self._expanded = bool(expanded)
        self._target = 0
        self._animation: QVariantAnimation | None = None
        if not expanded:
            wrapper.setMaximumHeight(0)
            wrapper.setVisible(False)

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def is_expanded(self) -> bool:
        return self._expanded

    def is_running(self) -> bool:
        return self._animation is not None and self._animation.state() == QVariantAnimation.State.Running

    def content_height(self) -> int:
        """内容在完全展开时的高度（含布局边距）。"""
        layout = self._wrapper.layout()
        if layout is not None:
            layout.activate()
            return max(0, layout.sizeHint().height())
        return max(0, self._wrapper.sizeHint().height())

    # ------------------------------------------------------------------
    # 动画
    # ------------------------------------------------------------------
    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        expanded = bool(expanded)
        if expanded == self._expanded and not self.is_running():
            return

        self._stop()
        self._expanded = expanded
        self._target = self.content_height() if expanded else 0
        start = self._wrapper.height() if self._wrapper.isVisible() else 0

        _, duration, _, _ = panel_settings()
        if not animate or duration <= 0 or start == self._target:
            self._finish(expanded)
            return

        if expanded:
            self._wrapper.setVisible(True)
        animation = QVariantAnimation(self)
        animation.setStartValue(start)
        animation.setEndValue(self._target)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(lambda value: self._on_tick(int(value)))
        animation.finished.connect(lambda: self._finish(expanded))
        animation.start()
        self._animation = animation

    def toggle(self, animate: bool = True) -> None:
        self.set_expanded(not self._expanded, animate)

    def _stop(self) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None

    def _on_tick(self, value: int) -> None:
        value = max(0, min(value, self._target))
        self._wrapper.setMaximumHeight(value)
        self.progressChanged.emit(self._progress(value))

    def _progress(self, value: int) -> float:
        if self._target <= 0:
            return 1.0 if self._expanded else 0.0
        return max(0.0, min(1.0, value / self._target))

    def _finish(self, expanded: bool) -> None:
        self._stop()
        if expanded:
            self._wrapper.setMaximumHeight(_EXPANDED_MAX)
            self._wrapper.setVisible(True)
        else:
            self._wrapper.setMaximumHeight(0)
            self._wrapper.setVisible(False)
        self.progressChanged.emit(1.0 if expanded else 0.0)
        self.finished.emit(expanded)


__all__ = ["CollapseAnimator"]
