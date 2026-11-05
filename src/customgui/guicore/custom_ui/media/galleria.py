"""主图 + 缩略图条（Windows Fluent Design Galleria）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from customgui.appcore import AppSettings

from ..display.palette import tokens
from ..icon_utils import render_icon
from .carousel import _ArrowButton, _IndicatorDots

_RADIUS = 8
_THUMB_WIDTH = 74
_THUMB_HEIGHT = 52
_THUMB_ROW_HEIGHT = 58
_FOOTER_HEIGHT = 30


def _galleria_config() -> tuple[int, int, int, int, int]:
    """(圆角, 缩略图宽, 缩略图高, 缩略图行高, 底部高度)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.media
        return (
            int(cfg.radius),
            int(cfg.galleria_thumb_width),
            int(cfg.galleria_thumb_height),
            int(cfg.galleria_thumb_row_height),
            int(cfg.galleria_footer_height),
        )
    except Exception:
        return _RADIUS, _THUMB_WIDTH, _THUMB_HEIGHT, _THUMB_ROW_HEIGHT, _FOOTER_HEIGHT


def _item_pixmap(item: dict) -> QPixmap:
    image = item.get("image")
    if isinstance(image, QPixmap):
        return QPixmap(image)
    if isinstance(image, str) and image:
        return QPixmap(image)
    return QPixmap()


class _Stage(QWidget):
    """画廊主图区。"""

    def __init__(self, item: dict | None = None, parent=None):
        super().__init__(parent)
        self._radius = _galleria_config()[0]
        self._item = dict(item) if item else {}

    def set_item(self, item: dict | None) -> None:
        self._item = dict(item) if item else {}
        self.update()

    def item(self) -> dict:
        return dict(self._item)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        palette = tokens()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(path, QColor(palette["surface"]))
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)

        content = rect.adjusted(10, 10, -10, -10)
        pixmap = _item_pixmap(self._item)
        if not pixmap.isNull():
            scaled = pixmap.scaled(content.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = content.left() + (content.width() - scaled.width()) / 2
            y = content.top() + (content.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            icon = render_icon("icon_pic_not_found", QColor(palette["muted"]), 40, self.devicePixelRatioF())
            if icon is not None:
                logical = icon.deviceIndependentSize()
                painter.drawPixmap(
                    int(content.center().x() - logical.width() / 2),
                    int(content.center().y() - logical.height() / 2),
                    icon,
                )

        title = str(self._item.get("title", ""))
        description = str(self._item.get("description", ""))
        if title or description:
            height = 50 if description else 32
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
                    QRectF(rect.left() + 14, rect.bottom() - height + 5, rect.width() - 28, 20),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    QFontMetrics(font).elidedText(title, Qt.ElideRight, int(rect.width()) - 28),
                )
            if description:
                font = QFont(self.font())
                font.setPixelSize(12)
                painter.setFont(font)
                painter.setPen(QColor(palette["muted"]))
                painter.drawText(
                    QRectF(rect.left() + 14, rect.bottom() - 26, rect.width() - 28, 18),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    QFontMetrics(font).elidedText(description, Qt.ElideRight, int(rect.width()) - 28),
                )
        painter.end()


class _Thumbnail(QAbstractButton):
    """单个缩略图，选中时用强调色描边。"""

    def __init__(self, item: dict, index: int, parent=None):
        super().__init__(parent)
        _, thumb_width, thumb_height, _, _ = _galleria_config()
        self._item = dict(item)
        self._index = index
        self._active = False
        self._hover = False
        self.setFixedSize(thumb_width, thumb_height)
        self.setCursor(Qt.PointingHandCursor)

    def index(self) -> int:
        return self._index

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def is_active(self) -> bool:
        return self._active

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        palette = tokens()
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, QColor(palette["surface"]))

        pixmap = _item_pixmap(self._item)
        if not pixmap.isNull():
            painter.save()
            painter.setClipPath(path)
            scaled = pixmap.scaled(rect.size().toSize(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawPixmap(
                int(rect.center().x() - scaled.width() / 2),
                int(rect.center().y() - scaled.height() / 2),
                scaled,
            )
            painter.restore()

        if self._active:
            border = QColor(palette["accent"])
            width = 2
        elif self._hover:
            border = QColor(palette["text"])
            width = 2
        else:
            border = QColor(palette["border"])
            width = 1
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, width))
        painter.drawPath(path)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


