"""指标卡：说明在上、数值在下，数值用等宽字体。

仪表盘/概览页的通用原子件（此前只在插件管理页内部实现过一次）。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...fonts import mono_font
from ...styles import card_surface_color
from ..panels.style import RADIUS, paint_surface, panel_colors


class CMetricCard(QWidget):
    """固定尺寸的指标卡：``caption`` 说明 + ``value`` 数值。"""

    def __init__(
        self,
        caption: str = "",
        value: str | int = "0",
        parent: QWidget | None = None,
        *,
        width: int = 104,
        height: int = 66,
    ):
        super().__init__(parent)
        self._caption = str(caption)
        self._value = str(value)
        self.setFixedSize(int(width), int(height))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ------------------------------------------------------------------
    def caption(self) -> str:
        return self._caption

    def value(self) -> str:
        return self._value

    def set_caption(self, caption: str) -> None:
        self._caption = str(caption)
        self.update()

    def set_value(self, value: str | int) -> None:
        self._value = str(value)
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_surface(
            painter,
            rect,
            RADIUS,
            background=card_surface_color(),
            border=colors["border"],
        )

        caption_font = QFont(self.font())
        caption_font.setPixelSize(9)
        painter.setFont(caption_font)
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 10, rect.width() - 28, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._caption,
        )

        painter.setFont(mono_font(22))
        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 27, rect.width() - 28, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._value,
        )
        painter.end()


__all__ = ["CMetricCard"]
