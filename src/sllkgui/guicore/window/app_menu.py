"""Windows Fluent Design 嵌套侧边菜单。

``CAppMenuItem`` 是一条可点击的菜单行（分组标题或叶子项），``CAppMenu``
负责树形结构、展开状态、单选激活与信号转发。所有颜色在绘制时实时读取
设计令牌，切换主题后 ``update()`` 即可生效。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, ColorPalette, get_design_tokens, get_theme_manager

from ..custom_ui.icon_utils import render_icon
from ..custom_ui.menu.menu_item import as_menu_item
from ..custom_ui.paint_utils import draw_chevron

#: 菜单行高
ROW_HEIGHT = 38
#: 每级子项缩进
INDENT = 16
#: 图标逻辑尺寸与图标 / 文字间距
ICON_SIZE = 16
ICON_GAP = 8
#: 文字到行左边缘的基础距离
TEXT_PADDING = 12
#: 行内圆角
ROW_RADIUS = 6
#: 配置不可用时的箭头旋转时长
FALLBACK_DURATION = 180


def _app_menu_config() -> tuple[int, int, int, int, int, int]:
    """(行高, 缩进, 图标尺寸, 图标间距, 文字留白, 行圆角)。"""
    try:
        cfg = AppSettings.menus
        return (
            int(cfg.app_row_height),
            int(cfg.app_indent),
            int(cfg.app_icon_size),
            int(cfg.app_icon_gap),
            int(cfg.app_text_padding),
            int(cfg.app_row_radius),
        )
    except Exception:  # 配置上下文未就绪时用兜底值
        return ROW_HEIGHT, INDENT, ICON_SIZE, ICON_GAP, TEXT_PADDING, ROW_RADIUS


def _build_item(value, depth: int) -> CAppMenuItem:
    """把字典 / ``MenuItem`` / 已有控件归一为 :class:`CAppMenuItem`。"""
    if isinstance(value, CAppMenuItem):
        value._set_depth(depth)
        return value
    data = as_menu_item(value)
    return CAppMenuItem(
        label=data.label,
        icon=data.icon,
        key=data.key,
        children=list(data.items),
        depth=depth,
    )


class CAppMenuItem(QWidget):
    """一条菜单行：分组标题（含子项）或可点击的叶子项。"""

    activated = Signal(object)
    toggled = Signal(object, bool)

    def __init__(
        self,
        label: str = "",
        icon=None,
        key: str | None = None,
        children=None,
        depth: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        (
            self._row_height,
            self._indent,
            self._icon_size,
            self._icon_gap,
            self._text_padding,
            self._row_radius,
        ) = _app_menu_config()
        self._label = str(label)
        self._icon = icon
        self._key = key
        self._children = [_build_item(child, depth + 1) for child in (children or [])]
        self._depth = max(0, int(depth))
        self._expanded = False
        self._active = False
        self._hover = False
        self._progress = 0.0
        self._animation: QVariantAnimation | None = None

        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(self._row_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_font()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def label(self) -> str:
        return self._label

    def icon(self):
        return self._icon

    def key(self) -> str | None:
        return self._key

    def identity(self) -> str:
        """业务标识：优先用 key，缺省回落到 label。"""
        return self._key if self._key is not None else self._label

    def children(self) -> list[CAppMenuItem]:
        return list(self._children)

    def has_children(self) -> bool:
        return bool(self._children)

    def depth(self) -> int:
        return self._depth

    def is_expanded(self) -> bool:
        return self._expanded

    def is_active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        if self._active != bool(active):
            self._active = bool(active)
            self.update()

    def _set_depth(self, depth: int) -> None:
        self._depth = max(0, int(depth))
        self._apply_font()
        for child in self._children:
            child._set_depth(self._depth + 1)

    def _apply_font(self) -> None:
        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold if self._depth == 0 else QFont.Weight.Normal)
        self.setFont(font)

    # ------------------------------------------------------------------
    # 展开 / 收起
    # ------------------------------------------------------------------
    def set_expanded(self, expanded: bool, emit: bool = True) -> None:
        target = bool(expanded)
        if target == self._expanded:
            return
        self._expanded = target
        self._animate_progress()
        if emit:
            self.toggled.emit(self, target)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _duration(self) -> int:
        try:
            return int(AppSettings.panels.collapse_duration)
        except Exception:
            return FALLBACK_DURATION

    def _animate_progress(self) -> None:
        target = 1.0 if self._expanded else 0.0
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        if not self.isVisible() or self._duration() <= 0:
            self._set_progress(target)
            return
        animation = QVariantAnimation(self)
        animation.setStartValue(self._progress)
        animation.setEndValue(target)
        animation.setDuration(self._duration())
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(self._set_progress)
        animation.start()
        self._animation = animation

    def _set_progress(self, value) -> None:
        self._progress = float(value)
        self.update()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(200, self._row_height)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        row = QRectF(self.rect()).adjusted(2, 1, -2, -1)
        painter.setPen(Qt.NoPen)
        if self._active:
            painter.setBrush(QColor(colors.border_context))
            painter.drawRoundedRect(row, self._row_radius, self._row_radius)
            text_color = QColor(ColorPalette.custom_white)
            muted_color = text_color
        elif self._hover:
            painter.setBrush(QColor(colors.surface_interactive))
            painter.drawRoundedRect(row, self._row_radius, self._row_radius)
            text_color = QColor(colors.text_active)
            muted_color = QColor(colors.text_primary)
        else:
            text_color = QColor(colors.text_primary if self._depth == 0 else colors.text_muted)
            muted_color = QColor(colors.text_muted)

        left = row.left() + self._text_padding + self._depth * self._indent
        if self._icon is not None:
            pixmap = render_icon(self._icon, text_color, self._icon_size, self.devicePixelRatioF())
            if pixmap is not None:
                painter.drawPixmap(
                    int(left),
                    int(row.center().y() - self._icon_size / 2),
                    pixmap,
                )
            left += self._icon_size + self._icon_gap

        reserved = 24 if self.has_children() else 8
        available = max(0.0, row.right() - left - reserved)
        metrics = QFontMetrics(self.font())
        painter.setPen(text_color)
        painter.drawText(
            QRectF(left, row.top(), available, row.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            metrics.elidedText(self._label, Qt.ElideRight, int(available)),
        )

        if self.has_children():
            painter.save()
            painter.translate(QPointF(row.right() - 12, row.center().y()))
            painter.rotate(90 * self._progress)
            draw_chevron(painter, QPointF(0, 0), muted_color, size=7, direction="right", width=1.4)
            painter.restore()
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            if self.has_children():
                self.toggle()
            else:
                self.activated.emit(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CAppMenu(QWidget):
    """嵌套侧边菜单：分组可展开 / 收起，叶子项单选激活。"""

    itemClicked = Signal(object)
    expandedChanged = Signal(str, bool)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self.setObjectName("CAppMenu_Widget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(2)
        self._layout.setAlignment(Qt.AlignTop)
        self._items: list[CAppMenuItem] = []
        self._active: CAppMenuItem | None = None
        self.set_items(items)
        get_theme_manager().subscribe(self.update_style)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_items(self, items) -> None:
        """替换全部菜单项（字典支持 ``label`` / ``icon`` / ``key`` / ``children``）。"""
        self._clear_layout()
        self._items = [_build_item(value, 0) for value in (items or [])]
        for item in self._items:
            for row in self._walk_rows(item):
                self._layout.addWidget(row)
        for item in self._items:
            self._connect(item)
        self._sync_visibility()

    def items(self) -> list[CAppMenuItem]:
        return list(self._items)

    def active_key(self) -> str | None:
        return self._active.identity() if self._active is not None else None

    def active_item(self) -> CAppMenuItem | None:
        return self._active

    def find_item(self, key: str) -> CAppMenuItem | None:
        for item in self._all_items():
            if item.key() == key or item.identity() == key:
                return item
        return None

    # ------------------------------------------------------------------
    # 展开 / 收起
    # ------------------------------------------------------------------
    def expand_all(self) -> None:
        for item in self._all_items():
            if item.has_children():
                item.set_expanded(True)

    def collapse_all(self) -> None:
        for item in self._items:
            self._collapse_recursive(item)

    def _collapse_recursive(self, item: CAppMenuItem) -> None:
        for child in item.children():
            self._collapse_recursive(child)
        item.set_expanded(False)

    def set_active(self, key: str | None) -> bool:
        """按 key / label 单选激活；未找到时清空激活状态。"""
        found = self.find_item(key) if key is not None else None
        for item in self._all_items():
            item.set_active(item is found)
        self._active = found
        return found is not None

    # ------------------------------------------------------------------
    # 内部组装
    # ------------------------------------------------------------------
    def _clear_layout(self) -> None:
        while self._layout.count():
            entry = self._layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self._items = []
        self._active = None

    @staticmethod
    def _walk_rows(item: CAppMenuItem):
        yield item
        for child in item.children():
            yield from CAppMenu._walk_rows(child)

    def _all_items(self):
        for item in self._items:
            yield from self._walk_rows(item)

    def _connect(self, item: CAppMenuItem) -> None:
        item.activated.connect(self._on_activated)
        item.toggled.connect(self._on_toggled)
        for child in item.children():
            self._connect(child)

    def _on_activated(self, item: CAppMenuItem) -> None:
        self.set_active(item.identity())
        self.itemClicked.emit(item)

    def _on_toggled(self, item: CAppMenuItem, expanded: bool) -> None:
        self._sync_visibility()
        self.expandedChanged.emit(item.identity(), expanded)

    def _sync_visibility(self) -> None:
        for item in self._items:
            self._apply_visibility(item, True)

    def _apply_visibility(self, item: CAppMenuItem, visible: bool) -> None:
        item.setVisible(visible)
        child_visible = visible and item.is_expanded()
        for child in item.children():
            self._apply_visibility(child, child_visible)

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def update_style(self) -> None:
        """主题切换后刷新全部行的绘制（颜色在 paintEvent 中实时读取）。"""
        for item in self._all_items():
            item.update()
        self.update()


__all__ = ["CAppMenu", "CAppMenuItem"]
