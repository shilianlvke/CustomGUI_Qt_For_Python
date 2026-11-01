"""切换型按钮：ToggleButton（开/关标签）与 SelectButton（分段单选）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..button import CButton
from .input_style import RADIUS, colors, field_font, rounded_path, size_spec


class CToggleButton(CButton):
    """带 on/off 文案的切换按钮。

    选中时用实心主色，未选中用描边——与 Aura ``ToggleButton`` 的两种视觉一致。
    """

    def __init__(
        self,
        on_label: str = "Yes",
        off_label: str = "No",
        checked: bool = False,
        icon=None,
        severity: str = "primary",
        size: str = "md",
        parent=None,
    ):
        super().__init__(
            text=on_label if checked else off_label,
            icon=icon,
            severity=severity,
            variant="solid" if checked else "outlined",
            size=size,
            parent=parent,
        )
        self._on_label = on_label
        self._off_label = off_label
        self.setCheckable(True)
        self.setChecked(checked)
        self.toggled.connect(self._sync_state)
        self._lock_width()

    def _lock_width(self) -> None:
        """按较长的标签定宽，切换时按钮不抖动。"""
        metrics = QFontMetrics(self.font())
        text_width = max(metrics.horizontalAdvance(self._on_label), metrics.horizontalAdvance(self._off_label))
        icon_width = self._spec.icon_px + 8 if self._has_icon() else 0
        self.setMinimumWidth(text_width + icon_width + self._spec.padding_x * 2)

    def _sync_state(self, checked: bool) -> None:
        self.setText(self._on_label if checked else self._off_label)
        self.set_variant("solid" if checked else "outlined")

    def on_label(self) -> str:
        return self._on_label

    def off_label(self) -> str:
        return self._off_label


class CSelectButton(QWidget):
    """分段单选（Aura SelectButton）。"""

    selectionChanged = Signal(int)

    def __init__(self, options=(), index: int = 0, size: str = "md", parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._index = index if 0 <= index < len(self._options) else 0
        self._size = size
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(field_font(size))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(size_spec(size).height)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def current_index(self) -> int:
        return self._index

    def current_option(self) -> str:
        return self._options[self._index] if self._options else ""

    def set_index(self, index: int, emit: bool = True) -> None:
        if not self._options:
            return
        index = max(0, min(len(self._options) - 1, index))
        if index == self._index:
            return
        self._index = index
        self.update()
        if emit:
            self.selectionChanged.emit(index)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        width = sum(metrics.horizontalAdvance(option) + 24 for option in self._options) + 2
        return QSize(max(width, 120), size_spec(self._size).height)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _segment_width(self) -> float:
        return (self.width() - 2) / max(1, len(self._options))

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(palette["addon_background"]))
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(rounded_path(rect, RADIUS))

        if not self.isEnabled():
            painter.setOpacity(0.5)

        accent = QColor(palette["focus_border"])
        width = self._segment_width()
        for index, option in enumerate(self._options):
            cell = QRectF(1 + index * width + 2, 3, width - 4, self.height() - 6)
            if index == self._index:
                painter.setPen(Qt.NoPen)
                painter.setBrush(accent)
                painter.drawRoundedRect(cell, RADIUS - 1, RADIUS - 1)
                painter.setPen(QColor("#ffffff"))
            else:
                if index == self._hover and self.isEnabled():
                    fill = QColor(palette["hover_border"])
                    fill.setAlpha(36)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(fill)
                    painter.drawRoundedRect(cell, RADIUS - 1, RADIUS - 1)
                painter.setPen(QColor(palette["text"]))
            painter.drawText(cell, Qt.AlignCenter, option)
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, x: float) -> int:
        width = self._segment_width()
        index = int((x - 1) // width) if width > 0 else -1
        return index if 0 <= index < len(self._options) else -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position().x())
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self.isEnabled():
            return
        index = self._index_at(event.position().x())
        if index >= 0:
            self.set_index(index)


__all__ = ["CToggleButton", "CSelectButton"]
