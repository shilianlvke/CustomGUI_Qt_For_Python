"""省略文本：宽度不足时按模式截断，并把全文放进 tooltip。

此前仓内有 3 份各写一遍的实现（自绘 ``painter.drawText`` 与两个 ``QLabel``
子类），行为还不一致（有的右省略、有的中省略、有的没有 tooltip）。统一到
本组件后：颜色/字体随全局样式，文本可选中，主题切换无需重绘逻辑。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class CElidedLabel(QLabel):
    """单行省略文本。

    Args:
        text: 完整文本。
        mode: ``Qt.TextElideMode``；``ElideRight``（默认）或 ``ElideMiddle``。
        tooltip_full: 悬停时是否显示完整文本（截断时才设置，避免无意义提示）。
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        tooltip_full: bool = True,
    ):
        super().__init__(parent)
        self._full_text = str(text)
        self._mode = mode
        self._tooltip_full = bool(tooltip_full)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._apply()

    # ------------------------------------------------------------------
    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._full_text = str(text)
        self._apply()

    def resizeEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        width = max(0, self.width() - self.contentsMargins().left() - self.contentsMargins().right())
        if width <= 0:
            elided = self._full_text
        else:
            elided = QFontMetrics(self.font()).elidedText(self._full_text, self._mode, width)
        if elided != self.text():
            QLabel.setText(self, elided)
        if self._tooltip_full and elided != self._full_text:
            self.setToolTip(self._full_text)
        else:
            self.setToolTip("")


__all__ = ["CElidedLabel"]
