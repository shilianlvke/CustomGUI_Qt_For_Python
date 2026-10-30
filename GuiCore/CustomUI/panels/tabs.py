"""标签页（复刻 PrimeVue Aura Tabs）。

标签栏自绘：支持图标、可关闭、禁用、top/bottom 两种位置，激活项下方
（或上方）有一条 2px 主色指示条，切换时滑动到新位置。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from AppCore import AppSettings

from ..icon_utils import render_icon
from .style import panel_colors, panel_settings, with_alpha

_TAB_HEIGHTS = {"sm": 34, "md": 40, "lg": 46}
_FONT_SIZES = {"sm": 13, "md": 14, "lg": 15}
_ICON_SIZES = {"sm": 14, "md": 16, "lg": 18}
_PAD_X = {"sm": 12, "md": 14, "lg": 16}
_CLOSE_WIDTH = 20
_ICON_GAP = 7


@dataclass
class _TabItem:
    """单个标签的元数据。"""

    title: str
    icon: str | QIcon | None = None
    closable: bool = False
    enabled: bool = True
    visible: bool = True


class _TabBar(QWidget):
    """自绘标签栏。"""

    clicked = Signal(int)
    closeRequested = Signal(int)
    currentRequested = Signal(int)

    def __init__(self, position: str = "top", size: str = "md", parent=None):
        super().__init__(parent)
        self._position = "bottom" if position == "bottom" else "top"
        self._size = size if size in _TAB_HEIGHTS else "md"
        self._items: list[_TabItem] = []
        self._current = -1
        self._hover = -1
        self._hover_close = -1
        self._icon_cache: dict[tuple, object] = {}
        self._indicator = QRectF()
        self._from = QRectF()
        self._to = QRectF()
        self._animation: QVariantAnimation | None = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_TAB_HEIGHTS[self._size])
        self._apply_font()

    # ------------------------------------------------------------------
    # 基础属性
    # ------------------------------------------------------------------
    def _apply_font(self) -> None:
        font = QFont(AppSettings.family)
        font.setPixelSize(_FONT_SIZES[self._size])
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)

    def set_size(self, size: str) -> None:
        self._size = size if size in _TAB_HEIGHTS else "md"
        self._apply_font()
        self.setFixedHeight(_TAB_HEIGHTS[self._size])
        self._reset_indicator()

    def set_position(self, position: str) -> None:
        self._position = "bottom" if position == "bottom" else "top"
        self._reset_indicator()
        self.update()

    def set_items(self, items: list[_TabItem]) -> None:
        self._items = items
        self._reset_indicator()

    def refresh(self) -> None:
        self._reset_indicator()

    def count(self) -> int:
        return len(self._items)

    def current(self) -> int:
        return self._current

    def set_current(self, index: int, animate: bool = True) -> None:
        if not (0 <= index < len(self._items)):
            self._current = -1
            self._indicator = QRectF()
            self.update()
            return
        previous = self._current
        self._current = index
        target = self._indicator_rect(index)
        if animate and previous != index and not self._indicator.isNull() and target is not None:
            self._animate_indicator(target)
        else:
            if target is not None:
                self._indicator = target
            self.update()
        self.ensureVisible(index)

    def ensureVisible(self, index: int) -> None:
        """标签压缩后始终可见（当前不滚动，仅保证选中项不被挤没）。"""

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _tab_font(self) -> QFont:
        return self.font()

    def _content_width(self, item: _TabItem, metrics: QFontMetrics) -> int:
        width = _PAD_X[self._size] * 2
        if item.icon is not None:
            width += _ICON_SIZES[self._size] + _ICON_GAP
        if item.closable:
            width += _CLOSE_WIDTH
        if item.title:
            width += metrics.horizontalAdvance(item.title)
        return max(44, width)

    def _layout_rects(self) -> dict[int, QRectF]:
        visible = [index for index, item in enumerate(self._items) if item.visible]
        if not visible:
            return {}

        metrics = QFontMetrics(self._tab_font())
        widths = {index: self._content_width(self._items[index], metrics) for index in visible}
        total = sum(widths.values())
        available = max(0, self.width())

        if total > available and total > 0:
            scale = available / total
            widths = {index: max(36, int(width * scale)) for index, width in widths.items()}
            total = sum(widths.values())
            if total > available:
                each = max(28, available // len(visible))
                widths = {index: min(width, each) for index, width in widths.items()}

        rects: dict[int, QRectF] = {}
        x = 0.0
        for index in visible:
            width = float(widths[index])
            rects[index] = QRectF(x, 0, width, float(self.height()))
            x += width
        return rects

    def _indicator_rect(self, index: int) -> QRectF | None:
        rect = self._layout_rects().get(index)
        if rect is None:
            return None
        y = 0.0 if self._position == "bottom" else self.height() - 2.0
        return QRectF(rect.left() + 6, y, max(0.0, rect.width() - 12), 2.0)

    def _reset_indicator(self) -> None:
        self._stop_animation()
        target = self._indicator_rect(self._current)
        self._indicator = target or QRectF()
        self.update()

    # ------------------------------------------------------------------
    # 指示条动画
    # ------------------------------------------------------------------
    def _stop_animation(self) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None

    def _animate_indicator(self, target: QRectF) -> None:
        _, duration, _, _ = panel_settings()
        if duration <= 0 or not self.isVisible():
            self._indicator = target
            self.update()
            return

        self._stop_animation()
        self._from = QRectF(self._indicator)
        self._to = QRectF(target)
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(duration)
        animation.valueChanged.connect(self._on_indicator_tick)
        animation.finished.connect(lambda: self._snap_indicator(target))
        animation.start()
        self._animation = animation

    def _on_indicator_tick(self, value: float) -> None:
        start, end = self._from, self._to
        self._indicator = QRectF(
            start.left() + (end.left() - start.left()) * value,
            start.top() + (end.top() - start.top()) * value,
            start.width() + (end.width() - start.width()) * value,
            start.height(),
        )
        self.update()

    def _snap_indicator(self, target: QRectF) -> None:
        self._stop_animation()
        self._indicator = QRectF(target)
        self.update()

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._stop_animation()
        target = self._indicator_rect(self._current)
        self._indicator = target or QRectF()
        self.update()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _text_rect(self, rect: QRectF, item: _TabItem) -> QRectF:
        left = rect.left() + _PAD_X[self._size]
        if item.icon is not None:
            left += _ICON_SIZES[self._size] + _ICON_GAP
        right = rect.right() - _PAD_X[self._size]
        if item.closable:
            right -= _CLOSE_WIDTH
        return QRectF(left, rect.top(), max(0.0, right - left), rect.height())

    def _close_rect(self, rect: QRectF) -> QRectF:
        return QRectF(rect.right() - _PAD_X[self._size] - _CLOSE_WIDTH + 2, rect.center().y() - 9, 18, 18)

    def _tab_color(self, index: int, item: _TabItem) -> QColor:
        colors = panel_colors()
        if not item.enabled:
            return with_alpha(colors["muted"], 140)
        if index == self._current:
            return QColor(colors["accent"])
        if index == self._hover:
            return QColor(colors["text"])
        return QColor(colors["muted"])

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = panel_colors()
        rects = self._layout_rects()

        # 与内容区之间的 1px 分隔线
        line_y = 0.5 if self._position == "bottom" else self.height() - 0.5
        painter.setPen(QPen(QColor(colors["divider"]), 1))
        painter.drawLine(0, int(line_y), self.width(), int(line_y))

        metrics = QFontMetrics(self.font())
        dpr = self.devicePixelRatioF()

        for index, rect in rects.items():
            item = self._items[index]
            if index == self._hover and item.enabled and index != self._current:
                painter.setPen(Qt.NoPen)
                painter.setBrush(with_alpha(colors["text"], 16))
                painter.drawRoundedRect(rect.adjusted(2, 3, -2, -3), 6, 6)

            color = self._tab_color(index, item)

            if item.icon is not None:
                icon_size = _ICON_SIZES[self._size]
                key = (str(item.icon), color.name(), icon_size, round(dpr, 2))
                pixmap = self._icon_cache.get(key)
                if pixmap is None:
                    pixmap = render_icon(item.icon, color, icon_size, dpr)
                    self._icon_cache[key] = pixmap
                if pixmap is not None:
                    x = rect.left() + _PAD_X[self._size]
                    painter.drawPixmap(
                        int(x),
                        int(rect.center().y() - icon_size / 2),
                        pixmap,
                    )

            text_rect = self._text_rect(rect, item)
            if item.title:
                elided = metrics.elidedText(item.title, Qt.ElideRight, int(text_rect.width()))
                painter.setPen(color)
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

            if item.closable:
                self._paint_close(painter, rect, index, colors)

        if not self._indicator.isNull():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors["accent"]))
            painter.drawRoundedRect(self._indicator, 1, 1)

        painter.end()

    def _paint_close(self, painter: QPainter, rect: QRectF, index: int, colors: dict) -> None:
        close = self._close_rect(rect)
        if index == self._hover_close:
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(colors["text"], 28))
            painter.drawEllipse(close)
        color = QColor(colors["accent"] if index == self._hover_close else colors["muted"])
        painter.setPen(QPen(color, 1.4, Qt.SolidLine, Qt.RoundCap))
        inset = 5.5
        painter.drawLine(
            int(close.left() + inset),
            int(close.top() + inset),
            int(close.right() - inset),
            int(close.bottom() - inset),
        )
        painter.drawLine(
            int(close.right() - inset),
            int(close.top() + inset),
            int(close.left() + inset),
            int(close.bottom() - inset),
        )

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _index_at(self, position) -> int:
        for index, rect in self._layout_rects().items():
            if rect.contains(position):
                return index
        return -1

    def _close_at(self, index: int, position) -> bool:
        rect = self._layout_rects().get(index)
        return rect is not None and self._close_rect(rect).contains(position)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        index = self._index_at(event.position())
        if index < 0:
            return
        item = self._items[index]
        if item.closable and self._close_at(index, event.position()):
            self.closeRequested.emit(index)
            event.accept()
            return
        if not item.enabled:
            return
        self.clicked.emit(index)
        self.currentRequested.emit(index)
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = self._index_at(event.position())
        hover_close = (
            index if (index >= 0 and self._items[index].closable and self._close_at(index, event.position())) else -1
        )
        if index != self._hover or hover_close != self._hover_close:
            self._hover = index
            self._hover_close = hover_close
            self.setCursor(Qt.PointingHandCursor if index >= 0 else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = -1
        self._hover_close = -1
        self.setCursor(Qt.PointingHandCursor)
        self.update()
        super().leaveEvent(event)

    def event(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.type() == QEvent.StyleChange:
            self._reset_indicator()
        return super().event(event)

    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        visible = [index for index, item in enumerate(self._items) if item.visible and item.enabled]
        if not visible:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Up):
            position = visible.index(self._current) if self._current in visible else 0
            self.currentRequested.emit(visible[max(0, position - 1)])
        elif event.key() in (Qt.Key_Right, Qt.Key_Down):
            position = visible.index(self._current) if self._current in visible else -1
            self.currentRequested.emit(visible[min(len(visible) - 1, position + 1)])
        elif event.key() == Qt.Key_Home:
            self.currentRequested.emit(visible[0])
        elif event.key() == Qt.Key_End:
            self.currentRequested.emit(visible[-1])
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if 0 <= self._current < len(self._items):
                self.clicked.emit(self._current)
        else:
            super().keyPressEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        metrics = QFontMetrics(self.font())
        width = sum(self._content_width(item, metrics) for item in self._items if item.visible)
        return QSize(max(120, width), _TAB_HEIGHTS[self._size])


class CTabs(QWidget):
    """标签页容器。"""

    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)
    tabBarClicked = Signal(int)

    def __init__(
        self,
        size: str = "md",
        tab_position: str = "top",
        animated: bool = True,
        closable: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._animated = animated
        self._closable = closable
        self._items: list[_TabItem] = []
        self._index = -1

        self._bar = _TabBar(tab_position, size, self)
        self._stack = QStackedWidget(self)
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if tab_position == "bottom":
            layout.addWidget(self._stack, 1)
            layout.addWidget(self._bar, 0)
        else:
            layout.addWidget(self._bar, 0)
            layout.addWidget(self._stack, 1)

        self._bar.set_items(self._items)
        self._bar.currentRequested.connect(self.set_current_index)
        self._bar.clicked.connect(self.tabBarClicked.emit)
        self._bar.closeRequested.connect(self.tabCloseRequested.emit)

    # ------------------------------------------------------------------
    # 标签维护
    # ------------------------------------------------------------------
    def add_tab(
        self,
        title: str,
        widget: QWidget | None = None,
        icon: str | QIcon | None = None,
        closable: bool | None = None,
        enabled: bool = True,
    ) -> int:
        return self.insert_tab(self.count(), title, widget, icon, closable, enabled)

    def insert_tab(
        self,
        index: int,
        title: str,
        widget: QWidget | None = None,
        icon: str | QIcon | None = None,
        closable: bool | None = None,
        enabled: bool = True,
    ) -> int:
        index = max(0, min(int(index), self.count()))
        item = _TabItem(
            title=title,
            icon=icon,
            closable=self._closable if closable is None else closable,
            enabled=enabled,
        )
        page = widget or QWidget()
        self._items.insert(index, item)
        self._stack.insertWidget(index, page)
        self._bar.refresh()

        if self._index < 0:
            self._index = index
            self._stack.setCurrentIndex(index)
            self._bar.set_current(index, animate=False)
        elif index <= self._index:
            self._index += 1
            self._bar.set_current(self._index, animate=False)
        self._bar.resize(self._bar.size())
        return index

    def remove_tab(self, index: int) -> None:
        if not (0 <= index < self.count()):
            return
        page = self._stack.widget(index)
        self._stack.removeWidget(page)
        page.deleteLater()
        self._items.pop(index)

        if self.count() == 0:
            self._index = -1
            self._bar.refresh()
            self._bar.set_current(-1, animate=False)
            return

        if index < self._index:
            self._index -= 1
        elif index == self._index:
            self._index = min(index, self.count() - 1)
            self._stack.setCurrentIndex(self._index)
            self._bar.refresh()
            self._bar.set_current(self._index, animate=False)
            self.currentChanged.emit(self._index)
            return
        self._bar.refresh()
        self._bar.set_current(self._index, animate=False)

    def clear(self) -> None:
        while self.count():
            self.remove_tab(self.count() - 1)

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def count(self) -> int:
        return len(self._items)

    def current_index(self) -> int:
        return self._index

    def current_widget(self) -> QWidget | None:
        return self._stack.currentWidget() if self._index >= 0 else None

    def widget(self, index: int) -> QWidget | None:
        return self._stack.widget(index) if 0 <= index < self.count() else None

    def set_current_index(self, index: int, animate: bool | None = None) -> None:
        if not (0 <= index < self.count()) or index == self._index:
            return
        self._index = index
        self._stack.setCurrentIndex(index)
        self._bar.set_current(index, self._animated if animate is None else animate)
        self.currentChanged.emit(index)

    def set_current_widget(self, widget: QWidget, animate: bool | None = None) -> None:
        index = self._stack.indexOf(widget)
        if index >= 0:
            self.set_current_index(index, animate)

    def set_tab_text(self, index: int, title: str) -> None:
        if 0 <= index < self.count():
            self._items[index].title = title
            self._bar.refresh()

    def tab_text(self, index: int) -> str:
        return self._items[index].title if 0 <= index < self.count() else ""

    def set_tab_icon(self, index: int, icon: str | QIcon | None) -> None:
        if 0 <= index < self.count():
            self._items[index].icon = icon
            self._bar.refresh()

    def set_tab_enabled(self, index: int, enabled: bool) -> None:
        if 0 <= index < self.count():
            self._items[index].enabled = enabled
            self._bar.update()

    def set_tab_visible(self, index: int, visible: bool) -> None:
        if 0 <= index < self.count():
            self._items[index].visible = visible
            self._stack.widget(index).setVisible(visible)
            self._bar.refresh()
            if not visible and index == self._index:
                for offset in range(1, self.count() + 1):
                    candidate = (index + offset) % self.count()
                    if self._items[candidate].visible:
                        self.set_current_index(candidate)
                        break

    def set_closable(self, closable: bool) -> None:
        self._closable = closable
        for item in self._items:
            item.closable = closable
        self._bar.refresh()

    def set_size(self, size: str) -> None:
        self._bar.set_size(size)

    def tab_bar(self) -> _TabBar:
        return self._bar


__all__ = ["CTabs"]
