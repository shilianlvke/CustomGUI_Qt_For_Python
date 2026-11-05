"""浮层卡片：圆角、描边、主题底色（对话框与抽屉共用）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame

from customgui.appcore import AppSettings, get_design_tokens

from ...acrylic import glass_surface
from ..display.palette import tokens


class COverlayCard(QFrame):
    """浮层内容卡片。"""

    def __init__(self, parent=None, radius: int = 10):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WA_StyledBackground, False)

    def setRadius(self, radius: int) -> None:  # noqa: N802 - 与 Qt 命名风格一致
        self._radius = max(0, int(radius))
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        # 底色取主题的 surface_app，并随亚克力强度轻微透出下层；对话框本身
        # 覆盖在遮罩之上，保留 90% 以上的不透明度，正文仍然清晰可读。
        background = glass_surface(
            get_design_tokens().colors.surface_app,
            AppSettings.glass.overlay_panel,
            minimum=0.90,
        )
        border = QColor(palette["border"])

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(path, background)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        painter.end()


__all__ = ["COverlayCard"]
