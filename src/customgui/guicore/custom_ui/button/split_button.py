"""分体按钮：主按钮 + 下拉箭头（对应 PrimeVue 的 SplitButton）。

附带一个 :class:`_SplitMenu`：PrimeVue 的 SplitButton 弹的是 ``<Menu popup>``，
样式由 ``.p-menu`` 决定（圆角卡片 + 4px 内衬 + 36px 圆角菜单项 + 悬停高亮 + 着色图标），
``QMenu`` 的原生渲染做不出这套排版，所以这里按同一规格自绘一个浮层。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QKeyEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from customgui.appcore import AppSettings, get_design_tokens

from ..icon_utils import render_icon
from ..paint_utils import draw_shadow
from .button import _SIZES, CButton

#: 浮层圆角（Aura ``menu.border.radius`` = ``content.border.radius`` = 6px）
_MENU_RADIUS = 6
#: ``navigation.list.padding`` = 0.25rem，``navigation.list.gap`` = 2px
_MENU_PADDING = 4
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
#: 浮层的阴影比按钮更大（``overlay.navigation.shadow``），边距相应放大
_MENU_SHADOW_MARGINS = (6, 2, 6, 10)
#: 浮层与箭头按钮之间的间距
_MENU_OFFSET = 4


class _SplitMenu(QWidget):
    """PrimeVue ``Menu`` 的弹出形态：单选、带图标、可含分隔线。"""

    actionTriggered = Signal(str)

    def __init__(self, items, min_width: int = _MENU_MIN_WIDTH, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setObjectName("CSplitMenu_Popup")

        self._items = list(items)
        self._hover = -1
        self._rows: list[tuple[str, str | None, str | None, QRect]] = []
        self._font = QFont(AppSettings.family)
        self._font.setPixelSize(max(12, AppSettings.text_size + 2))
        self._font.setWeight(QFont.Weight.Normal)
        self._item_height = _MENU_ITEM_PADDING_Y * 2 + max(_MENU_ICON, QFontMetrics(self._font).height())

        self._layout_rows(max(min_width, self._natural_width()))

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
            icon_width = _MENU_ICON + _MENU_ICON_GAP if icon else 0
            widest = max(widest, icon_width + metrics.horizontalAdvance(label))
        return widest + _MENU_ITEM_PADDING_X * 2 + _MENU_PADDING * 2

    def _layout_rows(self, body_width: int) -> None:
        left, top, right, bottom = _MENU_SHADOW_MARGINS
        x = left + _MENU_PADDING
        width = body_width - 2 * _MENU_PADDING
        y = top + _MENU_PADDING
        rows: list[tuple[str, str | None, str | None, QRect]] = []
        for item in self._items:
            if item is None:
                rows.append(("separator", None, None, QRect(x, y, width, 1)))
                y += 1 + _MENU_GAP
                continue
            label, icon = item
            rows.append(("item", label, icon, QRect(x, y, width, self._item_height)))
            y += self._item_height + _MENU_GAP
        self._rows = rows
        content = y - _MENU_GAP + _MENU_PADDING
        self.setFixedSize(body_width + left + right, content + top + bottom)

    def entries(self) -> list[str | None]:
        """菜单项标签（``None`` = 分隔线），顺序与构造时的 ``items`` 一致。"""
        return [label if kind == "item" else None for kind, label, _icon, _rect in self._rows]

    def _body_rect(self) -> QRectF:
        left, top, right, bottom = _MENU_SHADOW_MARGINS
        return QRectF(self.rect()).adjusted(left, top, -right, -bottom)

    def popup(self, global_pos: QPoint) -> None:
        """在 ``global_pos``（分体按钮左下角）弹出浮层，超出屏幕时自动翻边。"""
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        left, top, _right, _bottom = _MENU_SHADOW_MARGINS
        pos = QPoint(global_pos)
        if screen is not None:
            available = screen.availableGeometry()
            if pos.x() + self.width() - left - _MENU_SHADOW_MARGINS[2] > available.right():
                pos.setX(available.right() - self.width() + _MENU_SHADOW_MARGINS[2])
            if pos.y() + self.height() - top - _MENU_SHADOW_MARGINS[3] > available.bottom():
                pos.setY(max(available.top(), pos.y() - self.height() - _MENU_OFFSET))
        self.move(pos - QPoint(left, top))
        self.show()
        self.raise_()
        self.setFocus(Qt.PopupFocusReason)

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def _menu_colors(self) -> tuple[QColor, QColor, QColor, QColor, QColor]:
        """(底色, 描边, 正文色, 悬停色, 图标色)。

        对齐 Aura 的关系：浮层比卡片更「深一档」，描边是正文色的低透明度叠加，
        悬停是正文色 9% 的叠加（``navigation.item.focus.background``），
        图标比正文再暗一档（``navigation.item.icon.color``）。
        """
        colors = get_design_tokens().colors
        background = QColor(colors.surface_sidebar)
        text = QColor(colors.text_primary)
        active = QColor(colors.text_active)
        icon = QColor(colors.text_muted)
        border = QColor(text)
        border.setAlpha(60)
        return background, border, text, active, icon

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        background, border, text_color, active_color, icon_color = self._menu_colors()

        body = self._body_rect()
        path = QPainterPath()
        path.addRoundedRect(body, _MENU_RADIUS, _MENU_RADIUS)

        draw_shadow(painter, path, body, _MENU_RADIUS)
        painter.fillPath(path, background)

        border_path = QPainterPath()
        border_path.addRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), _MENU_RADIUS, _MENU_RADIUS)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(border_path)

        painter.setFont(self._font)
        for index, (kind, label, icon, rect) in enumerate(self._rows):
            if kind == "separator":
                painter.setPen(QPen(border, 1))
                painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
                continue

            hovered = index == self._hover
            if hovered:
                highlight = QColor(active_color)
                highlight.setAlpha(24)
                painter.setPen(Qt.NoPen)
                painter.setBrush(highlight)
                painter.drawRoundedRect(QRectF(rect), _MENU_ITEM_RADIUS, _MENU_ITEM_RADIUS)

            color = active_color if hovered else text_color
            x = rect.left() + _MENU_ITEM_PADDING_X
            if icon:
                tint = text_color if hovered else icon_color
                pixmap = render_icon(icon, tint, _MENU_ICON, self.devicePixelRatioF())
                if pixmap is not None:
                    painter.drawPixmap(int(x), int(rect.center().y() - pixmap.height() / 2), pixmap)
                x += _MENU_ICON + _MENU_ICON_GAP
            painter.setPen(color)
            painter.drawText(
                QRect(x, rect.top(), rect.right() - x - _MENU_ITEM_PADDING_X, rect.height()),
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
        self.close()
        if label:
            self.actionTriggered.emit(label)

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802 - 覆写 Qt 命名
        if event.key() == Qt.Key_Escape:
            self.close()
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
        self._menu: _SplitMenu | None = None

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
        """最近一次弹出的浮层（没弹过为 ``None``）。"""
        return self._menu

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        main = self._main.sizeHint()
        return QSize(main.width() + self._arrow.sizeHint().width(), main.height())

    def _show_menu(self) -> None:
        if not self._items:
            return
        if self._menu is not None:
            self._menu.close()
            self._menu.deleteLater()
        menu = _SplitMenu(self._items, min_width=max(_MENU_MIN_WIDTH, self.width()), parent=self)
        menu.actionTriggered.connect(self.actionTriggered.emit)
        self._menu = menu
        menu.popup(self.mapToGlobal(QPoint(0, self.height() + _MENU_OFFSET)))


__all__ = ["CSplitButton"]
