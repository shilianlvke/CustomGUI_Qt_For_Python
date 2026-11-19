"""分组侧边导航（设置窗口 / 偏好页等左侧导航的通用组件）。

结构：一组标题 + 若干可选中条目；条目支持图标、右侧徽标与禁用态。
只负责「展示 + 命中」，不绑定具体业务数据；切换页面由调用方监听
``itemClicked``。

样式全部在 ``paintEvent`` 里实时读设计令牌，主题切换后调用 :meth:`update_style`
即可重绘，不需要重建控件树。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, get_design_tokens, get_theme_manager

from ..icon_utils import render_icon


@dataclass(frozen=True)
class CSideNavItem:
    """导航条目：``item_id`` 由调用方定义，必须唯一。"""

    item_id: str
    text: str
    icon: str = ""
    badge: str = ""
    enabled: bool = True
    tooltip: str = ""
    #: 附加搜索词（设置项标题 / 说明等），不参与显示
    keywords: str = ""


@dataclass(frozen=True)
class CSideNavGroup:
    """一组导航条目（渲染为「小标题 + 条目」）。"""

    title: str
    items: tuple[CSideNavItem, ...] = field(default_factory=tuple)


class _CSideNavButton(QWidget):
    """单条导航：自绘选中底、左侧强调条、图标与徽标。"""

    clicked = Signal(str)

    def __init__(self, item: CSideNavItem, parent=None, *, height: int = 34):
        super().__init__(parent)
        self._item = item
        self._selected = False
        self._hover = False
        self._height = max(24, int(height))
        self.setCursor(Qt.PointingHandCursor if item.enabled else Qt.ArrowCursor)
        self.setFixedHeight(self._height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if item.tooltip:
            self.setToolTip(item.tooltip)

    @property
    def item_id(self) -> str:
        return self._item.item_id

    def item(self) -> CSideNavItem:
        return self._item

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        value = bool(selected) and self._item.enabled
        if value != self._selected:
            self._selected = value
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(180, self._height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(80, self._height)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        tokens = get_design_tokens()
        colors = tokens.colors
        enabled = self._item.enabled
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, tokens.radius.control, tokens.radius.control)

        if self._selected:
            fill = QColor(colors.accent)
            fill.setAlpha(30)
            painter.fillPath(path, fill)
            bar = QRectF(rect.left() + 1, rect.top() + 8, 2, rect.height() - 16)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors.accent))
            painter.drawRoundedRect(bar, 1, 1)
        elif self._hover and enabled:
            painter.fillPath(path, QColor(colors.surface_interactive_hover))

        text_color = QColor(colors.text_active if self._selected else colors.text_primary)
        icon_color = QColor(colors.accent if self._selected else colors.text_muted)
        if not enabled:
            text_color.setAlpha(110)
            icon_color.setAlpha(90)

        left = rect.left() + 12
        if self._item.icon:
            pixmap = render_icon(self._item.icon, icon_color, 16, self.devicePixelRatioF())
            if pixmap is not None:
                painter.drawPixmap(int(left), int(rect.center().y() - 8), pixmap)
                left += 24

        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold if self._selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(text_color)

        badge_width = self._badge_width(font)
        right = rect.right() - 10 - badge_width
        text_rect = QRectF(left, rect.top(), max(0.0, right - left - 6), rect.height())
        elided = QFontMetrics(font).elidedText(self._item.text, Qt.TextElideMode.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

        if badge_width > 0:
            self._paint_badge(painter, font, rect, badge_width)
        painter.end()

    def _badge_font(self, base: QFont) -> QFont:
        font = QFont(base)
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def _badge_width(self, base: QFont) -> float:
        if not self._item.badge:
            return 0.0
        metrics = QFontMetrics(self._badge_font(base))
        return max(18.0, metrics.horizontalAdvance(self._item.badge) + 12.0)

    def _paint_badge(self, painter: QPainter, base: QFont, rect: QRectF, width: float) -> None:
        font = self._badge_font(base)
        painter.setFont(font)
        pill = QRectF(rect.right() - 8 - width, rect.center().y() - 8, width, 16)
        path = QPainterPath()
        path.addRoundedRect(pill, 8, 8)
        accent = QColor(get_design_tokens().colors.accent)
        fill = QColor(accent)
        fill.setAlpha(24)
        painter.fillPath(path, fill)
        pen = QColor(accent)
        pen.setAlpha(90)
        painter.setPen(QPen(pen, 1))
        painter.drawPath(path)
        painter.setPen(accent)
        painter.drawText(pill, Qt.AlignCenter, self._item.badge)

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._item.enabled:
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if (
            self._item.enabled
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self._item.item_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CSideNav(QWidget):
    """分组侧边导航容器。

    用法::

        nav = CSideNav([
            CSideNavGroup("基座设置", (CSideNavItem("appearance", "外观", "icon_palette"),)),
            CSideNavGroup("插件设置", (CSideNavItem("plugin.x", "X 插件", "icon_store", "示例"),)),
        ])
        nav.itemClicked.connect(show_page)
        nav.set_current("appearance")
    """

    itemClicked = Signal(str)

    def __init__(
        self,
        groups: tuple[CSideNavGroup, ...] | list[CSideNavGroup] | None = None,
        parent=None,
        *,
        item_height: int = 34,
    ):
        super().__init__(parent)
        self._item_height = max(24, int(item_height))
        self._buttons: list[_CSideNavButton] = []
        self._group_widgets: list[QWidget] = []
        self._current = ""
        self._query = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        self._layout = layout
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if groups:
            self.set_groups(groups)
        get_theme_manager().subscribe(self.update_style)

    # ------------------------------------------------------------------
    def set_groups(self, groups: tuple[CSideNavGroup, ...] | list[CSideNavGroup]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._buttons.clear()
        self._group_widgets.clear()

        first_enabled = ""
        for index, group in enumerate(groups):
            box = QWidget(self)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(1)
            if index:
                box_layout.addSpacing(14)
            if group.title:
                label = _CSideNavGroupLabel(group.title, box)
                box_layout.addWidget(label)
            for item in group.items:
                button = _CSideNavButton(item, box, height=self._item_height)
                button.clicked.connect(self._on_clicked)
                box_layout.addWidget(button)
                self._buttons.append(button)
                if not first_enabled and item.enabled:
                    first_enabled = item.item_id
            self._layout.addWidget(box)
            self._group_widgets.append(box)
        self._layout.addStretch(1)
        if self._current and self._find(self._current) is not None:
            self.set_current(self._current)
        elif first_enabled:
            self.set_current(first_enabled)
        self._apply_filter()

    def set_current(self, item_id: str) -> None:
        self._current = str(item_id)
        for button in self._buttons:
            button.set_selected(button.item_id == self._current)

    def current(self) -> str:
        return self._current

    def item_ids(self) -> tuple[str, ...]:
        return tuple(button.item_id for button in self._buttons)

    def visible_count(self) -> int:
        return sum(1 for button in self._buttons if not button.isHidden())

    def filter(self, text: str) -> None:
        """按条目文字过滤；空字符串恢复全部。"""
        self._query = str(text or "").strip().lower()
        self._apply_filter()

    def _apply_filter(self) -> None:
        for button in self._buttons:
            item = button.item()
            haystack = f"{item.text} {item.keywords}".lower()
            hit = not self._query or self._query in haystack
            button.setVisible(hit)
        for group_widget in self._group_widgets:
            visible = any(
                not child.isHidden() for child in group_widget.findChildren(_CSideNavButton)
            )
            group_widget.setVisible(visible)

    def _find(self, item_id: str) -> _CSideNavButton | None:
        for button in self._buttons:
            if button.item_id == item_id:
                return button
        return None

    def _on_clicked(self, item_id: str) -> None:
        if item_id == self._current:
            return
        self.set_current(item_id)
        self.itemClicked.emit(item_id)

    def update_style(self) -> None:
        for label in self.findChildren(_CSideNavGroupLabel):
            label.update_style()
        for button in self._buttons:
            button.update()
        self.update()

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        # 首次显示时按最终宽度重新排版，避免 elide 用旧宽度
        QTimer.singleShot(0, self.update)


class _CSideNavGroupLabel(QWidget):
    """小标题 + 右侧发丝线。"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(180, 22)

    def update_style(self) -> None:
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        font = QFont(AppSettings.family)
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        color = QColor(colors.text_muted)
        painter.setPen(color)
        metrics = QFontMetrics(font)
        text = self._text.upper() if self._text.isascii() else self._text
        width = metrics.horizontalAdvance(text)
        painter.drawText(QRectF(10, 0, width + 4, self.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        line_color = QColor(colors.text_primary)
        line_color.setAlpha(26)
        painter.setPen(QPen(line_color, 1))
        y = self.height() / 2
        painter.drawLine(int(10 + width + 10), int(y), self.width() - 6, int(y))
        painter.end()


__all__ = ["CSideNav", "CSideNavGroup", "CSideNavItem"]
