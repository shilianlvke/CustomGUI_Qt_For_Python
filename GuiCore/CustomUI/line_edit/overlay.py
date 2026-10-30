"""下拉浮层基础件：浮层容器、选项列表、树形列表。

三者被 ``CSelect`` / ``CMultiSelect`` / ``CAutoComplete`` / ``CTreeSelect`` /
``CDatePicker`` / ``CColorPicker`` 共用。浮层用 ``Qt.Popup``，点击外部自动关闭，
因此外观（底色、边框、圆角）全部自绘，与主题调色板实时同步。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from AppCore import AppSettings

from .input_style import colors, rounded_path
from ..paint_utils import draw_check, draw_chevron

#: 列表行高（Aura 菜单项约 2.25rem）
ROW_HEIGHT = 34
#: 浮层最多直接展开的行数，超出后滚动
MAX_VISIBLE_ROWS = 8
#: 列表上下留白
LIST_PADDING = 3


def list_font() -> QFont:
    font = QFont(AppSettings.family)
    font.setPixelSize(14)
    return font


class CPopover(QFrame):
    """圆角浮层容器（``Qt.Popup``：点外部自动关闭）。"""

    closed = Signal()

    def __init__(self, parent=None, width: int = 220, radius: int = 8):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("CPopover")
        self._radius = radius
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self.setFixedWidth(width)

    def content_layout(self) -> QVBoxLayout:
        return self._layout

    # ------------------------------------------------------------------
    # 绘制与定位
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(palette["background"]))
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(rounded_path(rect, self._radius))
        painter.end()

    def show_at(self, anchor: QWidget) -> None:
        """贴住控件下方展开；下方空间不足时翻到上方。"""
        self.adjustSize()
        origin = anchor.mapToGlobal(QPoint(0, 0))
        position = QPoint(origin.x(), origin.y() + anchor.height() + 6)
        screen = QGuiApplication.screenAt(origin)
        if screen is not None:
            area = screen.availableGeometry()
            if position.y() + self.height() > area.bottom():
                position.setY(origin.y() - self.height() - 6)
            position.setX(max(area.left(), min(position.x(), area.right() - self.width())))
        self.move(position)
        self.show()
        self.raise_()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().hideEvent(event)
        self.closed.emit()


class COptionList(QWidget):
    """可滚动的选项列表（单选/多选通用）。"""

    activated = Signal(int)

    def __init__(self, options=(), selected=(), multi: bool = False, parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._selected = set(selected)
        self._multi = multi
        self._filter = ""
        self._hover = -1
        self._scroll = 0
        self._preferred_height: int | None = None
        self._visible: list[int] = list(range(len(self._options)))
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(list_font())
        self._sync_height()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_options(self, options) -> None:
        self._options = list(options)
        self._selected = {index for index in self._selected if index < len(self._options)}
        self._apply_filter()

    def options(self) -> list[str]:
        return list(self._options)

    def set_filter(self, text: str) -> None:
        self._filter = text or ""
        self._scroll = 0
        self._apply_filter()

    def visible_count(self) -> int:
        return len(self._visible)

    def set_selected(self, indices) -> None:
        self._selected = {index for index in indices if 0 <= index < len(self._options)}
        self.update()

    def selected_indices(self) -> list[int]:
        return sorted(self._selected)

    def current_index(self) -> int:
        return next(iter(self._selected), -1)

    def first_visible_index(self) -> int:
        return self._visible[0] if self._visible else -1

    def _apply_filter(self) -> None:
        needle = self._filter.strip().lower()
        if needle:
            self._visible = [index for index, text in enumerate(self._options) if needle in str(text).lower()]
        else:
            self._visible = list(range(len(self._options)))
        self._sync_height()
        self.update()

    def _content_height(self) -> int:
        return max(1, len(self._visible)) * ROW_HEIGHT + LIST_PADDING * 2

    def _viewport_height(self) -> int:
        rows = max(1, min(len(self._visible), MAX_VISIBLE_ROWS))
        return rows * ROW_HEIGHT + LIST_PADDING * 2

    def _max_scroll(self) -> int:
        return max(0, self._content_height() - self.height())

    def _sync_height(self) -> None:
        self.setFixedHeight(self._viewport_height())
        self._scroll = max(0, min(self._scroll, self._max_scroll()))

    def set_preferred_height(self, height: int) -> None:
        """强制列表高度（Listbox 用固定高度）。"""
        self._preferred_height = max(ROW_HEIGHT + LIST_PADDING * 2, height)
        self.setFixedHeight(self._preferred_height)
        self._scroll = max(0, min(self._scroll, self._max_scroll()))

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        accents = QColor(palette["focus_border"])
        metrics = QFontMetrics(self.font())

        for row, index in enumerate(self._visible):
            top = LIST_PADDING + row * ROW_HEIGHT - self._scroll
            if top + ROW_HEIGHT < 0 or top > self.height():
                continue
            item = QRectF(4, top + 1, self.width() - 8, ROW_HEIGHT - 2)
            if index in self._selected:
                fill = QColor(accents)
                fill.setAlpha(38)
                painter.setBrush(fill)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(item, 6, 6)
            elif index == self._hover:
                fill = QColor(palette["hover_border"])
                fill.setAlpha(34)
                painter.setBrush(fill)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(item, 6, 6)

            color = QColor(accents) if index in self._selected else QColor(palette["text"])
            painter.setPen(color)
            text = metrics.elidedText(str(self._options[index]), Qt.ElideRight, int(item.width()) - 46)
            painter.drawText(
                QRectF(item.left() + 10, item.top(), item.width() - 44, item.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                text,
            )
            if index in self._selected:
                draw_check(painter, QRectF(item.right() - 24, item.center().y() - 7, 14, 14), accents, 1.7)

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, position) -> int:
        row = int((position.y() + self._scroll - LIST_PADDING) // ROW_HEIGHT)
        if 0 <= row < len(self._visible):
            return self._visible[row]
        return -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index >= 0:
            self.activated.emit(index)

    def wheelEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._max_scroll() <= 0:
            return
        step = event.angleDelta().y() // 3
        self._scroll = max(0, min(self._max_scroll(), self._scroll - step))
        self.update()


class CTreeList(QWidget):
    """树形选项列表（``CTreeSelect`` 用）。

    节点格式：``{"label": str, "children": [...]}``；默认全部展开，点击箭头折叠。
    """

    activated = Signal(str)

    def __init__(self, nodes=(), parent=None):
        super().__init__(parent)
        self._nodes = list(nodes)
        self._collapsed: set[str] = set()
        self._rows: list[tuple[int, dict, bool, bool, str]] = []
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(list_font())
        self._rebuild()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _rebuild(self) -> None:
        self._rows = []
        self._walk(self._nodes, 0, "")
        self.setFixedHeight(max(1, len(self._rows)) * ROW_HEIGHT + LIST_PADDING * 2)
        self.update()

    def _walk(self, nodes, depth: int, prefix: str) -> None:
        for order, node in enumerate(nodes):
            path = f"{prefix}/{order}"
            children = node.get("children") or []
            expanded = bool(children) and path not in self._collapsed
            self._rows.append((depth, node, bool(children), expanded, path))
            if children and expanded:
                self._walk(children, depth + 1, path)

    def _toggle(self, path: str) -> None:
        if path in self._collapsed:
            self._collapsed.discard(path)
        else:
            self._collapsed.add(path)
        self._rebuild()

    def labels(self) -> list[str]:
        return [row[1].get("label", "") for row in self._rows]

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        accent = QColor(palette["focus_border"])
        metrics = QFontMetrics(self.font())

        for row, (depth, node, has_children, expanded, _path) in enumerate(self._rows):
            top = LIST_PADDING + row * ROW_HEIGHT
            item = QRectF(4, top + 1, self.width() - 8, ROW_HEIGHT - 2)
            if row == self._hover:
                fill = QColor(palette["hover_border"])
                fill.setAlpha(34)
                painter.setBrush(fill)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(item, 6, 6)

            left = item.left() + 8 + depth * 16
            if has_children:
                center = QPointF(left + 5, item.center().y())
                draw_chevron(painter, center, palette["text"], 7, "down" if expanded else "right", 1.4)
            left += 16

            painter.setPen(QColor(palette["text"]))
            text = metrics.elidedText(str(node.get("label", "")), Qt.ElideRight, int(item.right() - left - 8))
            painter.drawText(
                QRectF(left, item.top(), item.right() - left - 8, item.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                text,
            )
            if node.get("children"):
                painter.setPen(QPen(QColor(accent), 1))
                painter.drawPoint(QPointF(item.right() - 12, item.center().y()))

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _row_at(self, position) -> int:
        row = int((position.y() - LIST_PADDING) // ROW_HEIGHT)
        return row if 0 <= row < len(self._rows) else -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        row = self._row_at(event.position())
        if row != self._hover:
            self._hover = row
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        row = self._row_at(event.position())
        if row < 0:
            return
        depth, node, has_children, _expanded, path = self._rows[row]
        hit_left = 4 + 8 + depth * 16
        if has_children and event.position().x() <= hit_left + 18:
            self._toggle(path)
            return
        self.activated.emit(str(node.get("label", "")))


__all__ = ["CPopover", "COptionList", "CTreeList", "ROW_HEIGHT", "list_font"]
