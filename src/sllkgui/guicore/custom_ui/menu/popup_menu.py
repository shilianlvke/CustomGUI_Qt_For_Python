"""自绘弹出菜单：单窗口多面板，不继承 ``QMenu``。

为什么不用 ``QMenu``（三处绕不过去的限制）：

1. 一旦套用样式表，Qt 就不再绘制子菜单箭头——插件子菜单失去「可点开」的
   视觉暗示，只能靠额外贴图补，且贴图要按主题准备四套；
2. 菜单项只支持一种高度、一种字体、一段文本，做不了分组标题、右侧元信息、
   只读状态行（托盘协议里的 ``status`` 槽需要灰显且不可点）；
3. 子菜单固定向右展开，贴到屏幕右缘时会被整体推回、压在父面板上，
   层级关系被打乱；``QMenu`` 也没有「整条链路一起关」的确定性行为。

本组件用一个 ``Qt.Popup`` 窗口承载全部面板：

- **面板**（panel）就是一级菜单，深度 0 起；子菜单是同一窗口里的另一块面板，
  因此 hover 链、外部点击、Esc 只有一个事件源，不会出现「子菜单关了、父菜单
  还在」的多窗口竞态；
- 面板矩形按**屏幕坐标**排布，贴近右缘自动向左翻转，纵向超限则夹紧 + 滚动；
- 全部视觉由 ``QPainter`` 绘制：圆角、描边、悬停底色、分隔线、箭头都来自
  主题令牌（``menu_colors()``），切换主题重绘即生效。

公开接口见 :class:`CPopupMenu`，样式覆盖见 :class:`MenuStyle`。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import QWidget

from ..icon_utils import render_icon
from ..paint_utils import draw_chevron
from .menu_item import MenuItem, normalize_items
from .menu_list import menu_colors, menu_font

#: 面板内边距（上下各一份）
PANEL_PADDING = 5
#: 普通行高
ROW_HEIGHT = 34
#: 分隔线占用高度
SEPARATOR_HEIGHT = 9
#: 行内圆角
ROW_RADIUS = 6
#: 行左右内缩，让悬停底色不贴到面板描边
ROW_INSET = 4
#: 文字到行左边缘的距离
TEXT_PADDING = 12
#: 子菜单箭头预留宽度
ARROW_SPACE = 22
#: 子菜单与父面板的间距（负值表示轻微压盖，视觉上连成一体）
PANEL_GAP = -1
#: 阴影留白：窗口比面板外扩这么多像素
SHADOW = 14
#: hover 打开子菜单的延迟（毫秒）
SUBMENU_DELAY = 150
#: 滚轮一格滚动的行数
WHEEL_ROWS = 3
#: 勾号尺寸与线宽（占图标列，与原生菜单一致）
CHECK_SIZE = 10
CHECK_WIDTH = 1.6
#: 背景模糊：先缩到 1/16 再放大到 1/4，等价于一次低成本高斯近似
BACKDROP_DOWNSCALE = 16
BACKDROP_UPSCALE = 4


@dataclass
class MenuStyle:
    """菜单样式覆盖项：``None`` 表示沿用当前主题令牌。

    只覆盖想改的字段，其余继续跟随主题；几何与字号也在这里调，方便不同宿主
    （托盘、右键菜单）用不同密度。
    """

    background: str | None = None
    border: str | None = None
    divider: str | None = None
    text: str | None = None
    muted: str | None = None
    hover: str | None = None
    accent: str | None = None
    radius: int | None = None
    row_radius: int = ROW_RADIUS
    row_inset: int = ROW_INSET
    row_height: int = ROW_HEIGHT
    separator_height: int = SEPARATOR_HEIGHT
    padding: int = PANEL_PADDING
    text_padding: int = TEXT_PADDING
    arrow_space: int = ARROW_SPACE
    icon_size: int = 16
    icon_gap: int = 8
    min_width: int = 180
    max_width: int = 420
    font_size: int = 14
    shadow: int = SHADOW
    #: 模糊底透出比例：0 完全按主题底色，1 全透明；仅在截到模糊底时生效
    backdrop_tint: float = 0.25


@dataclass
class _Row:
    """面板里的一行（分隔线也算一行，只是没有文本）。"""

    item: MenuItem
    top: int = 0
    height: int = ROW_HEIGHT

    @property
    def selectable(self) -> bool:
        return not self.item.separator and not self.item.disabled


class _Panel:
    """一级菜单：一组行 + 自己的滚动位置与展开状态。"""

    def __init__(self, items: Sequence[MenuItem], depth: int) -> None:
        self.items = list(items)
        self.depth = depth
        self.rows: list[_Row] = []
        self.width = 0
        self.content_height = 0
        self.rect = QRect()
        self.scroll = 0
        self.hover = -1
        self.icon_column = 0
        self.open_index: int | None = None
        self.parent: _Panel | None = None
        self.child: _Panel | None = None

    @property
    def max_scroll(self) -> int:
        return max(0, self.content_height - self.rect.height())

    @property
    def scrollable(self) -> bool:
        return self.max_scroll > 0

    def clamp_scroll(self) -> None:
        self.scroll = max(0, min(self.scroll, self.max_scroll))


class CPopupMenu(QWidget):
    """自绘弹出菜单（不继承 ``QMenu``）。

    信号：
        ``triggered(MenuItem)``：选中了一条可执行项（分隔线 / 禁用项不触发）。
        ``aboutToShow()`` / ``aboutToHide()``：显示前与关闭后。
        ``closed()``：完全关闭（含点击外部、Esc、选中后自动关闭）。

    交互约定：
        - 勾选：``MenuItem.checked`` 非 ``None`` 即为可勾选项，勾号占图标列；
          点击 / ``Enter`` / ``Space`` 切换并发 ``toggled(item, checked)``；
        - 鼠标：悬停高亮；悬停带子菜单的项 150ms 后自动展开，点击父项立即展开；
        - 键盘：``↑↓`` 移动（跳过禁用项与分隔线、首尾循环）、``→`` 展开、
          ``←`` 收起、``Enter`` / ``Space`` 执行、``Home`` / ``End`` 跳首尾、
          ``Esc`` 逐级关闭、``Tab`` 直接关闭；
        - 关闭：点击窗口外部（``Qt.Popup`` 语义）、窗口失活、执行完动作。
    """

    triggered = Signal(object)
    toggled = Signal(object, bool)
    hovered = Signal(object)
    aboutToShow = Signal()
    aboutToHide = Signal()
    closed = Signal()

    def __init__(
        self,
        items: Iterable[MenuItem] | None = None,
        style: MenuStyle | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CPopupMenu_Widget")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("菜单")

        self._style = style or MenuStyle()
        self._root = _Panel(normalize_items(items), 0)
        self._anchor = QPoint()
        self._area = QRect()
        self._origin = QPoint()
        self._above = True
        self._align = "right"
        self._hover_panel: _Panel | None = None
        self._hover_index = -1
        self._closing = False
        self._was_active = False
        self._last_hover: MenuItem | None = None
        # 亚克力：整屏截图 + 模糊，按面板裁剪后垫在底色下面
        self._backdrop: QPixmap | None = None
        self._backdrop_rect = QRect()

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._open_hovered)

        self._measure_all()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_items(self, items: Iterable[MenuItem] | None) -> None:
        """替换顶层菜单项。

        菜单正在显示时先关闭：条目变化后旧的面板几何与 hover 链都已失效，
        静默重排会让用户点到他没看见的项。原生菜单重建时同样会关闭。
        """
        if self.isVisible():
            self.dismiss()
        self._root = _Panel(normalize_items(items), 0)
        self._measure_all()
        self.update()

    def items(self) -> list[MenuItem]:
        return list(self._root.items)

    def set_style(self, style: MenuStyle | None) -> None:
        """替换样式覆盖并重新测量（字号/行高会影响面板尺寸）。"""
        self._style = style or MenuStyle()
        self._measure_all()
        if self.isVisible():
            self._relayout()
        self.update()

    def style(self) -> MenuStyle:
        return self._style

    def colors(self) -> dict[str, str]:
        """当前生效的配色（主题令牌 + ``MenuStyle`` 覆盖）。

        不能用 ``palette()`` 这个名字：``QWidget.palette()`` 返回 ``QPalette``，
        覆盖它会破坏 Qt 自身的绘制路径。
        """
        return self._palette()

    # ------------------------------------------------------------------
    # 显示 / 关闭
    # ------------------------------------------------------------------
    def popup(self, anchor: QPoint, *, above: bool = True, align: str = "right") -> None:
        """在全局坐标 ``anchor`` 处展开。

        Args:
            anchor: 锚点（托盘图标处通常传 ``QCursor.pos()``）。
            above: ``True`` 向上生长（贴底边的托盘），``False`` 向下生长。
            align: ``right`` 右对齐锚点、``left`` 左对齐、``center`` 居中。
        """
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        self._area = screen.availableGeometry() if screen is not None else QRect(0, 0, 1280, 800)
        self._anchor = anchor
        self._above = above
        self._align = align
        self._measure_all()
        self._root.scroll = 0
        self._close_all_submenus()
        self._layout(anchor, above=above, align=align)
        self._apply_geometry()
        self._capture_backdrop()
        self._root.hover = self._first_selectable(self._root)
        self.aboutToShow.emit()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.PopupFocusReason)
        self.update()

    def dismiss(self) -> None:
        """关闭整条菜单链路。"""
        self._close_all_submenus()
        self.hide()

    def is_open(self) -> bool:
        return self.isVisible()

    # ------------------------------------------------------------------
    # 诊断 / 测试访问器
    # ------------------------------------------------------------------
    def panel_count(self) -> int:
        """当前展开的面板数（1 表示只有根面板）。"""
        return len(self._chain())

    def visible_labels(self) -> list[list[str]]:
        """每个面板的可见文本（分隔线记为 ``"---"``）。"""
        return [["---" if row.item.separator else row.item.label for row in panel.rows] for panel in self._chain()]

    def panel_rects(self) -> list[QRect]:
        """每个面板的全局矩形（由浅到深）。"""
        return [QRect(panel.rect) for panel in self._chain()]

    def active_label(self) -> str:
        panel = self._active_panel()
        row = self._row(panel, panel.hover)
        return "" if row is None else row.item.label

    def open_depth(self) -> int:
        return len(self._chain()) - 1

    def scroll_offset(self, depth: int = 0) -> int:
        panel = self._panel_at_depth(depth)
        return panel.scroll if panel is not None else 0

    def icon_column(self, depth: int = 0) -> int:
        """该面板为图标/勾号预留的列宽（0 表示整列不占位）。"""
        panel = self._panel_at_depth(depth)
        return panel.icon_column if panel is not None else 0

    def content_height(self, depth: int = 0) -> int:
        panel = self._panel_at_depth(depth)
        return panel.content_height if panel is not None else 0

    def visible_height(self, depth: int = 0) -> int:
        panel = self._panel_at_depth(depth)
        return panel.rect.height() if panel is not None else 0

    # ------------------------------------------------------------------
    # 键盘语义（也供宿主直接调用）
    # ------------------------------------------------------------------
    def move_active(self, delta: int) -> None:
        """在当前面板内移动高亮，跳过禁用项与分隔线，首尾循环。"""
        panel = self._active_panel()
        count = len(panel.rows)
        if count == 0:
            return
        if panel.hover < 0:
            start = -1 if delta > 0 else 0
        else:
            start = panel.hover
        for step in range(1, count + 1):
            index = (start + delta * step) % count
            if panel.rows[index].selectable:
                self._set_panel_hover(panel, index)
                self._scroll_into_view(panel, index)
                return

    def set_active_index(self, index: int) -> bool:
        """高亮当前面板的第 ``index`` 行（含禁用项，便于宿主做自定义命中）。"""
        panel = self._active_panel()
        if not 0 <= index < len(panel.rows):
            return False
        self._set_panel_hover(panel, index)
        self._scroll_into_view(panel, index)
        return True

    def open_active_submenu(self) -> bool:
        panel = self._active_panel()
        row = self._row(panel, panel.hover)
        if row is None or not row.item.items or row.item.disabled:
            return False
        self._open_submenu(panel, panel.hover, focus_first=True)
        return True

    def close_submenu(self) -> bool:
        panel = self._active_panel()
        if panel is self._root:
            return False
        self._close_child(panel.parent)
        return True

    def activate_active(self) -> bool:
        panel = self._active_panel()
        return self._activate_row(panel, panel.hover, focus_first=True)

    def _activate_row(self, panel: _Panel | None, index: int, *, focus_first: bool = False) -> bool:
        """执行一行：父项展开子菜单，普通项发 ``triggered``，可勾选项先翻转。"""
        row = self._row(panel, index)
        if row is None or not row.selectable:
            return False
        if row.item.items:
            self._open_submenu(panel, index, focus_first=focus_first)
            return True
        if row.item.checked is not None:
            row.item.checked = not row.item.checked
            self.toggled.emit(row.item, row.item.checked)
            self.update()
        self._emit_triggered(row.item)
        return True

    # ------------------------------------------------------------------
    # 测量与布局
    # ------------------------------------------------------------------
    def _font(self) -> QFont:
        return menu_font(self._style.font_size)

    def _palette(self) -> dict[str, str]:
        colors = menu_colors()
        for key in ("background", "border", "divider", "text", "muted", "hover", "accent"):
            override = getattr(self._style, key)
            if override:
                colors[key] = override
        return colors

    def _measure_panel(self, panel: _Panel) -> None:
        style = self._style
        metrics = QFontMetrics(self._font())
        # 图标列：只要本面板有一条带图标或可勾选的行，整列统一留白，
        # 保证所有文案左对齐（否则有无图标的行会各差 24px）
        panel.icon_column = (
            style.icon_size + style.icon_gap
            if any(not item.separator and (item.icon is not None or item.checked is not None) for item in panel.items)
            else 0
        )
        width = style.min_width
        top = style.padding
        panel.rows = []
        for item in panel.items:
            height = style.separator_height if item.separator else style.row_height
            panel.rows.append(_Row(item=item, top=top, height=height))
            top += height
            if item.separator:
                continue
            arrow = style.arrow_space if item.items else 0
            text_width = metrics.horizontalAdvance(item.label)
            needed = style.text_padding * 2 + style.row_inset * 2 + panel.icon_column + text_width + arrow
            width = max(width, needed)
        panel.content_height = top + style.padding
        panel.width = min(width, style.max_width)
        panel.clamp_scroll()

    def _measure_all(self) -> None:
        panel: _Panel | None = self._root
        while panel is not None:
            self._measure_panel(panel)
            panel = panel.child

    def _chain(self) -> list[_Panel]:
        chain = [self._root]
        while chain[-1].child is not None:
            chain.append(chain[-1].child)
        return chain

    def _panel_at_depth(self, depth: int) -> _Panel | None:
        chain = self._chain()
        return chain[depth] if 0 <= depth < len(chain) else None

    def _active_panel(self) -> _Panel:
        return self._chain()[-1]

    def _layout(self, anchor: QPoint, *, above: bool, align: str) -> None:
        style = self._style
        margin = style.shadow
        limit = self._area.adjusted(margin, margin, -margin, -margin)

        root = self._root
        height = min(root.content_height, limit.height())
        if align == "left":
            x = anchor.x()
        elif align == "center":
            x = anchor.x() - root.width // 2
        else:
            x = anchor.x() - root.width
        x = max(limit.left(), min(x, limit.right() + 1 - root.width))
        y = anchor.y() - height if above else anchor.y()
        y = max(limit.top(), min(y, limit.bottom() + 1 - height))
        root.rect = QRect(x, y, root.width, height)
        root.clamp_scroll()

        panel = root
        while panel.child is not None:
            child = panel.child
            row = self._row(panel, panel.open_index)
            if row is None:
                break
            row_top = panel.rect.top() + style.padding + row.top - panel.scroll
            child_height = min(child.content_height, limit.height())
            right = panel.rect.right() + 1 + PANEL_GAP
            left = panel.rect.left() - child.width - PANEL_GAP
            if right + child.width <= limit.right() + 1:
                child_x = right
            elif left >= limit.left():
                child_x = left
            else:
                child_x = max(limit.left(), min(right, limit.right() + 1 - child.width))
            child_y = max(limit.top(), min(row_top, limit.bottom() + 1 - child_height))
            child.rect = QRect(child_x, child_y, child.width, child_height)
            child.clamp_scroll()
            panel = child

    def uses_backdrop(self) -> bool:
        """当前配色是否需要模糊背景（底色带透明度即视为启用亚克力）。

        ``menu_colors()`` 里的底色由 ``glass_surface()`` 决定：不支持亚克力或
        关闭质感时返回**不透明**色，此时完全跳过截图与模糊，零额外开销。
        """
        return QColor(self._palette()["background"]).alpha() < 250

    def backdrop(self) -> QPixmap | None:
        """当前模糊背景（测试与调试用；``None`` 表示走不透明底色）。"""
        return self._backdrop

    def _capture_backdrop(self) -> None:
        """抓一张桌面截图并做低成本模糊，作为面板的亚克力底。

        抓整屏而不是菜单区域：子菜单展开时窗口会变大并左移，整屏图可以按
        屏幕坐标随时裁切，不必在每次重排时重新截图（否则会把菜单自身也拍进去）。
        """
        self._backdrop = None
        if not self.uses_backdrop():
            return
        # 先按锚点找屏幕：弹层未显示时 self.screen() 可能还是主屏，多屏会截错
        screen = QGuiApplication.screenAt(self._anchor) or self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        shot = screen.grabWindow(0)
        if shot.isNull():
            return
        shot.setDevicePixelRatio(1.0)
        width = max(1, shot.width())
        height = max(1, shot.height())
        small = shot.scaled(
            max(1, width // BACKDROP_DOWNSCALE),
            max(1, height // BACKDROP_DOWNSCALE),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        soft = small.scaled(
            max(1, width // BACKDROP_UPSCALE),
            max(1, height // BACKDROP_UPSCALE),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        self._backdrop = soft
        self._backdrop_rect = QRect(screen.geometry())

    def _apply_geometry(self) -> None:
        union = QRect()
        for panel in self._chain():
            union = union.united(panel.rect)
        margin = self._style.shadow
        self._origin = QPoint(union.left() - margin, union.top() - margin)
        self.setGeometry(
            self._origin.x(),
            self._origin.y(),
            union.width() + margin * 2,
            union.height() + margin * 2,
        )

    def _relayout(self) -> None:
        """子菜单开合后重排（沿用打开时的锚点与方向）。"""
        self._layout(self._anchor, above=self._above, align=self._align)
        self._apply_geometry()
        self.update()

    # ------------------------------------------------------------------
    # 子菜单
    # ------------------------------------------------------------------
    def _row(self, panel: _Panel | None, index: int | None) -> _Row | None:
        if panel is None or index is None:
            return None
        if 0 <= index < len(panel.rows):
            return panel.rows[index]
        return None

    def _first_selectable(self, panel: _Panel, start: int = 0) -> int:
        for index in range(start, len(panel.rows)):
            if panel.rows[index].selectable:
                return index
        return -1

    def _set_panel_hover(self, panel: _Panel, index: int) -> None:
        panel.hover = index
        self._hover_panel = panel
        self._hover_index = index
        self._emit_hover(self._row(panel, index))
        self.update()

    def _emit_hover(self, row: _Row | None) -> None:
        item = None if row is None or row.item.separator else row.item
        if item is self._last_hover:
            return
        self._last_hover = item
        if item is not None:
            self.hovered.emit(item)

    def _open_submenu(self, panel: _Panel, index: int, *, focus_first: bool = False) -> None:
        row = self._row(panel, index)
        if row is None or not row.item.items or row.item.disabled:
            return
        if panel.open_index == index and panel.child is not None:
            return
        self._close_child(panel)
        child = _Panel(row.item.items, panel.depth + 1)
        child.parent = panel
        panel.child = child
        panel.open_index = index
        panel.hover = index
        self._measure_panel(child)
        child.hover = self._first_selectable(child) if focus_first else -1
        self._relayout()
        if child.hover >= 0:
            self._set_panel_hover(panel, index)

    def _close_child(self, panel: _Panel | None) -> None:
        if panel is None or panel.child is None:
            return
        panel.child = None
        panel.open_index = None
        self._hover_timer.stop()
        self._relayout()

    def _close_all_submenus(self) -> None:
        self._root.child = None
        self._root.open_index = None
        self._hover_panel = None
        self._hover_index = -1
        self._hover_timer.stop()
        self._last_hover = None
        self.update()

    def _open_hovered(self) -> None:
        panel = self._hover_panel
        row = self._row(panel, self._hover_index)
        if panel is None or row is None or not row.item.items or row.item.disabled:
            return
        self._open_submenu(panel, self._hover_index)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self._palette()
        radius = self._style.radius if self._style.radius is not None else 10
        self._paint_shadow(painter, radius)
        metrics = QFontMetrics(self._font())
        for panel in self._chain():
            self._paint_panel(painter, panel, palette, metrics, radius)
        painter.end()

    def _panel_local_rect(self, panel: _Panel) -> QRectF:
        return QRectF(panel.rect.translated(-self._origin))

    def _paint_shadow(self, painter: QPainter, radius: int) -> None:
        style = self._style
        if style.shadow <= 0:
            return
        # 面板可能是半透明（亚克力），阴影只能落在面板之外，
        # 否则会透过底色把整块面板压暗
        region = QRegion(self.rect())
        for panel in self._chain():
            shape = QPainterPath()
            shape.addRoundedRect(self._panel_local_rect(panel), radius, radius)
            region = region.subtracted(QRegion(shape.toFillPolygon().toPolygon()))
        if region.isEmpty():
            return
        painter.save()
        painter.setClipRegion(region)
        painter.setBrush(Qt.NoBrush)
        steps = style.shadow
        for step in range(steps, 0, -1):
            ratio = step / steps
            alpha = int(26 * (1 - ratio) ** 1.6) + 3
            painter.setPen(QPen(QColor(0, 0, 0, alpha), 2))
            for panel in self._chain():
                rect = self._panel_local_rect(panel).adjusted(-step, -step + 5, step, step + 5)
                painter.drawRoundedRect(rect, radius + step, radius + step)
        painter.restore()

    def _paint_panel(
        self,
        painter: QPainter,
        panel: _Panel,
        palette: dict[str, str],
        metrics: QFontMetrics,
        radius: int,
    ) -> None:
        style = self._style
        rect = self._panel_local_rect(panel)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        if self._backdrop is not None:
            # 亚克力：把整屏模糊图按屏幕坐标贴进来，再叠半透明底色
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(
                QRectF(self._backdrop_rect).translated(-self._origin),
                self._backdrop,
                QRectF(self._backdrop.rect()),
            )
            painter.restore()
        background = QColor(palette["background"])
        if self._backdrop is None:
            # 没有模糊层时必须不透明，否则半透明底色会把下方阴影透上来
            background.setAlpha(255)
        else:
            # 有真实模糊底时再让出一部分透明度，亚克力才看得出来；
            # 下限 90 保证亮色桌面下文字仍然可读
            tint = max(0.0, min(1.0, self._style.backdrop_tint))
            background.setAlpha(max(90, round(background.alpha() * (1.0 - tint))))
        painter.fillPath(path, background)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        painter.setFont(self._font())
        for index, row in enumerate(panel.rows):
            top = rect.top() + style.padding + row.top - panel.scroll
            if top + row.height < rect.top() or top > rect.bottom():
                continue
            row_rect = QRectF(
                rect.left() + style.row_inset,
                top + 1,
                rect.width() - style.row_inset * 2,
                row.height - 2,
            )
            if row.item.separator:
                y = top + row.height / 2
                painter.setPen(QPen(QColor(palette["divider"]), 1))
                painter.drawLine(QPointF(rect.left() + 10, y), QPointF(rect.right() - 10, y))
                continue

            if index == panel.hover and row.selectable:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(palette["hover"]))
                painter.drawRoundedRect(row_rect, style.row_radius, style.row_radius)

            color = QColor(palette["muted"] if row.item.disabled else palette["text"])
            x = row_rect.left() + style.text_padding
            if panel.icon_column:
                column = QRectF(x, row_rect.top(), style.icon_size, row_rect.height())
                if row.item.checked is not None:
                    # 勾号独占图标列（与原生菜单一致，可勾选项不再画图标）
                    if row.item.checked:
                        check_color = QColor(palette["muted"] if row.item.disabled else palette["accent"])
                        self._draw_check(painter, column, check_color)
                elif row.item.icon is not None:
                    pixmap = render_icon(row.item.icon, color, style.icon_size, self.devicePixelRatioF())
                    if pixmap is not None:
                        painter.drawPixmap(int(x), int(row_rect.center().y() - style.icon_size / 2), pixmap)
                x += panel.icon_column

            reserved = style.arrow_space if row.item.items else 8
            available = max(0.0, row_rect.right() - x - reserved)
            text = metrics.elidedText(row.item.label, Qt.ElideRight, int(available))
            painter.setPen(color)
            painter.drawText(
                QRectF(x, row_rect.top(), available, row_rect.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                text,
            )
            if row.item.items:
                center = QPointF(row_rect.right() - style.arrow_space / 2, row_rect.center().y())
                draw_chevron(painter, center, color, size=7, direction="right", width=1.4)

        self._paint_scroll_hints(painter, panel, rect, palette)
        painter.restore()

    @staticmethod
    def _draw_check(painter: QPainter, column: QRectF, color: QColor) -> None:
        """在图标列内画一个 10px 勾号（圆头圆角，1.6px 线宽）。"""
        cx = column.center().x()
        cy = column.center().y()
        half = CHECK_SIZE / 2
        path = QPainterPath()
        path.moveTo(cx - half, cy + half * 0.04)
        path.lineTo(cx - half * 0.16, cy + half * 0.72)
        path.lineTo(cx + half, cy - half * 0.62)
        pen = QPen(color, CHECK_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _paint_scroll_hints(self, painter: QPainter, panel: _Panel, rect: QRectF, palette: dict[str, str]) -> None:
        if not panel.scrollable:
            return
        color = QColor(palette["muted"])
        color.setAlpha(170)
        if panel.scroll > 0:
            draw_chevron(painter, QPointF(rect.center().x(), rect.top() + 8), color, size=6, direction="up", width=1.4)
        if panel.scroll < panel.max_scroll:
            draw_chevron(
                painter, QPointF(rect.center().x(), rect.bottom() - 8), color, size=6, direction="down", width=1.4
            )

    # ------------------------------------------------------------------
    # 鼠标
    # ------------------------------------------------------------------
    def _hit(self, global_pos: QPoint) -> tuple[_Panel | None, int]:
        for panel in reversed(self._chain()):
            if not panel.rect.contains(global_pos):
                continue
            local_y = global_pos.y() - panel.rect.top() - self._style.padding + panel.scroll
            for index, row in enumerate(panel.rows):
                if row.top <= local_y < row.top + row.height:
                    return panel, index
            return panel, -1
        return None, -1

    def _apply_hover(self, panel: _Panel, index: int) -> None:
        if self._hover_panel is panel and self._hover_index == index:
            return
        self._hover_panel = panel
        self._hover_index = index
        for candidate in self._chain():
            candidate.hover = index if candidate is panel else -1
        self._emit_hover(self._row(panel, index))
        self.update()

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        global_pos = event.globalPosition().toPoint()
        panel, index = self._hit(global_pos)
        if panel is None:
            self._hover_timer.stop()
            super().mouseMoveEvent(event)
            return
        # 回到祖先面板：先关掉它下面已展开的子菜单，避免“看着父级、点着子级”
        if panel is not self._active_panel():
            self._close_child(panel)
        self._apply_hover(panel, index)
        row = self._row(panel, index)
        if row is None:
            self._hover_timer.stop()
        elif row.item.items and not row.item.disabled:
            if panel.open_index != index:
                self._hover_timer.start(SUBMENU_DELAY)
        else:
            self._hover_timer.stop()
            if panel.child is not None:
                self._close_child(panel)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover_timer.stop()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        panel, index = self._hit(event.globalPosition().toPoint())
        row = self._row(panel, index)
        if row is None or not row.selectable:
            super().mouseReleaseEvent(event)
            return
        self._activate_row(panel, index)
        event.accept()

    def wheelEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        panel, _index = self._hit(event.globalPosition().toPoint())
        if panel is None or not panel.scrollable:
            super().wheelEvent(event)
            return
        direction = -1 if event.angleDelta().y() > 0 else 1
        step = self._style.row_height * WHEEL_ROWS
        panel.scroll = max(0, min(panel.scroll + direction * step, panel.max_scroll))
        if panel.child is not None:
            self._close_child(panel)
        else:
            self.update()
        event.accept()

    # ------------------------------------------------------------------
    # 键盘
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        key = event.key()
        if key == Qt.Key_Escape:
            if not self.close_submenu():
                self.dismiss()
            event.accept()
            return
        if key in (Qt.Key_Tab, Qt.Key_Backtab):
            self.dismiss()
            event.accept()
            return
        if key in (Qt.Key_Down, Qt.Key_Up):
            self.move_active(1 if key == Qt.Key_Down else -1)
            event.accept()
            return
        if key == Qt.Key_Right:
            self.open_active_submenu()
            event.accept()
            return
        if key == Qt.Key_Left:
            self.close_submenu()
            event.accept()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activate_active()
            event.accept()
            return
        if key == Qt.Key_Home:
            self._select_edge(first=True)
            event.accept()
            return
        if key == Qt.Key_End:
            self._select_edge(first=False)
            event.accept()
            return
        super().keyPressEvent(event)

    def _select_edge(self, *, first: bool) -> None:
        panel = self._active_panel()
        order = range(len(panel.rows)) if first else range(len(panel.rows) - 1, -1, -1)
        for index in order:
            if panel.rows[index].selectable:
                self._set_panel_hover(panel, index)
                self._scroll_into_view(panel, index)
                return

    def _scroll_into_view(self, panel: _Panel, index: int) -> None:
        row = self._row(panel, index)
        if row is None or not panel.scrollable:
            return
        top = row.top
        bottom = top + row.height
        view_top = panel.scroll
        view_bottom = panel.scroll + panel.rect.height() - self._style.padding * 2
        if top < view_top:
            panel.scroll = max(0, top - self._style.padding)
        elif bottom > view_bottom:
            panel.scroll = min(panel.max_scroll, bottom - panel.rect.height() + self._style.padding * 2)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def _emit_triggered(self, item: MenuItem) -> None:
        self.triggered.emit(item)
        if callable(item.command):
            item.command()
        self.dismiss()

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        self._was_active = False
        self.setFocus(Qt.PopupFocusReason)

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover_timer.stop()
        self._root.child = None
        self._root.open_index = None
        self._root.hover = -1
        self._root.scroll = 0
        self._hover_panel = None
        self._hover_index = -1
        self._backdrop = None
        super().hideEvent(event)
        if not self._closing:
            self._closing = True
            try:
                self.aboutToHide.emit()
                self.closed.emit()
            finally:
                self._closing = False

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.type() == QEvent.Type.ActivationChange:
            # 只在「曾经激活过、随后失活」时关闭：show() 过程中会先收到一次
            # 未激活的 ActivationChange，直接关会让菜单一闪而过。
            if self.isActiveWindow():
                self._was_active = True
            elif self._was_active and self.isVisible():
                self.dismiss()
        super().changeEvent(event)


__all__ = [
    "ARROW_SPACE",
    "PANEL_PADDING",
    "ROW_HEIGHT",
    "SEPARATOR_HEIGHT",
    "CPopupMenu",
    "MenuStyle",
]
