"""横向轮播（复刻 PrimeVue Aura Carousel）。"""

from __future__ import annotations

from math import ceil

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from customgui.appcore import AppSettings

from ..display.palette import tokens
from ..icon_utils import render_icon
from ..paint_utils import draw_chevron

#: 卡片圆角
_RADIUS = 8
#: 指示器与翻页条高度
_FOOTER_HEIGHT = 30
#: 相邻卡片间距
_SPACING = 8
#: 单个指示点占位宽度
_DOT_STEP = 14


def _scroll_duration() -> int:
    """翻页动画时长（读取面板配置，缺失时回落到 220ms）。"""
    try:
        return max(80, int(AppSettings.panels.tab_duration))
    except Exception:
        return 220


class _ArrowButton(QAbstractButton):
    """圆形翻页箭头。"""

    def __init__(self, direction: str = "left", parent=None):
        super().__init__(parent)
        self._direction = direction
        self._hover = False
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        if self._hover:
            fill = QColor(palette["surface_strong"])
            fill.setAlpha(120)
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        color = palette["text"] if self.isEnabled() else palette["muted"]
        draw_chevron(painter, QPointF(self.width() / 2, self.height() / 2), color, 8, self._direction, 1.5)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


class _IndicatorDots(QWidget):
    """轮播 / 画廊共用的指示点。"""

    activated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        self._current = 0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(12)

    def set_state(self, count: int, current: int) -> None:
        self._count = max(0, int(count))
        self._current = max(0, int(current))
        self.setFixedWidth(max(0, self._count * _DOT_STEP))
        self.setVisible(self._count > 1)
        self.update()

    def count(self) -> int:
        return self._count

    def current(self) -> int:
        return self._current

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = tokens()
        for index in range(self._count):
            color = QColor(palette["accent"] if index == self._current else palette["muted"])
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(index * _DOT_STEP + 3, 2, 8, 8))
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        index = int(event.position().x()) // _DOT_STEP
        if 0 <= index < self._count:
            self.activated.emit(index)
            event.accept()
            return
        super().mousePressEvent(event)


def _item_pixmap(item: dict) -> QPixmap:
    image = item.get("image")
    if isinstance(image, QPixmap):
        return QPixmap(image)
    if isinstance(image, str) and image:
        return QPixmap(image)
    return QPixmap()


