"""图例分组框（复刻 PrimeVue Aura Fieldset）。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from AppCore import AppSettings

from ..paint_utils import draw_chevron
from .collapse import CollapseAnimator
from .style import panel_colors

#: 边框线相对控件顶部的偏移（给图例留出上半部分）
_BORDER_TOP = 10
_LEGEND_HEIGHT = 20
_LEGEND_GAP = 6


class CFieldset(QWidget):
    """带图例的分组框，可选折叠。"""

    expandedChanged = Signal(bool)

    def __init__(
        self,
        legend: str = "",
        toggleable: bool = False,
        collapsed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._legend = legend
        self._toggleable = toggleable
        self._expanded = not collapsed
        self._hover = False
        self._progress = 0.0
        self._font = QFont(AppSettings.family)
        self._font.setPixelSize(13)
        self._font.setWeight(QFont.Weight.DemiBold)
        if toggleable:
            self.setCursor(Qt.PointingHandCursor)

        self._wrapper = QWidget(self)
        self._wrapper.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self._wrapper)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, _BORDER_TOP + 18, 14, 14)
        layout.setSpacing(0)
        layout.addWidget(self._wrapper)

        self._animator = CollapseAnimator(self._wrapper, self._expanded, self)
        self._animator.progressChanged.connect(self._on_progress)

    # ------------------------------------------------------------------
    def _on_progress(self, progress: float) -> None:
        if abs(progress - self._progress) > 1e-3:
            self._progress = progress
            self.update()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        expanded = bool(expanded)
        if expanded == self._expanded and not self._animator.is_running():
            return
        self._expanded = expanded
        self._animator.set_expanded(expanded, animate)
        self.expandedChanged.emit(expanded)

    def toggle(self) -> None:
        if self._toggleable:
            self.set_expanded(not self._expanded)

    def set_legend(self, legend: str) -> None:
        self._legend = legend
        self.update()

    def legend(self) -> str:
        return self._legend

    # ------------------------------------------------------------------
    def _legend_width(self) -> float:
        if not self._legend:
            return 0.0
        metrics = QFontMetrics(self._font)
        width = metrics.horizontalAdvance(self._legend) + 16
        if self._toggleable:
            width += 18
        return float(width)

    def _legend_rect(self) -> QRectF:
        return QRectF(14, _BORDER_TOP - _LEGEND_HEIGHT / 2, self._legend_width(), _LEGEND_HEIGHT)

    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()

        border = QRectF(0.5, _BORDER_TOP + 0.5, self.width() - 1, self.height() - _BORDER_TOP - 1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colors["background"]))
        painter.drawRoundedRect(border, 8, 8)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawRoundedRect(border, 8, 8)

        if not self._legend:
            painter.end()
            return

        legend = self._legend_rect()
        # 在边框上给图例开口（只清 2px 的线，不破坏圆角）
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colors["background"]))
        painter.drawRect(QRectF(legend.left(), _BORDER_TOP - 1, legend.width(), 3))

        text_left = legend.left() + 8
        if self._toggleable:
            painter.save()
            painter.translate(QPointF(legend.left() + 8, _BORDER_TOP))
            painter.rotate(180 * self._progress)
            draw_chevron(painter, QPointF(0, 0), QColor(colors["muted"]), size=7, direction="down", width=1.5)
            painter.restore()
            text_left += 18

        painter.setFont(self._font)
        painter.setPen(QColor(colors["text"] if not self._hover else colors["accent"]))
        painter.drawText(
            QRectF(text_left, legend.top(), legend.right() - text_left, legend.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._legend,
        )
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._toggleable:
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._toggleable and event.button() == Qt.LeftButton:
            if event.position().y() <= _BORDER_TOP + _LEGEND_HEIGHT / 2:
                self.toggle()
                event.accept()
                return
        super().mouseReleaseEvent(event)


__all__ = ["CFieldset"]