class CGalleria(QWidget):
    """画廊：主图、缩略图条、翻页箭头与指示点。"""

    itemChanged = Signal(int)

    def __init__(self, items=None, loop: bool = True, parent=None):
        super().__init__(parent)
        _, _, _, self._thumb_row_height, self._footer_height = _galleria_config()
        self._items: list[dict] = []
        self._index = 0
        self._loop = bool(loop)
        self._thumbnails: list[_Thumbnail] = []

        self._stage = _Stage(parent=self)

        thumb_row = QWidget(self)
        self._thumb_layout = QHBoxLayout(thumb_row)
        self._thumb_layout.setContentsMargins(0, 0, 0, 0)
        self._thumb_layout.setSpacing(6)
        self._thumb_layout.addStretch(1)
        thumb_row.setFixedHeight(self._thumb_row_height)

        footer = QWidget(self)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        self._prev_button = _ArrowButton("left", footer)
        self._dots = _IndicatorDots(footer)
        self._next_button = _ArrowButton("right", footer)
        footer_layout.addWidget(self._prev_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._dots)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._next_button)
        footer.setFixedHeight(self._footer_height)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.addWidget(self._stage, 1)
        outer.addWidget(thumb_row)
        outer.addWidget(footer)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._prev_button.clicked.connect(self.prev)
        self._next_button.clicked.connect(self.next)
        self._dots.activated.connect(self.set_index)

        if items:
            self.set_items(items)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def items(self) -> list[dict]:
        return [dict(item) for item in self._items]

    def set_items(self, items) -> None:
        self._items = [dict(item) for item in items]
        self._index = 0
        self._rebuild()

    def current_index(self) -> int:
        return self._index

    def thumbnails(self) -> list[_Thumbnail]:
        return list(self._thumbnails)

    def is_loop(self) -> bool:
        return self._loop

    def set_loop(self, loop: bool) -> None:
        self._loop = bool(loop)

    # ------------------------------------------------------------------
    # 切换
    # ------------------------------------------------------------------
    def set_index(self, index: int) -> None:
        if not self._items:
            return
        target = max(0, min(int(index), len(self._items) - 1))
        if target == self._index:
            return
        self._index = target
        self._apply_index(emit=True)

    def next(self) -> None:
        if not self._items:
            return
        if self._index + 1 < len(self._items):
            self._index += 1
        elif self._loop:
            self._index = 0
        else:
            return
        self._apply_index(emit=True)

    def prev(self) -> None:
        if not self._items:
            return
        if self._index > 0:
            self._index -= 1
        elif self._loop:
            self._index = len(self._items) - 1
        else:
            return
        self._apply_index(emit=True)

    # ------------------------------------------------------------------
    # 构建与刷新
    # ------------------------------------------------------------------
    def _rebuild(self) -> None:
        while self._thumb_layout.count():
            entry = self._thumb_layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._thumbnails = []
        for index, item in enumerate(self._items):
            thumb = _Thumbnail(item, index)
            thumb.clicked.connect(lambda _checked=False, i=index: self.set_index(i))
            self._thumbnails.append(thumb)
            self._thumb_layout.addWidget(thumb)
        self._thumb_layout.addStretch(1)
        self._apply_index(emit=False)

    def _apply_index(self, emit: bool) -> None:
        if self._items:
            self._stage.set_item(self._items[self._index])
        else:
            self._stage.set_item(None)
        for index, thumb in enumerate(self._thumbnails):
            thumb.set_active(index == self._index)
        self._dots.set_state(len(self._items), self._index)
        self._prev_button.setEnabled(len(self._items) > 1)
        self._next_button.setEnabled(len(self._items) > 1)
        if emit:
            self.itemChanged.emit(self._index)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(480, 360)


__all__ = ["CGalleria"]
