"""水平菜单栏。

``CMenubar`` 只负责顶层项；鼠标悬停到带子项的条目时，在条目下方展开
``CMenuListPopup`` 下拉菜单。所有颜色取自调色板与设计令牌。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from sllkgui.appcore import AppSettings

from ..icon_utils import render_icon
from .menu_item import MenuItem, normalize_items
from .menu_list import ICON_GAP, ICON_SIZE, ROW_HEIGHT, ROW_RADIUS, CMenuListPopup, menu_colors, menu_font

#: 菜单栏高度
BAR_HEIGHT = 36
#: 顶层项左右内边距
BAR_PADDING = 12
#: 顶层分隔线宽度
BAR_SEPARATOR = 9


def _menubar_config() -> tuple[int, int, int]:
    """(菜单栏高度, 项左右内边距, 分隔线宽度)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.menus
        return int(cfg.bar_height), int(cfg.bar_padding), int(cfg.bar_separator)
    except Exception:
        return BAR_HEIGHT, BAR_PADDING, BAR_SEPARATOR


class _MenuBarBase(QWidget):
    """顶层菜单条（水平 / 垂直两种排布，供菜单栏与 MegaMenu 共用）。"""

    itemClicked = Signal(object)
    submenuOpened = Signal(object)

    def __init__(self, items=None, orientation: str = "horizontal", parent=None):
        super().__init__(parent)
        self._bar_height, self._bar_padding, self._bar_separator = _menubar_config()
        self.setObjectName("CMenubar_Widget")
        self.setMouseTracking(True)
        self.setFont(menu_font(14))
        self._items: list[MenuItem] = normalize_items(items)
        self._orientation = "vertical" if str(orientation).lower() == "vertical" else "horizontal"
        self._hover = -1
        self._active = -1
        self._rects: list[QRectF] = []
        self._popup = None
        self._sync_extent()
        self._measure()

    # ------------------------------------------------------------------
    # 数据与几何
    # ------------------------------------------------------------------
    def set_items(self, items) -> None:
        """替换顶层菜单项并关闭已展开的下拉菜单。"""
        self._close_popup()
        self._items = normalize_items(items)
        self._sync_extent()
        self._measure()
        self.update()

    def items(self) -> list[MenuItem]:
        return list(self._items)

    def orientation(self) -> str:
        """顶层项排布方向：``horizontal`` / ``vertical``。"""
        return self._orientation

    def active_index(self) -> int:
        return self._active

    def is_menu_open(self) -> bool:
        return self._popup is not None and self._popup.isVisible()

    def item_rect(self, index: int) -> QRectF:
        """顶层项在控件内的矩形。"""
        if 0 <= index < len(self._rects):
            return QRectF(self._rects[index])
        return QRectF()

    def _sync_extent(self) -> None:
        if self._orientation == "horizontal":
            self.setFixedHeight(self._bar_height)
        else:
            self.setFixedWidth(200)
            self.setFixedHeight(max(ROW_HEIGHT * len(self._items), ROW_HEIGHT))

    def _item_width(self, item: MenuItem, metrics: QFontMetrics) -> int:
        if item.separator:
            return self._bar_separator
        width = metrics.horizontalAdvance(item.label) + self._bar_padding * 2
        if item.icon is not None:
            width += ICON_SIZE + ICON_GAP
        return width

    def _measure(self) -> None:
        metrics = QFontMetrics(self.font())
        rects: list[QRectF] = []
        if self._orientation == "horizontal":
            x = 0.0
            for item in self._items:
                width = float(self._item_width(item, metrics))
                rects.append(QRectF(x, 0, width, self._bar_height))
                x += width
        else:
            for index in range(len(self._items)):
                rects.append(QRectF(0, index * ROW_HEIGHT, self.width(), ROW_HEIGHT))
        self._rects = rects

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        if self._orientation == "horizontal":
            width = sum(self._item_width(item, metrics) for item in self._items)
            return QSize(max(120, width), self._bar_height)
        return QSize(200, max(ROW_HEIGHT * len(self._items), ROW_HEIGHT))

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._measure()
        super().resizeEvent(event)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._measure()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = menu_colors()
        metrics = QFontMetrics(self.font())

        for index, (item, rect) in enumerate(zip(self._items, self._rects, strict=False)):
            if item.separator:
                painter.setPen(QPen(QColor(colors["divider"]), 1))
                if self._orientation == "horizontal":
                    x = rect.center().x()
                    painter.drawLine(QPointF(x, 6), QPointF(x, self.height() - 6))
                else:
                    y = rect.center().y()
                    painter.drawLine(QPointF(8, y), QPointF(self.width() - 8, y))
                continue

            active = index == self._active
            hovered = index == self._hover
            if active or hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(colors["header"] if active else colors["hover"]))
                painter.drawRoundedRect(rect.adjusted(2, 3, -2, -3), ROW_RADIUS, ROW_RADIUS)

            color = QColor(colors["accent"] if active else colors["muted"] if item.disabled else colors["text"])
            x = rect.left() + self._bar_padding
            if item.icon is not None:
                pixmap = render_icon(item.icon, color, ICON_SIZE, self.devicePixelRatioF())
                if pixmap is not None:
                    painter.drawPixmap(int(x), int(rect.center().y() - ICON_SIZE / 2), pixmap)
                x += ICON_SIZE + ICON_GAP

            available = max(0.0, rect.right() - x - self._bar_padding)
            painter.setPen(color)
            painter.drawText(
                QRectF(x, rect.top(), available, rect.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                metrics.elidedText(item.label, Qt.ElideRight, int(available)),
            )

            if active:
                if self._orientation == "horizontal":
                    rect_bar = QRectF(rect.left() + 8, rect.bottom() - 2, max(0.0, rect.width() - 16), 2)
                else:
                    rect_bar = QRectF(rect.left() + 2, rect.top() + 6, 2, max(0.0, rect.height() - 12))
                painter.fillRect(rect_bar, QColor(colors["accent"]))
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _item(self, index: int) -> MenuItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def _index_at(self, position) -> int:
        for index, rect in enumerate(self._rects):
            if rect.contains(position):
                return index
        return -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            item = self._item(index)
            clickable = item is not None and not item.disabled and not item.separator
            self.setCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)
            if clickable and item is not None and item.items:
                self.open_menu(index)
            elif self._active >= 0:
                self.close_menu()
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
            item = self._item(index)
            if item is not None and not item.disabled and not item.separator:
                if item.items:
                    self.open_menu(index)
                else:
                    self.itemClicked.emit(item)
                    if callable(item.command):
                        item.command()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # 下拉菜单
    # ------------------------------------------------------------------
    def open_menu(self, index: int) -> None:
        """展开指定顶层项的下拉菜单。"""
        item = self._item(index)
        if item is None or item.disabled or item.separator or not item.items:
            return
        self._close_popup()
        popup = self._create_popup(item)
        if popup is None:
            return
        self._popup = popup
        popup.itemClicked.connect(self._on_popup_item_clicked)
        popup.closed.connect(self._on_popup_closed)
        self._measure()
        rect = self._rects[index]
        if self._orientation == "horizontal":
            position = self.mapToGlobal(QPoint(int(rect.left()), int(rect.bottom()) + 4))
        else:
            position = self.mapToGlobal(QPoint(int(rect.right()) + 4, int(rect.top())))
        popup.show_at_global(position)
        self._active = index
        self.update()
        self.submenuOpened.emit(item)

    def close_menu(self) -> None:
        """收起当前下拉菜单。"""
        if self._popup is None:
            self._active = -1
            self.update()
            return
        self._close_popup()
        self.update()

    def _create_popup(self, item: MenuItem):
        return CMenuListPopup(item.items, width=220, parent=self)

    def _close_popup(self) -> None:
        popup = self._popup
        self._popup = None
        if popup is not None:
            popup.hide()
            popup.deleteLater()
        self._active = -1

    def _on_popup_item_clicked(self, item: MenuItem) -> None:
        self.itemClicked.emit(item)
        self.close_menu()

    def _on_popup_closed(self) -> None:
        self._popup = None
        self._active = -1
        self.update()


class CMenubar(_MenuBarBase):
    """水平菜单栏。

    顶层项悬停即展开下拉菜单；点击叶子项在 ``itemClicked`` 中回传
    :class:`MenuItem`，同时执行其 ``command``。
    """

    def __init__(self, items=None, parent=None):
        super().__init__(items, orientation="horizontal", parent=parent)
        self.setObjectName("CMenubar_Widget")


__all__ = ["CMenubar", "BAR_HEIGHT", "menu_font"]
