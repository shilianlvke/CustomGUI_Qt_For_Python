"""分体按钮：主按钮 + 下拉箭头（Windows Fluent Design SplitButton）。

弹出内容拆成两层：

* :class:`_SplitMenu` 只画「菜单行」（36px 行高、4px 圆角悬停、着色图标、分隔线）；
* 浮层容器复用下拉字段那套 :class:`~customgui.guicore.custom_ui.line_edit.overlay.CPopover`
  （圆角 + 描边 + Aura 阴影 + 内容内衬 + 出屏翻边）。

以前菜单自己是一个 ``Qt.Popup`` 窗口、自己画阴影，和 ``CSelect`` 等下拉字段是两套实现，
圆角/阴影容易各走各的；统一到 ``CPopover`` 后只有一个地方定义「浮层长什么样」。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from customgui.appcore import AppSettings, get_design_tokens

from ..icon_utils import render_icon
from ..line_edit.overlay import CPopover
from .button import _SIZES, CButton

#: ``navigation.list.gap`` = 2px（行与行、行与分隔线之间）
_MENU_GAP = 2
#: ``navigation.item.padding`` = 0.5rem 0.75rem，``border.radius.sm`` = 4px
_MENU_ITEM_PADDING_X = 12
_MENU_ITEM_PADDING_Y = 8
_MENU_ITEM_RADIUS = 4
#: ``navigation.item.gap`` = 0.5rem
_MENU_ICON_GAP = 8
_MENU_ICON = 16
#: ``menu.min-width`` = 12.5rem
_MENU_MIN_WIDTH = 200


def _split_button_config() -> tuple[int, int, int, int, int, int, int]:
    """(行间距, 横向内边距, 纵向内边距, 行圆角, 图标间距, 图标尺寸, 最小宽度)。"""
    try:
        cfg = AppSettings.split_button
        return (
            int(cfg.menu_gap),
            int(cfg.item_padding_x),
            int(cfg.item_padding_y),
            int(cfg.item_radius),
            int(cfg.icon_gap),
            int(cfg.icon_size),
            int(cfg.min_width),
        )
    except Exception:  # 配置上下文未就绪时用兜底值
        return (
            _MENU_GAP,
            _MENU_ITEM_PADDING_X,
            _MENU_ITEM_PADDING_Y,
            _MENU_ITEM_RADIUS,
            _MENU_ICON_GAP,
            _MENU_ICON,
            _MENU_MIN_WIDTH,
        )


class _SplitMenu(QWidget):
    """PrimeVue ``Menu`` 的**内容**部分（单选、带图标、可含分隔线）。

    它不再是独立窗口：圆角、描边、阴影、内衬统一由 :class:`CPopover` 负责——
    和 ``CSelect`` / ``CDatePicker`` 等下拉字段共用同一套浮层外观，避免两套实现
    在圆角/阴影上各走各的（浮层右下角出现透明直角就是这么来的）。
    """

    actionTriggered = Signal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setObjectName("CSplitMenu_Content")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        (
            self._menu_gap,
            self._item_padding_x,
            self._item_padding_y,
            self._item_radius,
            self._icon_gap,
            self._icon_size,
            self._min_width,
        ) = _split_button_config()

        self._items = list(items)
        self._hover = -1
        self._rows: list[tuple[str, str | None, str | None, QRect]] = []
        self._font = QFont(AppSettings.family)
        self._font.setPixelSize(max(12, AppSettings.text_size + 2))
        self._font.setWeight(QFont.Weight.Normal)
        self._item_height = self._item_padding_y * 2 + max(self._icon_size, QFontMetrics(self._font).height())
        self.setFont(self._font)
        width = self._natural_width()
        self._build_rows(width)
        self.setMinimumWidth(width)
        self.setFixedHeight(self._rows_height())

    # ------------------------------------------------------------------
    # 尺寸与排版
    # ------------------------------------------------------------------
    def _natural_width(self) -> int:
        metrics = QFontMetrics(self._font)
        widest = 0
        for item in self._items:
            if item is None:
                continue
            label, icon = item
            icon_width = self._icon_size + self._icon_gap if icon else 0
            widest = max(widest, icon_width + metrics.horizontalAdvance(label))
        return widest + self._item_padding_x * 2

    def _build_rows(self, width: int) -> None:
        y = 0
        rows: list[tuple[str, str | None, str | None, QRect]] = []
        for item in self._items:
            if item is None:
                rows.append(("separator", None, None, QRect(0, y, width, 1)))
                y += 1 + self._menu_gap
                continue
            label, icon = item
            rows.append(("item", label, icon, QRect(0, y, width, self._item_height)))
            y += self._item_height + self._menu_gap
        self._rows = rows
        self._last_height = max(0, y - self._menu_gap)

    def _rows_height(self) -> int:
        return getattr(self, "_last_height", 0)

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        # 宽度由浮层内容区决定，行矩形跟着重排
        if self.width() > 0:
            self._build_rows(self.width())
        super().resizeEvent(event)

    def entries(self) -> list[str | None]:
        """菜单项标签（``None`` = 分隔线），顺序与构造时的 ``items`` 一致。"""
        return [label if kind == "item" else None for kind, label, _icon, _rect in self._rows]

    # ------------------------------------------------------------------
    # 外观（只画内容行，浮层外观由 CPopover 负责）
    # ------------------------------------------------------------------
    def _menu_colors(self) -> tuple[QColor, QColor, QColor, QColor]:
        """(正文色, 悬停色, 图标色, 分隔线色)。"""
        tokens = get_design_tokens().colors
        text = QColor(tokens.text_primary)
        active = QColor(tokens.text_active)
        icon = QColor(tokens.text_muted)
        separator = QColor(text)
        separator.setAlpha(60)
        return text, active, icon, separator

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        text_color, active_color, icon_color, separator = self._menu_colors()
        painter.setFont(self._font)

        for index, (kind, label, icon, rect) in enumerate(self._rows):
            if kind == "separator":
                painter.setPen(QPen(separator, 1))
                painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
                continue

            hovered = index == self._hover
            if hovered:
                highlight = QColor(active_color)
                highlight.setAlpha(24)
                painter.setPen(Qt.NoPen)
                painter.setBrush(highlight)
                painter.drawRoundedRect(QRectF(rect), self._item_radius, self._item_radius)

            color = active_color if hovered else text_color
            x = rect.left() + self._item_padding_x
            if icon:
                tint = text_color if hovered else icon_color
                pixmap = render_icon(icon, tint, self._icon_size, self.devicePixelRatioF())
                if pixmap is not None:
                    painter.drawPixmap(int(x), int(rect.center().y() - pixmap.height() / 2), pixmap)
                x += self._icon_size + self._icon_gap
            painter.setPen(color)
            painter.drawText(
                QRect(x, rect.top(), rect.right() - x - self._item_padding_x, rect.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                label or "",
            )
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, pos: QPoint) -> int:
        for index, (kind, _label, _icon, rect) in enumerate(self._rows):
            if kind == "item" and rect.contains(pos):
                return index
        return -1

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        hover = self._index_at(event.position().toPoint())
        if hover != self._hover:
            self._hover = hover
            self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            index = self._index_at(event.position().toPoint())
            if index >= 0:
                self._activate(index)
                return
        super().mouseReleaseEvent(event)

    def _activate(self, index: int) -> None:
        _kind, label, _icon, _rect = self._rows[index]
        host = self.window()
        if host is not None:
            host.close()
        if label:
            self.actionTriggered.emit(label)

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802 - 覆写 Qt 命名
        if event.key() == Qt.Key_Escape:
            host = self.window()
            if host is not None:
                host.close()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            items = [i for i, row in enumerate(self._rows) if row[0] == "item"]
            if not items:
                return
            step = 1 if event.key() == Qt.Key_Down else -1
            if self._hover in items:
                self._hover = items[(items.index(self._hover) + step) % len(items)]
            else:
                self._hover = items[0] if step > 0 else items[-1]
            self.update()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self._hover >= 0:
            self._activate(self._hover)
            return
        super().keyPressEvent(event)


class CSplitButton(QWidget):
    """主操作 + 附加菜单的分体按钮。

    主按钮负责默认动作，右侧箭头按钮弹出 ``items`` 指定的菜单项；
    两段共用同一 severity 与尺寸，右侧只有外侧圆角（对齐 Aura 的
    ``.p-splitbutton-button`` / ``.p-splitbutton-dropdown``）。

    ``items`` 的每一项是 ``(label, icon)``；元素为 ``None`` 时插入一条分隔线。
    """

    clicked = Signal()
    actionTriggered = Signal(str)

    def __init__(
        self,
        text: str = "Save",
        items: list[tuple[str, str | None] | None] | None = None,
        severity: str = "primary",
        size: str = "md",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CSplitButton_Widget")
        self._size = size if size in _SIZES else "md"
        self._items: list[tuple[str, str | None] | None] = list(items or [])
        self._severity = severity
        self._menu_min_width = _split_button_config()[-1]
        self._menu: _SplitMenu | None = None
        self._popover: CPopover | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        height = _SIZES[self._size].height
        self._main = CButton(
            text=text,
            severity=severity,
            size=self._size,
            corners=(True, False, False, True),
            parent=self,
        )
        self._arrow = CButton(
            icon="icon_arrow_down",
            severity=severity,
            size=self._size,
            fixed_width=height,
            border_visible=False,
            corners=(False, True, True, False),
            parent=self,
        )

        layout.addWidget(self._main)
        layout.addWidget(self._arrow)
        self.setFixedHeight(height)

        self._main.clicked.connect(self.clicked.emit)
        self._arrow.clicked.connect(self._show_menu)

    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._main.text()

    def setText(self, text: str) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._main.setText(text)
        self.updateGeometry()

    def set_items(self, items: list[tuple[str, str | None] | None]) -> None:
        self._items = list(items)

    def items(self) -> list[tuple[str, str | None] | None]:
        return list(self._items)

    def main_button(self) -> CButton:
        return self._main

    def arrow_button(self) -> CButton:
        return self._arrow

    def menu(self) -> _SplitMenu | None:
        """最近一次弹出的菜单内容（没弹过为 ``None``）。"""
        return self._menu

    def popover(self) -> CPopover | None:
        """最近一次弹出的浮层容器（与下拉字段共用 :class:`CPopover`）。"""
        return self._popover

    def _on_menu_closed(self) -> None:
        popover = self._popover
        self._popover = None
        self._menu = None
        if popover is not None:
            popover.deleteLater()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        main = self._main.sizeHint()
        return QSize(main.width() + self._arrow.sizeHint().width(), main.height())

    def _show_menu(self) -> None:
        if not self._items:
            return
        if self._popover is not None:
            self._popover.close()
            self._popover.deleteLater()

        popover = CPopover(self, width=max(self._menu_min_width, self.width()))
        menu = _SplitMenu(self._items, popover)
        menu.actionTriggered.connect(self.actionTriggered.emit)
        popover.content_layout().addWidget(menu)
        popover.closed.connect(self._on_menu_closed)
        self._popover = popover
        self._menu = menu
        popover.show_at(self._arrow)


__all__ = ["CSplitButton"]
