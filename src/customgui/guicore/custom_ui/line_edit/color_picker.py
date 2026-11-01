"""颜色选择器（复刻 PrimeVue Aura ColorPicker）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QGridLayout, QLabel, QVBoxLayout, QWidget

from .input_style import colors, rounded_path
from .overlay import CPopover

#: Aura 常用色板（8 列 × 3 行）
PALETTE = (
    "#ef4444",
    "#f97316",
    "#f59e0b",
    "#eab308",
    "#84cc16",
    "#22c55e",
    "#10b981",
    "#14b8a6",
    "#06b6d4",
    "#0ea5e9",
    "#3b82f6",
    "#6366f1",
    "#8b5cf6",
    "#a855f7",
    "#d946ef",
    "#ec4899",
    "#f43f5e",
    "#64748b",
    "#0f172a",
    "#ffffff",
    "#f1f5f9",
    "#94a3b8",
    "#475569",
    "#000000",
)

SWATCH = 40
CELL = 24


class _SwatchButton(QAbstractButton):
    """色板里的小色块。"""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(CELL, CELL)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def color(self) -> str:
        return self._color.name()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        painter.setBrush(self._color)
        painter.setPen(QPen(QColor(255, 255, 255, 90 if self._hover else 45), 1))
        painter.drawRoundedRect(rect, 4, 4)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


class CColorPicker(QWidget):
    """色块按钮：点击展开调色板，选择后回填。"""

    colorChanged = Signal(str)

    def __init__(self, color: str = "#568af2", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._popover: CPopover | None = None
        self._open = False
        self._label: QLabel | None = None
        self.setFixedSize(SWATCH, SWATCH)
        self.setCursor(Qt.PointingHandCursor)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def color(self) -> str:
        return self._color.name()

    def set_color(self, color: str, emit: bool = True) -> None:
        candidate = QColor(color)
        if not candidate.isValid():
            return
        self._color = candidate
        if self._label is not None:
            self._label.setText(self._color.name().upper())
        self.update()
        if emit:
            self.colorChanged.emit(self._color.name())

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(self._color)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(rounded_path(rect, 6))

        # 浅色色块加一圈内描边，避免与页面底色糊在一起
        if self._color.lightness() > 230:
            inner = rect.adjusted(1, 1, -1, -1)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
            painter.drawPath(rounded_path(inner, 5))
        painter.end()

    # ------------------------------------------------------------------
    # 弹层
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        if self._open:
            self.close_popup()
            return
        self._open = True
        popover = CPopover(self, width=CELL * 8 + 30)
        popover.content_layout().addWidget(self._build_content(popover))
        popover.closed.connect(self._on_closed)
        popover.show_at(self)
        self._popover = popover

    def _build_content(self, parent) -> QWidget:
        holder = QWidget(parent)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        for index, color in enumerate(PALETTE):
            button = _SwatchButton(color, holder)
            button.clicked.connect(lambda _checked=False, value=color: self._choose(value))
            grid.addWidget(button, index // 8, index % 8)
        layout.addLayout(grid)

        self._label = QLabel(self._color.name().upper(), holder)
        palette = colors()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(f"color: {palette['placeholder']}; font-size: 12px;")
        layout.addWidget(self._label)
        return holder

    def _choose(self, color: str) -> None:
        self.set_color(color)
        self.close_popup()

    def close_popup(self) -> None:
        if self._popover is not None:
            self._popover.hide()

    def _on_closed(self) -> None:
        popover = self._popover
        self._popover = None
        self._open = False
        self._label = None
        if popover is not None:
            popover.deleteLater()


__all__ = ["CColorPicker", "PALETTE"]
