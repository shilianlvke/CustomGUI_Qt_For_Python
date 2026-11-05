"""下拉浮层基础件：浮层容器、选项列表、树形列表。

三者被 ``CSelect`` / ``CMultiSelect`` / ``CAutoComplete`` / ``CTreeSelect`` /
``CDatePicker`` / ``CColorPicker`` 共用。浮层用 ``Qt.Popup``，点击外部自动关闭，
因此外观（底色、边框、圆角、阴影）全部自绘，与主题调色板实时同步。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from customgui.appcore import AppSettings

from ..menu.menu_list import menu_colors
from ..paint_utils import draw_check, draw_chevron, draw_shadow
from .input_style import colors, rounded_path

#: 列表行高的兼容兜底值（运行时以 :func:`row_height` 为准）
ROW_HEIGHT = 34
#: 浮层最多展开行数的兼容兜底值（运行时以 :func:`max_visible_rows` 为准）
MAX_VISIBLE_ROWS = 8
#: 列表上下留白（无对应配置，保持常量）
LIST_PADDING = 3

#: 浮层阴影边距（左, 上, 右, 下）——Aura 的 ``overlay.navigation.shadow`` 比按钮大一圈，
#: 圆角外不再是一块「透明的直角缺口」，而是被阴影包住的悬浮卡片
POPOVER_SHADOW = (8, 4, 8, 14)
#: 内衬的兼容兜底值（运行时以 :func:`popover_inset` 为准）
POPOVER_INSET = 6


def row_height() -> int:
    """列表行高（运行时读取 ``AppSettings.input.row_height``）。"""
    return int(AppSettings.input.row_height)


def max_visible_rows() -> int:
    """浮层最多直接展开的行数（读取 ``AppSettings.input.popover_max_rows``）。"""
    return int(AppSettings.input.popover_max_rows)


def popover_inset() -> int:
    """内容与浮层本体内衬（读取 ``AppSettings.input.popover_inset``）。"""
    return int(AppSettings.input.popover_inset)


def list_font() -> QFont:
    font = QFont(AppSettings.family)
    font.setPixelSize(14)
    return font


class CPopover(QFrame):
    """圆角浮层容器（``Qt.Popup``：点外部自动关闭）。

    外观分三层，缺一层右下角就会露出「透明的直角」：

    1. **本体**：``paintEvent`` 用圆角路径铺底色 + 1px 描边，路径以外 alpha=0；
    2. **阴影**：用 ``paint_utils.draw_shadow`` 在本体外圈画 Aura 的浮层阴影，
       否则半透明窗口的圆角直接叠在页面上，看着像缺了一块；
    3. **内衬**：内容距本体至少 :data:`POPOVER_INSET`，保证任何子控件（列表的悬停行、
       日历的日期圆点、色板网格）都不会画进圆角里把它「削」成直角。
    """

    closed = Signal()

    def __init__(self, parent=None, width: int = 220, radius: int = 8):
        # NoDropShadowWindowHint：不要系统那种矩形投影，否则透明圆角处会多出一个直角阴影
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("CPopover")
        self._radius = radius
        self._body_width = width
        inset = popover_inset()
        left, top, right, bottom = POPOVER_SHADOW
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            left + inset,
            top + inset,
            right + inset,
            bottom + inset,
        )
        self._layout.setSpacing(4)
        self.setFixedWidth(width + left + right)

    def content_layout(self) -> QVBoxLayout:
        return self._layout

    def body_width(self) -> int:
        """浮层本体的宽度（不含阴影边距）。"""
        return self._body_width

    def _body_rect(self) -> QRectF:
        left, top, right, bottom = POPOVER_SHADOW
        return QRectF(self.rect()).adjusted(left, top, -right, -bottom)

    # ------------------------------------------------------------------
    # 绘制与定位
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 浮层必须使用菜单级高不透明度底色；输入控件的 22% 玻璃底会让
        # 页面正文透出，导致弹层文字与底层内容互相干扰。
        palette = menu_colors()
        body = self._body_rect()
        path = rounded_path(body, self._radius)

        draw_shadow(painter, path, body, self._radius)
        painter.fillPath(path, QColor(palette["background"]))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(rounded_path(body.adjusted(0.5, 0.5, -0.5, -0.5), self._radius))
        painter.end()

    def show_at(self, anchor: QWidget) -> None:
        """贴住控件下方展开；空间不足时翻到上方，并同时受屏幕与宿主窗口约束。"""
        self.adjustSize()
        left, top, right, bottom = POPOVER_SHADOW
        body_width = self.width() - left - right
        body_height = self.height() - top - bottom
        origin = anchor.mapToGlobal(QPoint(0, 0))
        position = QPoint(origin.x(), origin.y() + anchor.height() + 6)

        screen = QGuiApplication.screenAt(origin)
        bounds = screen.availableGeometry() if screen is not None else None
        # 弹层是 Qt.Popup 顶层窗口，只按屏幕夹紧会盖住版权栏甚至伸出宿主窗口；
        # 这里把可用范围再与宿主窗口求交，保证气泡完整落在窗口内。
        host = anchor.window()
        if host is not None and host.isVisible():
            host_rect = QRect(host.mapToGlobal(QPoint(0, 0)), host.size())
            bounds = host_rect if bounds is None else bounds.intersected(host_rect)

        if bounds is not None:
            if position.y() + body_height > bounds.bottom() + 1:
                flipped = origin.y() - body_height - 6
                if flipped >= bounds.top():
                    position.setY(flipped)
                else:
                    position.setY(bounds.bottom() + 1 - body_height)
            if position.y() < bounds.top():
                position.setY(bounds.top())
            position.setX(max(bounds.left(), min(position.x(), bounds.right() + 1 - body_width)))
        # 定位以「本体」左上角为准，阴影边距要减掉
        self.move(position - QPoint(left, top))
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
        self._row_height = row_height()
        self._max_rows = max_visible_rows()
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
        return max(1, len(self._visible)) * self._row_height + LIST_PADDING * 2

    def _viewport_height(self) -> int:
        rows = max(1, min(len(self._visible), self._max_rows))
        return rows * self._row_height + LIST_PADDING * 2

    def _max_scroll(self) -> int:
        return max(0, self._content_height() - self.height())

    def _sync_height(self) -> None:
        self.setFixedHeight(self._viewport_height())
        self._scroll = max(0, min(self._scroll, self._max_scroll()))

    def set_preferred_height(self, height: int) -> None:
        """强制列表高度（Listbox 用固定高度）。"""
        self._preferred_height = max(self._row_height + LIST_PADDING * 2, height)
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
            top = LIST_PADDING + row * self._row_height - self._scroll
            if top + self._row_height < 0 or top > self.height():
                continue
            item = QRectF(4, top + 1, self.width() - 8, self._row_height - 2)
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
        row = int((position.y() + self._scroll - LIST_PADDING) // self._row_height)
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
        self._row_height = row_height()
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
        self.setFixedHeight(max(1, len(self._rows)) * self._row_height + LIST_PADDING * 2)
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
            top = LIST_PADDING + row * self._row_height
            item = QRectF(4, top + 1, self.width() - 8, self._row_height - 2)
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
        row = int((position.y() - LIST_PADDING) // self._row_height)
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


__all__ = [
    "CPopover",
    "COptionList",
    "CTreeList",
    "ROW_HEIGHT",
    "MAX_VISIBLE_ROWS",
    "POPOVER_SHADOW",
    "POPOVER_INSET",
    "row_height",
    "max_visible_rows",
    "popover_inset",
    "list_font",
]
