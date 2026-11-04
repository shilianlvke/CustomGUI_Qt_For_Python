"""输入框组（复刻 PrimeVue Aura InputGroup / InputGroupAddon）。

对齐 Aura 的边框规则：**每个块只画自己的外轮廓边**，共享边交给邻居的边框去画
（``.p-inputgroupaddon`` 只带 top/bottom，first-child 补 inline-start、last-child 补
inline-end、紧跟另一个 addon 时补 inline-start）。这样接缝永远是 1px 的单线，
既不会缺边，也不会出现双线。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..icon_utils import render_icon
from .input_style import colors, field_font, radius, rounded_path, size_spec


class CInputGroupAddon(QWidget):
    """输入框组的前缀/后缀块：图标或文字，自绘底色与轮廓。"""

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
        #: 哪几条竖边算「自己的外轮廓」（由 CInputGroup 按位置刷新）
        self._edge_left = True
        self._edge_right = True

        spec = size_spec(size)
        self.setFont(field_font(size))
        self.setFixedHeight(spec.height)
        if widget is not None:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(spec.padding_x, 0, spec.padding_x, 0)
            layout.setSpacing(0)
            layout.addWidget(widget, 0, Qt.AlignCenter)
        self.setFixedWidth(self._content_width() + spec.padding_x * 2)

    def set_corners(self, corners: tuple[bool, bool, bool, bool]) -> None:
        self._corners = corners
        self.update()

    def set_edge_borders(self, left: bool, right: bool) -> None:
        """指定左右竖边是否属于本块（组内只有首/尾块才画外轮廓）。"""
        self._edge_left = left
        self._edge_right = right
        self.update()

    def set_size(self, size: str) -> None:
        spec = size_spec(size)
        self._size = size
        self.setFont(field_font(size))
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
        return render_icon(self._icon, color, spec.icon_px, self.devicePixelRatioF())

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        palette = colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(self.rect())

        # 底色铺满整块：与相邻块之间不留 1px 缝
        painter.fillPath(rounded_path(body, radius(), self._corners), QColor(palette["addon_background"]))

        # 描边：先画完整轮廓，再把共享边裁掉
        stroke = rounded_path(body.adjusted(0.5, 0.5, -0.5, -0.5), radius(), self._corners)
        left = 0.0 if self._edge_left else 1.0
        right = 0.0 if self._edge_right else 1.0
        painter.setClipRect(QRectF(left, 0.0, self.width() - left - right, self.height()))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(stroke)
        painter.setClipping(False)

        if self._text:
            painter.setPen(QColor(palette["text"]))
            painter.drawText(body, Qt.AlignCenter, self._text)
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
        previous_addon = False
        for index, widget in enumerate(self._widgets):
            first, last = index == 0, index == count - 1
            setter = getattr(widget, "set_corners", None)
            if callable(setter):
                setter((first, last, last, first))
            if isinstance(widget, CInputGroupAddon):
                # addon 只画外轮廓；紧跟另一个 addon 时补左竖边（对齐 Aura 的
                # ``.p-inputgroupaddon + .p-inputgroupaddon { border-inline-start }``）
                widget.set_edge_borders(left=first or previous_addon, right=last)
                previous_addon = True
            else:
                previous_addon = False


__all__ = ["CInputGroup", "CInputGroupAddon"]
