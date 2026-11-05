"""自绘菜单列表基类与弹层。

``CMenuList`` 负责菜单项的全部视觉（圆角、描边、悬停高亮、图标、分隔线、
子菜单箭头），颜色每次重绘时从 ``ColorPalette`` / 设计令牌读取，因此切换
主题后重绘即生效。``CMenuListPopup`` 在它之上套一层 ``Qt.Popup`` 窗口，
供菜单栏、右键菜单与子菜单复用。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from sllkgui.appcore import AppSettings, ColorPalette, get_design_tokens

from ...acrylic import glass_surface
from ..display.palette import tokens
from ..icon_utils import render_icon
from ..paint_utils import draw_chevron
from .menu_item import MenuItem, normalize_items

#: 列表上下留白
LIST_PADDING = 4
#: 菜单行高
ROW_HEIGHT = 36
#: 分隔线占用高度
SEPARATOR_HEIGHT = 9
#: 行内圆角（与 Fluent 菜单项一致）
ROW_RADIUS = 4
#: 行左右内缩
ROW_INSET = 4
#: 图标逻辑尺寸与图标/文字间距
ICON_SIZE = 16
ICON_GAP = 8
#: 每级子菜单缩进
INDENT = 16
#: 文字到行左边缘的距离
TEXT_PADDING = 12
#: 子菜单箭头预留宽度
ARROW_SPACE = 24


def _menu_list_config() -> tuple[int, int, int, int, int, int, int, int, int, int]:
    """(留白, 行高, 分隔线高, 行圆角, 行内缩, 图标, 图标间距, 缩进, 文字留白, 箭头预留)。"""
    try:
        cfg = AppSettings.menus
        return (
            int(cfg.list_padding),
            int(cfg.list_row_height),
            int(cfg.separator_height),
            int(cfg.row_radius),
            int(cfg.row_inset),
            int(cfg.icon_size),
            int(cfg.icon_gap),
            int(cfg.indent),
            int(cfg.text_padding),
            int(cfg.arrow_space),
        )
    except Exception:  # 配置上下文未就绪时用兜底值
        return (
            LIST_PADDING,
            ROW_HEIGHT,
            SEPARATOR_HEIGHT,
            ROW_RADIUS,
            ROW_INSET,
            ICON_SIZE,
            ICON_GAP,
            INDENT,
            TEXT_PADDING,
            ARROW_SPACE,
        )


def menu_font(size: int = 14, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """菜单族统一字体（像素字号，跟随应用字体族）。"""
    font = QFont(AppSettings.family)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def menu_colors() -> dict[str, str]:
    """当前主题下的菜单配色（全部取自调色板或中性色令牌）。

    - 底色跟随亚克力配置，并受「质感强度」影响；用高不透明度下限保证浮层
      文字不会与下层页面互相干扰。
    - hover/选中底色取 ``custom_dark_four``：浅色主题下比页面更深、深色主题
      下比页面更亮，避免旧实现（亮色主题用纯白）把悬停行"隐"进背景。

    返回值为 ``#AARRGGBB`` / 主题色字符串，既可直接交给 ``QColor`` 绘制，
    也可拼接进样式表，保持调用方原有的字符串约定。
    """
    base = tokens()
    accent = QColor(base["accent"])
    header = QColor(accent)
    header.setAlpha(38)
    # 延迟导入：button 包会反向依赖菜单浮层，模块级导入会形成循环。
    from ..button.severity import contrast_text

    def to_text(color: QColor) -> str:
        return color.name(QColor.NameFormat.HexArgb)

    return {
        "background": to_text(glass_surface(ColorPalette.custom_dark_one, AppSettings.glass.menu, minimum=0.85)),
        "header": to_text(header),
        "hover": ColorPalette.custom_dark_four,
        "border": base["border"],
        "divider": base["border"],
        "text": base["text"],
        "muted": base["muted"],
        "accent": base["accent"],
        "track": base["surface_strong"],
        # 强调色在 dracula 等主题中是浅粉/浅蓝，固定白字对比度不足；
        # 按实际亮度自动选择黑/白前景。
        "on_accent": to_text(contrast_text(accent)),
    }


@dataclass
class _Row:
    """一条可见行（展开后父子项按顺序铺开）。"""

    item: MenuItem
    depth: int
    path: str
    has_children: bool
    expanded: bool
    top: float = 0.0
    height: float = ROW_HEIGHT
    inset: float = ROW_INSET

    def rect(self, width: float) -> QRectF:
        height = max(1.0, self.height - 2)
        return QRectF(self.inset, self.top + 1, max(0.0, width - self.inset * 2), height)


class CMenuList(QWidget):
    """自绘菜单列表。

    两种模式：

    * ``inline=False``：只渲染顶层项，带子项的条目点击后发 ``submenuRequested``，
      由外层弹层负责展开（菜单栏 / 右键菜单使用）；
    * ``inline=True``：子项直接缩进展开在当前列表内，点击父项即展开/收起
      （分层菜单 / 面板菜单使用）。

    信号 ``itemClicked`` 携带 :class:`MenuItem` 本体，调用方可用 ``item.key``
    做业务分发。
    """

    itemClicked = Signal(object)
    itemHovered = Signal(object)
    submenuRequested = Signal(object)

    def __init__(
        self,
        items=None,
        width: int | None = 220,
        inline: bool = False,
        draw_surface: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        (
            self._list_padding,
            self._row_height,
            self._separator_height,
            self._row_radius,
            self._row_inset,
            self._icon_size,
            self._icon_gap,
            self._indent,
            self._text_padding,
            self._arrow_space,
        ) = _menu_list_config()
        self.setObjectName("CMenuList_Widget")
        self.setMouseTracking(True)
        self.setFont(menu_font())
        self._items: list[MenuItem] = normalize_items(items)
        self._inline = inline
        self._draw_surface = draw_surface
        self._expanded: set[str] = set()
        self._rows: list[_Row] = []
        self._hover = -1
        self._radius = get_design_tokens().radius.window
        if width is not None:
            self.setFixedWidth(width)
        self._refresh_rows()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_items(self, items) -> None:
        """替换全部菜单项，并清空展开状态。"""
        self._items = normalize_items(items)
        self._expanded.clear()
        self._refresh_rows()

    def items(self) -> list[MenuItem]:
        return list(self._items)

    def visible_items(self) -> list[MenuItem]:
        """当前实际可见的行（含已展开的子项）。"""
        return [row.item for row in self._rows]

    def row_count(self) -> int:
        return len(self._rows)

    def row_rect(self, index: int) -> QRectF:
        """可见行在控件内的矩形（测试与自定义命中判断用）。"""
        row = self._row(index)
        if row is None:
            return QRectF()
        width = self.width() if self.width() > 0 else self.sizeHint().width()
        return QRectF(0, row.top, width, row.height)

    # ------------------------------------------------------------------
    # 展开 / 收起
    # ------------------------------------------------------------------
    def expanded_paths(self) -> list[str]:
        return sorted(self._expanded)

    def is_expanded(self, path: str) -> bool:
        return path in self._expanded

    def expand(self, path: str) -> None:
        if path not in self._expanded:
            self._expanded.add(path)
            self._refresh_rows()

    def collapse(self, path: str) -> None:
        removed = {entry for entry in self._expanded if entry == path or entry.startswith(f"{path}/")}
        if removed:
            self._expanded -= removed
            self._refresh_rows()

    def toggle(self, path: str) -> None:
        if path in self._expanded:
            self.collapse(path)
        else:
            self.expand(path)

    def toggle_index(self, index: int) -> None:
        """按当前可见行号展开/收起。"""
        row = self._row(index)
        if row is not None and row.has_children:
            self.toggle(row.path)

    def expand_index(self, index: int) -> None:
        row = self._row(index)
        if row is not None and row.has_children:
            self.expand(row.path)

    def collapse_index(self, index: int) -> None:
        row = self._row(index)
        if row is not None:
            self.collapse(row.path)

    def _row(self, index: int) -> _Row | None:
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def _refresh_rows(self) -> None:
        self._rows = []
        self._walk(self._items, 0, "")
        top = float(self._list_padding)
        for row in self._rows:
            row.top = top
            row.height = self._separator_height if row.item.separator else self._row_height
            top += row.height
        self.setFixedHeight(max(int(top + self._list_padding), self._row_height + self._list_padding * 2))
        self.update()

    def _walk(self, items: list[MenuItem], depth: int, prefix: str) -> None:
        for index, item in enumerate(items):
            path = f"{prefix}/{index}"
            has_children = bool(item.items) and not item.separator
            expanded = has_children and path in self._expanded
            self._rows.append(_Row(item, depth, path, has_children, expanded, inset=float(self._row_inset)))
            if self._inline and has_children and expanded:
                self._walk(item.items, depth + 1, path)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = menu_colors()
        if self._draw_surface:
            body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(body, self._radius, self._radius)
            painter.fillPath(path, QColor(colors["background"]))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(colors["border"]), 1))
            painter.drawPath(path)

        metrics = QFontMetrics(self.font())
        dpr = self.devicePixelRatioF()
        for index, row in enumerate(self._rows):
            item = row.item
            rect = row.rect(self.width())
            if item.separator:
                y = row.top + row.height / 2
                painter.setPen(QPen(QColor(colors["divider"]), 1))
                painter.drawLine(QPointF(rect.left() + 8, y), QPointF(rect.right() - 8, y))
                continue

            hovered = index == self._hover and not item.disabled
            if hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(colors["hover"]))
                painter.drawRoundedRect(rect, self._row_radius, self._row_radius)

            color = QColor(colors["muted"] if item.disabled else colors["text"])
            x = rect.left() + self._text_padding + row.depth * self._indent
            if item.icon is not None:
                pixmap = render_icon(item.icon, color, self._icon_size, dpr)
                if pixmap is not None:
                    painter.drawPixmap(int(x), int(rect.center().y() - self._icon_size / 2), pixmap)
                x += self._icon_size + self._icon_gap

            reserved = self._arrow_space if row.has_children else 8
            available = max(0.0, rect.right() - x - reserved)
            text = metrics.elidedText(item.label, Qt.ElideRight, int(available))
            painter.setPen(color)
            painter.drawText(
                QRectF(x, rect.top(), available, rect.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                text,
            )

            if row.has_children:
                center = QPointF(rect.right() - 12, rect.center().y())
                direction = "down" if row.expanded else "right"
                draw_chevron(painter, center, color, size=7, direction=direction, width=1.4)
        painter.end()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        width = max((metrics.horizontalAdvance(item.label) for item in self._items), default=0)
        return QSize(max(160, width + self._text_padding * 2 + self._icon_size + self._arrow_space), self.height())

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, position) -> int:
        for index, row in enumerate(self._rows):
            if row.top <= position.y() < row.top + row.height:
                return index
        return -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            row = self._row(index)
            clickable = row is not None and not row.item.disabled and not row.item.separator
            self.setCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)
            if clickable and row is not None:
                self.itemHovered.emit(row.item)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            row = self._row(self._index_at(event.position()))
            if row is not None:
                self._activate_row(row)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _activate_row(self, row: _Row) -> None:
        item = row.item
        if item.disabled or item.separator:
            return
        if row.has_children:
            if self._inline:
                self.toggle(row.path)
            else:
                self.submenuRequested.emit(item)
            return
        self.itemClicked.emit(item)
        if callable(item.command):
            item.command()


class CMenuListPopup(CMenuList):
    """以 ``Qt.Popup`` 展示的自绘菜单弹层。

    点外部自动关闭；带子项的条目会在右侧打开下一级弹层。
    """

    closed = Signal()

    def __init__(self, items=None, width: int = 220, parent=None):
        super().__init__(items=items, width=width, inline=False, parent=parent)
        self.setObjectName("CMenuListPopup_Popup")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._child_popup: CMenuListPopup | None = None

    def show_at_global(self, position: QPoint) -> None:
        """在全局坐标处展开；贴近屏幕边缘时向内夹紧，避免越出屏幕。"""
        screen = QGuiApplication.screenAt(position) or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = self.width() or self.sizeHint().width()
            height = self.height()
            x = max(area.left(), min(position.x(), area.right() + 1 - width))
            y = max(area.top(), min(position.y(), area.bottom() + 1 - height))
            position = QPoint(x, y)
        self.move(position)
        self.show()
        self.raise_()

    def _open_submenu(self, row: _Row) -> None:
        self._close_submenu()
        popup = CMenuListPopup(row.item.items, width=self.width(), parent=self)
        popup.itemClicked.connect(self._forward_item)
        popup.closed.connect(self._on_child_closed)
        self._child_popup = popup
        origin = self.mapToGlobal(QPoint(self.width() + 4, int(row.top)))
        popup.show_at_global(origin)

    def _forward_item(self, item: MenuItem) -> None:
        self.itemClicked.emit(item)
        self.hide()

    def _on_child_closed(self) -> None:
        self._child_popup = None

    def _close_submenu(self) -> None:
        popup = self._child_popup
        self._child_popup = None
        if popup is not None:
            popup.hide()
            popup.deleteLater()

    def _activate_row(self, row: _Row) -> None:
        if row.has_children:
            if not row.item.disabled:
                self._open_submenu(row)
            return
        super()._activate_row(row)
        if not row.item.disabled and not row.item.separator:
            self.hide()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._close_submenu()
        super().hideEvent(event)
        self.closed.emit()


__all__ = [
    "CMenuList",
    "CMenuListPopup",
    "MenuItem",
    "LIST_PADDING",
    "ROW_HEIGHT",
    "SEPARATOR_HEIGHT",
    "menu_colors",
    "menu_font",
]
