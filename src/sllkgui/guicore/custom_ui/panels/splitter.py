"""可拖拽分割器（复刻 PrimeVue Aura Splitter）。

基于 ``QSplitter``（拖拽、最小尺寸、嵌套都由 Qt 负责），只把抓手换成
自绘样式：整条 1px 分隔线 + 居中握把，悬停/拖动时主色高亮。
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QWidget

from .style import panel_colors, panel_settings, with_alpha


class CSplitterHandle(QSplitterHandle):
    """自绘抓手。"""

    def __init__(self, orientation, parent: QSplitter):
        super().__init__(orientation, parent)
        self._hover = False
        self.setMouseTracking(True)

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()
        _, _, _, grip = panel_settings()
        highlight = QColor(colors["accent"])
        track = QColor(colors["track"])

        horizontal = self.orientation() == Qt.Horizontal
        painter.setPen(Qt.NoPen)

        if self._hover:
            painter.setBrush(with_alpha(highlight, 40))
            painter.drawRect(self.rect())

        line_color = highlight if self._hover else QColor(colors["divider"])
        grip_color = highlight if self._hover else track

        if horizontal:
            x = self.width() / 2 - 0.5
            painter.setPen(QPen(line_color, 1))
            painter.drawLine(int(x), 4, int(x), self.height() - 4)
            length = min(grip, max(10, self.height() - 16))
            painter.setPen(QPen(grip_color, 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(int(x), int(self.height() / 2 - length / 2), int(x), int(self.height() / 2 + length / 2))
        else:
            y = self.height() / 2 - 0.5
            painter.setPen(QPen(line_color, 1))
            painter.drawLine(4, int(y), self.width() - 4, int(y))
            length = min(grip, max(10, self.width() - 16))
            painter.setPen(QPen(grip_color, 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(int(self.width() / 2 - length / 2), int(y), int(self.width() / 2 + length / 2), int(y))

        painter.end()


class CSplitter(QSplitter):
    """水平 / 垂直分割器。"""

    def __init__(
        self,
        orientation: str = "horizontal",
        handle_width: int | None = None,
        parent=None,
    ):
        qt_orientation = Qt.Vertical if orientation in ("vertical", "v") else Qt.Horizontal
        super().__init__(qt_orientation, parent)
        _, _, configured, _ = panel_settings()
        self._handle_width = max(4, int(handle_width if handle_width is not None else configured))
        self.setHandleWidth(self._handle_width)
        self.setChildrenCollapsible(False)
        self.setOpaqueResize(True)
        self._weights: list[int] = []
        self._weights_applied = False

    # ------------------------------------------------------------------
    def createHandle(self):  # noqa: N802 - 覆写 Qt 命名
        return CSplitterHandle(self.orientation(), self)

    def add_panel(self, widget: QWidget, size: int | None = None, min_size: int | None = None) -> QWidget:
        """添加一个面板；``size`` 是比例权重，``min_size`` 是最小像素尺寸。"""
        self.addWidget(widget)
        if min_size is not None:
            if self.orientation() == Qt.Horizontal:
                widget.setMinimumWidth(max(0, int(min_size)))
            else:
                widget.setMinimumHeight(max(0, int(min_size)))
        self._weights.append(max(1, int(size)) if size is not None else 100)
        return widget

    def set_sizes(self, weights: list[int]) -> None:
        """按权重分配尺寸（总和自动换算为可用像素）。"""
        weights = [max(1, int(value)) for value in weights]
        if not weights:
            return
        if len(weights) < self.count():
            weights += [100] * (self.count() - len(weights))
        total = sum(weights)
        available = self.width() if self.orientation() == Qt.Horizontal else self.height()
        if available <= 1:
            available = 600
        available -= self.handleWidth() * (self.count() - 1)
        available = max(self.count() * 20, available)
        sizes = [max(20, int(available * weight / total)) for weight in weights]
        super().setSizes(sizes)

    def set_handle_width(self, width: int) -> None:
        self._handle_width = max(4, int(width))
        self.setHandleWidth(self._handle_width)

    def handle_width(self) -> int:
        return self._handle_width

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        # 首次显示后按声明的权重落位（此时才拿得到真实像素宽度）
        if not self._weights_applied and self._weights and len(self._weights) == self.count():
            self._weights_applied = True
            self.set_sizes(self._weights)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(360, 240)


__all__ = ["CSplitter", "CSplitterHandle"]
