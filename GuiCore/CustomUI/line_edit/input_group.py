"""输入框组（复刻 PrimeVue Aura InputGroup / InputGroupAddon）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QWidget

from AppCore import PathFactory

from .input_style import RADIUS, colors, rounded_path, size_spec


class CInputGroupAddon(QWidget):
    """输入框组的前缀/后缀块：图标或文字，自绘背景与分隔线。"""

    def __init__(
        self,
        text: str | None = None,
        icon: str | None = None,
        size: str = "md",
        corners=None,
        widget: QWidget | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CInputGroupAddon_Widget")
        self._text = text or ""
        self._icon = icon
        self._size = size
        self._corners = corners
        self._widget = widget
        self._icon_cache: dict[tuple[str, str, int], QPixmap] = {}

        spec = size_spec(size)
        self.setFixedHeight(spec.height)
        if widget is not None:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(spec.padding_x, 0, spec.padding_x, 0)
            layout.setSpacing(0)
            layout.addWidget(widget, 0, Qt.AlignCenter)
        content = self._content_width()
        self.setFixedWidth(content + spec.padding_x * 2)

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        self._corners = corners
        self.update()

    def set_size(self, size: str) -> None:
        spec = size_spec(size)
        self._size = size
        self.setFixedHeight(spec.height)
        self.setFixedWidth(self._content_width() + spec.padding_x * 2)

    def _content_width(self) -> int:
        spec = size_spec(self._size)
        if self._widget is not None:
            return self._widget.sizeHint().width()
        if self._text:
            return self.fontMetrics().horizontalAdvance(self._text)
        return spec.icon_px if self._icon else 0

    def _tinted_icon(self, color: QColor) -> QPixmap | None:
        if not self._icon:
            return None
        spec = size_spec(self._size)
        path = PathFactory.set_svg_icon(self._icon)
        key = (path, color.name(), spec.icon_px)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached
        source = QPixmap(path)
        if source.isNull():
            return None
        pixmap = source.scaled(spec.icon_px, spec.icon_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()
        self._icon_cache[key] = pixmap
        return pixmap

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        palette = colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillPath(rounded_path(rect, RADIUS, self._corners), QColor(palette["addon_background"]))

        painter.setPen(QPen(QColor(palette["border"]), 1))
        tl = self._corners[0] if self._corners else True
        br = self._corners[2] if self._corners else True
        if not tl:
            painter.drawLine(0, 0, 0, self.height())
        if not br:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        if self._text:
            painter.setPen(QColor(palette["text"]))
            painter.drawText(rect, Qt.AlignCenter, self._text)
        elif self._icon:
            pixmap = self._tinted_icon(QColor(palette["icon"]))
            if pixmap is not None:
                painter.drawPixmap(
                    int((self.width() - pixmap.width()) / 2),
                    int((self.height() - pixmap.height()) / 2),
                    pixmap,
                )
        painter.end()


class CInputGroup(QWidget):
    """横向输入框组：首尾保留外侧圆角，内部相邻边合并。"""

    def __init__(self, widgets: list[QWidget] | None = None, size: str = "md", parent=None):
        super().__init__(parent)
        self.setObjectName("CInputGroup_Widget")
        self._size = size
        self._height = size_spec(size).height
        self.setFixedHeight(self._height)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._widgets: list[QWidget] = []
        for widget in widgets or []:
            self.add_widget(widget)

    def add_widget(self, widget: QWidget) -> None:
        widget.setFixedHeight(self._height)
        setter = getattr(widget, "set_size", None)
        if callable(setter):
            setter(self._size)
        self._layout.addWidget(widget)
        self._widgets.append(widget)
        self._refresh_corners()

    def widgets(self) -> list[QWidget]:
        return list(self._widgets)

    def _refresh_corners(self) -> None:
        count = len(self._widgets)
        for index, widget in enumerate(self._widgets):
            first, last = index == 0, index == count - 1
            setter = getattr(widget, "set_corners", None)
            if callable(setter):
                setter((first, last, last, first))


__all__ = ["CInputGroup", "CInputGroupAddon"]