def _paint_cover(painter: QPainter, path: QPainterPath, rect: QRectF, pixmap: QPixmap) -> None:
    """把图片裁剪进圆角卡片（铺满，不拉伸变形）。"""
    if pixmap.isNull():
        return
    painter.save()
    painter.setClipPath(path)
    scaled = pixmap.scaled(rect.size().toSize(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = rect.left() + (rect.width() - scaled.width()) / 2
    y = rect.top() + (rect.height() - scaled.height()) / 2
    painter.drawPixmap(int(x), int(y), scaled)
    painter.restore()


def _paint_placeholder(painter: QPainter, rect: QRectF, dpr: float, palette: dict[str, str]) -> None:
    icon = render_icon("icon_pic_not_found", QColor(palette["muted"]), 32, dpr)
    if icon is not None:
        logical = icon.deviceIndependentSize()
        painter.drawPixmap(
            int(rect.center().x() - logical.width() / 2),
            int(rect.center().y() - logical.height() / 2),
            icon,
        )


class _SlideCard(QWidget):
    """轮播中的单张卡片。"""

    clicked = Signal(int)

    def __init__(self, item: dict, index: int, parent=None):
        super().__init__(parent)
        self._item = dict(item)
        self._index = index
        self.setCursor(Qt.PointingHandCursor)

    def item(self) -> dict:
        return dict(self._item)

    def index(self) -> int:
        return self._index

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        palette = tokens()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, _RADIUS, _RADIUS)
        painter.fillPath(path, QColor(palette["surface"]))

        pixmap = _item_pixmap(self._item)
        _paint_cover(painter, path, rect, pixmap)
        if pixmap.isNull():
            _paint_placeholder(painter, rect, self.devicePixelRatioF(), palette)

        title = str(self._item.get("title", ""))
        description = str(self._item.get("description", ""))
        if title or description:
            height = 50 if description else 34
            painter.setClipPath(path)
            overlay = QColor(palette["surface"])
            overlay.setAlpha(235)
            painter.fillRect(QRectF(rect.left(), rect.bottom() - height, rect.width(), height), overlay)
            painter.setClipRect(rect)
            if title:
                font = QFont(self.font())
                font.setPixelSize(14)
                font.setWeight(QFont.Weight.DemiBold)
                painter.setFont(font)
                painter.setPen(QColor(palette["text"]))
                painter.drawText(
                    QRectF(rect.left() + 12, rect.bottom() - height + 6, rect.width() - 24, 20),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    QFontMetrics(font).elidedText(title, Qt.ElideRight, int(rect.width()) - 24),
                )
            if description:
                font = QFont(self.font())
                font.setPixelSize(12)
                painter.setFont(font)
                painter.setPen(QColor(palette["muted"]))
                painter.drawText(
                    QRectF(rect.left() + 12, rect.bottom() - 26, rect.width() - 24, 18),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    QFontMetrics(font).elidedText(description, Qt.ElideRight, int(rect.width()) - 24),
                )
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)
        painter.end()

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _CarouselViewport(QWidget):
    """裁切轮播条并容纳所有卡片。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strip = QWidget(self)
        self._cards: list[_SlideCard] = []

    def strip(self) -> QWidget:
        return self._strip

    def cards(self) -> list[_SlideCard]:
        return list(self._cards)

    def add_card(self, card: _SlideCard) -> None:
        card.setParent(self._strip)
        self._cards.append(card)

    def clear_cards(self) -> None:
        for card in self._cards:
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def relayout(self, slide_width: int, step: int, height: int) -> None:
        count = len(self._cards)
        width = max(0, count * step)
        self._strip.setGeometry(0, 0, width, height)
        for index, card in enumerate(self._cards):
            card.setGeometry(index * step, 0, slide_width, height)


class CCarousel(QWidget):
    """横向轮播：可见数量、步进、循环、指示点与平滑滚动。"""

    itemClicked = Signal(int)
    pageChanged = Signal(int)

    def __init__(
        self,
        items=None,
        num_visible: int = 1,
        num_scroll: int = 1,
        loop: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._items: list[dict] = []
        self._num_visible = max(1, int(num_visible))
        self._num_scroll = max(1, int(num_scroll))
        self._loop = bool(loop)
        self._page = 0
        self._step = 0
        self._animation: QPropertyAnimation | None = None

        self._viewport = _CarouselViewport(self)
        footer = QWidget(self)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        self._prev_button = _ArrowButton("left", footer)
        self._next_button = _ArrowButton("right", footer)
        self._dots = _IndicatorDots(footer)
        footer_layout.addWidget(self._prev_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._dots)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._next_button)
        footer.setFixedHeight(_FOOTER_HEIGHT)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.addWidget(self._viewport, 1)
        outer.addWidget(footer)

        self._prev_button.clicked.connect(self.prev)
        self._next_button.clicked.connect(self.next)
        self._dots.activated.connect(self.go_to_page)
        self._viewport.installEventFilter(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if items:
            self.set_items(items)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def items(self) -> list[dict]:
        return [dict(item) for item in self._items]

    def set_items(self, items) -> None:
        self._items = [dict(item) for item in items]
        self._page = 0
        self._rebuild()

    def current_index(self) -> int:
        return self._index_for_page(self._page)

    def current_page(self) -> int:
        return self._page

    def page_count(self) -> int:
        count = len(self._items)
        if count <= 0:
            return 0
        visible = min(self._num_visible, count)
        if count <= visible:
            return 1
        return ceil((count - visible) / self._num_scroll) + 1

    def num_visible(self) -> int:
        return self._num_visible

    def set_num_visible(self, value: int) -> None:
        self._num_visible = max(1, int(value))
        self._num_scroll = min(self._num_scroll, self._num_visible)
        self._sync_state()
        self._relayout()
        self._apply_page(animate=False)

    def num_scroll(self) -> int:
        return self._num_scroll

    def set_num_scroll(self, value: int) -> None:
        self._num_scroll = max(1, min(int(value), self._num_visible))
        self._sync_state()
        self._apply_page(animate=False)

    def is_loop(self) -> bool:
        return self._loop

    def set_loop(self, loop: bool) -> None:
        self._loop = bool(loop)

    # ------------------------------------------------------------------
    # 翻页
    # ------------------------------------------------------------------
    def next(self) -> None:
        pages = self.page_count()
        if pages <= 1:
            return
        if self._page + 1 < pages:
            self._page += 1
        elif self._loop:
            self._page = 0
        else:
            return
        self._apply_page(animate=True)

    def prev(self) -> None:
        pages = self.page_count()
        if pages <= 1:
            return
        if self._page > 0:
            self._page -= 1
        elif self._loop:
            self._page = pages - 1
        else:
            return
        self._apply_page(animate=True)

    def go_to_page(self, page: int) -> None:
        pages = self.page_count()
        if pages <= 0:
            return
        target = max(0, min(int(page), pages - 1))
        if target == self._page:
            return
        self._page = target
        self._apply_page(animate=True)

    def set_index(self, index: int) -> None:
        if not self._items:
            return
        target = max(0, min(int(index), len(self._items) - 1))
        page = target // self._num_scroll
        self._page = max(0, min(page, self.page_count() - 1))
        self._apply_page(animate=False)

    def _index_for_page(self, page: int) -> int:
        if not self._items:
            return -1
        return max(0, min(page * self._num_scroll, len(self._items) - self._num_visible))

    def _apply_page(self, animate: bool) -> None:
        self._dots.set_state(self.page_count(), self._page)
        self._animate_to(self.current_index(), animate)
        self.pageChanged.emit(self._page)

    # ------------------------------------------------------------------
    # 构建与布局
    # ------------------------------------------------------------------
    def _rebuild(self) -> None:
        self._viewport.clear_cards()
        for index, item in enumerate(self._items):
            card = _SlideCard(item, index, self._viewport.strip())
            card.clicked.connect(self.itemClicked.emit)
            self._viewport.add_card(card)
        self._sync_state()
        self._relayout()
        self._apply_page(animate=False)

    def _sync_state(self) -> None:
        pages = self.page_count()
        self._page = max(0, min(self._page, pages - 1))
        self._prev_button.setEnabled(pages > 1)
        self._next_button.setEnabled(pages > 1)

    def _relayout(self) -> None:
        count = len(self._items)
        if count <= 0:
            self._viewport.relayout(0, 0, self._viewport.height())
            return
        visible = max(1, min(self._num_visible, count))
        spacing = _SPACING if visible > 1 else 0
        width = self._viewport.width() - spacing * (visible - 1)
        slide_width = max(1, int(width / visible))
        self._step = slide_width + spacing
        self._viewport.relayout(slide_width, self._step, self._viewport.height())
        self._animate_to(self.current_index(), animate=False)

    def _animate_to(self, index: int, animate: bool) -> None:
        if index < 0:
            return
        strip = self._viewport.strip()
        target = QPoint(-index * self._step, 0)
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        if not animate or self._step <= 0:
            strip.move(target)
            return
        animation = QPropertyAnimation(strip, b"pos", self)
        animation.setDuration(_scroll_duration())
        animation.setStartValue(strip.pos())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._animation = animation

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(480, 300)

    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if watched is self._viewport and event.type() == QEvent.Resize:
            self._relayout()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        self._relayout()


__all__ = ["CCarousel"]
