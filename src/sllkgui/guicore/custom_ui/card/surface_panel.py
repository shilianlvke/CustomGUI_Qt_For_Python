"""圆角表面面板：只画底色 + 1px 描边，不做布局。

``CCard`` 走 QSS（``#CCard_Frame``），加几何参数需要 repolish，和"样式缓存 +
主题热切换"的机制冲突；需要自定义圆角/描边的自绘页面用本组件，颜色仍取自
``panel_colors()``，主题切换时随重绘更新。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..panels.style import RADIUS, paint_surface, panel_colors


class CSurfacePanel(QWidget):
    """圆角面板容器：``radius`` / ``background`` / ``border`` 可覆盖主题默认值。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        radius: float | None = None,
        background: QColor | str | None = None,
        border: QColor | str | None = None,
    ):
        super().__init__(parent)
        self._radius = RADIUS if radius is None else float(radius)
        self._background = background
        self._border = border
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_surface(
        self,
        *,
        radius: float | None = None,
        background: QColor | str | None = None,
        border: QColor | str | None = None,
    ) -> None:
        if radius is not None:
            self._radius = float(radius)
        self._background = background
        self._border = border
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_surface(
            painter,
            rect,
            self._radius,
            background=self._background or colors["background"],
            border=self._border if self._border is not None else colors["border"],
        )
        painter.end()


__all__ = ["CSurfacePanel"]
