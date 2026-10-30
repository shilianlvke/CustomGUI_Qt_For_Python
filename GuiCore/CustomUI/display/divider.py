"""分割线（复刻 PrimeVue Aura Divider）。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .palette import tokens

_STYLES = {
    "solid": Qt.SolidLine,
    "dashed": Qt.DashLine,
    "dotted": Qt.DotLine,
}


class CDivider(QWidget):
    """水平/垂直分割线，可带文字与对齐方式。"""

    def __init__(
        self,
        orientation: str = "horizontal",
        style: str = "solid",
        text: str = "",
        align: str = "center",
        parent=None,
    ):
        super().__init__(parent)
        self._orientation = "vertical" if orientation == "vertical" else "horizontal"
        self._line_style = _STYLES.get(style, Qt.SolidLine)
        self._text = text
        self._align = align if align in ("left", "center", "right") else "center"

        font = QFont(self.font())
        font.setPixelSize(12)
        self.setFont(font)
        if self._orientation == "vertical":
            self.setFixedWidth(21)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(20)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def orientation(self) -> str:
        return self._orientation

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        if self._orientation == "vertical":
            return QSize(21, 80)
        return QSize(120, 20)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _pen(self, palette: dict) -> QPen:
        pen = QPen(QColor(palette["surface_strong"]), 1)
        pen.setStyle(self._line_style)
        return pen

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        palette = tokens()
        painter.setPen(self._pen(palette))

        if self._orientation == "vertical":
            x = self.width() // 2
            painter.drawLine(QPoint(x, 0), QPoint(x, self.height()))
            painter.end()
            return

        y = self.height() // 2
        if not self._text:
            painter.drawLine(QPoint(0, y), QPoint(self.width(), y))
            painter.end()
            return

        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self._text)
        gap = 12
        if self._align == "left":
            text_left = 0
        elif self._align == "right":
            text_left = self.width() - text_width
        else:
            text_left = (self.width() - text_width) / 2
        text_left = max(0, min(text_left, self.width() - text_width))

        painter.drawLine(QPoint(0, y), QPoint(int(text_left - gap), y))
        painter.drawLine(
            QPoint(int(text_left + text_width + gap), y),
            QPoint(self.width(), y),
        )
        painter.setPen(QColor(palette["muted"]))
        painter.drawText(
            QRectF(text_left, 0, text_width, self.height()),
            Qt.AlignCenter,
            self._text,
        )
        painter.end()


__all__ = ["CDivider"]
