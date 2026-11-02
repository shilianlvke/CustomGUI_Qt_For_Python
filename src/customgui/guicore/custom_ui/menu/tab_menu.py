"""标签式水平菜单。

与普通标签页不同，``CTabMenu`` 只提供一个水平切换条，不带内容区；激活项
下方绘制强调指示条，点击切换时发出 ``tabChanged(int)``。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..icon_utils import render_icon
from .menu_item import MenuItem, as_menu_item, normalize_items
from .menu_list import ICON_GAP, ICON_SIZE, ROW_RADIUS, menu_colors, menu_font

#: 标签条高度
TAB_HEIGHT = 38
#: 标签左右内边距
TAB_PADDING = 16
#: 激活指示条高度
INDICATOR_HEIGHT = 2


class CTabMenu(QWidget):
    """标签式水平菜单。

    使用 ``set_tabs`` / ``add_tab`` 提供标签，``set_current`` 切换激活项；
    用户点击标签时也会通过 ``tabChanged`` 通知当前索引。
    """

    tabChanged = Signal(int)

    def __init__(self, tabs=None, current: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("CTabMenu_Widget")
        self.setMouseTracking(True)
        self.setFont(menu_font(13))
        self.setFixedHeight(TAB_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._tabs: list[MenuItem] = []
        self._current = 0
        self._hover = -1
        self._rects: list[QRectF] = []
        self.set_tabs(tabs or [], current=current)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_tabs(self, tabs, current: int | None = None) -> None:
        """替换标签集合；当前索引越界时自动收敛。"""
        self._tabs = normalize_items(tabs)
        self._current = self._clamp(self._current if current is None else int(current))
        self._hover = -1
        self._measure()
        self.update()

    def add_tab(self, tab) -> None:
        self._tabs.append(as_menu_item(tab))
        if len(self._tabs) == 1:
            self._current = 0
        self._measure()
        self.update()

    def tabs(self) -> list[str]:
        return [item.label for item in self._tabs]

    def items(self):
        return list(self._tabs)

    def current_index(self) -> int:
        return self._current

    def set_current(self, index: int) -> None:
        """切换激活标签；索引变化时发出 ``tabChanged``。"""
        if not self._tabs:
            self._current = 0
            return
        target = self._clamp(index)
        if target == self._current:
            return
        self._current = target
        self.update()
        self.tabChanged.emit(target)

    def tab_rect(self, index: int) -> QRectF:
        """标签在控件内的矩形（测试与自定义命中判断用）。"""
        if 0 <= index < len(self._rects):
            return QRectF(self._rects[index])
        return QRectF()

    def _clamp(self, index: int) -> int:
        if not self._tabs:
            return 0
        return max(0, min(int(index), len(self._tabs) - 1))

    def _measure(self) -> None:
        metrics = QFontMetrics(self.font())
        rects: list[QRectF] = []
        x = 0.0
        for item in self._tabs:
            width = metrics.horizontalAdvance(item.label) + TAB_PADDING * 2
            if item.icon is not None:
                width += ICON_SIZE + ICON_GAP
            rects.append(QRectF(x, 0, float(width), TAB_HEIGHT))
            x += width
        self._rects = rects

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._measure()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = menu_colors()
        metrics = QFontMetrics(self.font())

        if self._rects:
            painter.setPen(QPen(QColor(colors["divider"]), 1))
            painter.drawLine(QPointF(0, TAB_HEIGHT - 1), QPointF(self.width(), TAB_HEIGHT - 1))

        for index, (item, rect) in enumerate(zip(self._tabs, self._rects, strict=False)):
            active = index == self._current
            hovered = index == self._hover and not item.disabled
            if active or hovered:
                painter.setPen(Qt.NoPen)
                fill = colors["header"] if active else colors["hover"]
                painter.setBrush(QColor(fill))
                painter.drawRoundedRect(rect.adjusted(2, 4, -2, -4), ROW_RADIUS, ROW_RADIUS)

            color = QColor(colors["muted"] if item.disabled else colors["accent"] if hovered else colors["text"])
            content = metrics.horizontalAdvance(item.label)
            if item.icon is not None:
                content += ICON_SIZE + ICON_GAP
            x = rect.center().x() - content / 2
            if item.icon is not None:
                pixmap = render_icon(item.icon, color, ICON_SIZE, self.devicePixelRatioF())
                if pixmap is not None:
                    painter.drawPixmap(int(x), int(rect.center().y() - ICON_SIZE / 2), pixmap)
                x += ICON_SIZE + ICON_GAP
            text_width = max(0.0, rect.right() - x - TAB_PADDING)
            painter.setPen(color)
            painter.drawText(
                QRectF(x, rect.top(), text_width, rect.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                metrics.elidedText(item.label, Qt.ElideRight, int(text_width)),
            )

            if active:
                painter.fillRect(
                    QRectF(rect.left() + TAB_PADDING, TAB_HEIGHT - INDICATOR_HEIGHT, max(0.0, rect.width() - TAB_PADDING * 2), INDICATOR_HEIGHT),
                    QColor(colors["accent"]),
                )
        painter.end()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        self._measure()
        width = int(self._rects[-1].right()) if self._rects else 0
        return QSize(max(160, width), TAB_HEIGHT)

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, position) -> int:
        for index, rect in enumerate(self._rects):
            if rect.contains(position):
                return index
        return -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            item = self._tabs[index] if 0 <= index < len(self._tabs) else None
            clickable = item is not None and not item.disabled and not item.separator
            self.setCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            index = self._index_at(event.position())
            if 0 <= index < len(self._tabs):
                item = self._tabs[index]
                if not item.disabled and not item.separator:
                    self.set_current(index)
                    if callable(item.command):
                        item.command()
                    event.accept()
                    return
        super().mouseReleaseEvent(event)


__all__ = ["CTabMenu", "TAB_HEIGHT"]
