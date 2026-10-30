"""下拉字段基类：输入框外观、箭头、浮层生命周期。

``CSelect`` / ``CMultiSelect`` / ``CAutoComplete`` / ``CTreeSelect`` /
``CDatePicker`` 共用同一套盒子绘制与弹层管理，差异只在“弹层里放什么”和
“控件区显示什么”。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .input_style import RADIUS, colors, field_font, rounded_path, size_spec
from .overlay import CPopover
from ..paint_utils import draw_chevron

#: 右侧留给箭头/图标的宽度
AFFIX_WIDTH = 30


class CDropdownField(QWidget):
    """下拉字段基类（自绘盒子 + 浮层）。"""

    def __init__(self, placeholder: str = "", size: str = "md", chevron: bool = True, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._size = size
        self._hover = False
        self._open = False
        self._popover: CPopover | None = None
        self._show_chevron = chevron

        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFont(field_font(size))
        self.setFixedHeight(size_spec(size).height)

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def _spec(self):
        return size_spec(self._size)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(220, self._spec().height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(120, self._spec().height)

    def set_size(self, size: str) -> None:
        self._size = size if size in ("sm", "md", "lg") else "md"
        self.setFont(field_font(self._size))
        self.setFixedHeight(self._spec().height)
        self.updateGeometry()
        self.update()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _text_left(self) -> float:
        return float(self._spec().padding_x)

    def _content_right(self) -> float:
        right = self.width() - self._spec().padding_x
        return right - AFFIX_WIDTH + 10 if self._show_chevron else right

    def _paint_box(self, painter: QPainter, invalid: bool = False) -> None:
        palette = colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        enabled = self.isEnabled()
        background = palette["disabled_background"] if not enabled else palette["background"]
        border = palette["border"]
        if invalid:
            border = palette["invalid_border"]
        elif self.hasFocus() or self._open:
            border = palette["focus_border"]
        elif self._hover:
            border = palette["hover_border"]
        if not enabled:
            painter.setOpacity(0.6)
        painter.setBrush(QColor(background))
        painter.setPen(QPen(QColor(border), 1))
        painter.drawPath(rounded_path(rect, RADIUS))

    def _paint_chevron(self, painter: QPainter) -> None:
        if not self._show_chevron:
            return
        palette = colors()
        center = QPointF(self.width() - self._spec().padding_x - 6, self.height() / 2)
        draw_chevron(painter, center, palette["icon"], 7.5, "up" if self._open else "down", 1.5)

    # ------------------------------------------------------------------
    # 浮层
    # ------------------------------------------------------------------
    def is_open(self) -> bool:
        return self._open

    def popup(self) -> CPopover | None:
        return self._popover

    def _popup_width(self) -> int:
        return max(self.width(), 200)

    def _build_popup(self) -> QWidget | None:  # pragma: no cover - 由子类实现
        return None

    def _toggle_popup(self) -> None:
        if self._open:
            self.close_popup()
            return
        content = self._build_popup()
        if content is None:
            return
        popover = CPopover(self, width=self._popup_width())
        popover.content_layout().addWidget(content)
        popover.closed.connect(self._on_popup_closed)
        popover.show_at(self)
        self._popover = popover
        self._open = True
        self.update()

    def close_popup(self) -> None:
        popover = self._popover
        if popover is not None:
            popover.hide()

    def _on_popup_closed(self) -> None:
        popover = self._popover
        self._popover = None
        self._open = False
        if popover is not None:
            popover.deleteLater()
        self.update()

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setFocus(Qt.MouseFocusReason)
            self._toggle_popup()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.key() == Qt.Key_Escape and self._open:
            self.close_popup()
            event.accept()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter) and not self._open:
            self._toggle_popup()
            event.accept()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self.close_popup()
        super().hideEvent(event)


__all__ = ["CDropdownField", "AFFIX_WIDTH"]
