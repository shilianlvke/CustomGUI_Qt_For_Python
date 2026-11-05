"""带左右图标槽的输入框（复刻 PrimeVue IconField / InputIcon）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QWidget

from ..icon_utils import render_icon
from .input_style import InputSize, colors, radius, rounded_path, size_spec
from .input_text import CInputText


class _IconSlot(QAbstractButton):
    """输入框外侧的图标槽（左边或右边）。"""

    def __init__(self, side: str, spec: InputSize, parent=None):
        super().__init__(parent)
        self._side = "right" if side == "right" else "left"
        self._spec = spec
        self._icon: str | QIcon | None = None
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._sync_geometry()

    def _sync_geometry(self) -> None:
        width = self._spec.icon_px + self._spec.padding_x * 2
        self.setFixedSize(width, self._spec.height)

    def set_spec(self, spec: InputSize) -> None:
        self._spec = spec
        self._sync_geometry()
        self.update()

    def icon(self) -> str | QIcon | None:
        return self._icon

    def set_icon(self, icon: str | QIcon | None) -> None:
        self._icon = icon
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        corners = (True, False, False, True) if self._side == "left" else (False, True, True, False)
        path = rounded_path(rect, radius(), corners)
        painter.fillPath(path, QColor(palette["addon_background"]))
        if self._hover:
            tint = QColor(palette["hover_border"])
            tint.setAlpha(36)
            painter.fillPath(path, tint)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)

        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        pixmap = render_icon(
            self._icon,
            QColor(palette["icon"]),
            self._spec.icon_px,
            self.devicePixelRatioF(),
        )
        if pixmap is not None:
            logical = pixmap.deviceIndependentSize()
            painter.drawPixmap(
                int((self.width() - logical.width()) / 2),
                int((self.height() - logical.height()) / 2),
                pixmap,
            )
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


class CIconField(QWidget):
    """左右图标槽 + 单行输入框；图标位置可分别设置与清除。"""

    leftIconClicked = Signal()
    rightIconClicked = Signal()

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        size: str = "md",
        left_icon: str | QIcon | None = None,
        right_icon: str | QIcon | None = None,
        invalid: bool = False,
        fluid: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._size = size
        spec = size_spec(size)
        self._field = CInputText(
            text=text,
            placeholder=placeholder,
            size=size,
            invalid=invalid,
            fluid=fluid,
            parent=self,
        )
        self._left = _IconSlot("left", spec, self)
        self._right = _IconSlot("right", spec, self)
        for slot in (self._left, self._right):
            slot.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._left)
        layout.addWidget(self._field, 1)
        layout.addWidget(self._right)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding if fluid else QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.setFixedHeight(spec.height)

        self._left.clicked.connect(self.leftIconClicked.emit)
        self._right.clicked.connect(self.rightIconClicked.emit)

        if left_icon is not None:
            self.set_icon(left_icon, "left")
        if right_icon is not None:
            self.set_icon(right_icon, "right")
        self._sync_corners()

    # ------------------------------------------------------------------
    # 输入框
    # ------------------------------------------------------------------
    def field(self) -> CInputText:
        return self._field

    def line_edit(self) -> CInputText:
        return self._field

    def text(self) -> str:
        return self._field.text()

    def set_text(self, text: str) -> None:
        self._field.setText(text)

    def set_placeholder(self, text: str) -> None:
        self._field.setPlaceholderText(text)

    def set_invalid(self, invalid: bool) -> None:
        self._field.set_invalid(invalid)

    def set_size(self, size: str) -> None:
        self._size = size
        spec = size_spec(size)
        self._field.set_size(size)
        self._left.set_spec(spec)
        self._right.set_spec(spec)
        self.setFixedHeight(spec.height)
        self._sync_corners()

    # ------------------------------------------------------------------
    # 图标
    # ------------------------------------------------------------------
    def set_icon(self, icon: str | QIcon | None, position: str = "left") -> None:
        """设置某一侧的图标；``icon=None`` 等价于清除该侧。"""
        slot = self._slot(position)
        if slot is None:
            return
        if icon is None:
            self.clear_icon(position)
            return
        slot.set_icon(icon)
        slot.show()
        self._sync_corners()

    def clear_icon(self, position: str | None = None) -> None:
        """清除图标；``position=None`` 时清空两侧。"""
        positions = ("left", "right") if position is None else (position,)
        for side in positions:
            slot = self._slot(side)
            if slot is None:
                continue
            slot.set_icon(None)
            slot.hide()
        self._sync_corners()

    def has_icon(self, position: str = "left") -> bool:
        slot = self._slot(position)
        return slot is not None and slot.icon() is not None

    def icon(self, position: str = "left"):
        slot = self._slot(position)
        return None if slot is None else slot.icon()

    def left_slot(self) -> _IconSlot:
        return self._left

    def right_slot(self) -> _IconSlot:
        return self._right

    def _slot(self, position: str) -> _IconSlot | None:
        if position == "left":
            return self._left
        if position == "right":
            return self._right
        return None

    def _sync_corners(self) -> None:
        left = self._left.icon() is not None
        right = self._right.icon() is not None
        self._field.set_corners((not left, not right, not right, not left))


#: PrimeVue 的 InputIcon 与 IconField 常一起使用，这里提供同义名字
CInputIcon = CIconField

__all__ = ["CIconField", "CInputIcon"]
