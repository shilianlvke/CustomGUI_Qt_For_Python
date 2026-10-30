"""选择器族：Select / MultiSelect / AutoComplete / TreeSelect / Listbox。

全部为自绘控件，配色实时读 ``input_style.colors()``，切换主题无需重建。
选项弹层复用 ``overlay.CPopover`` + ``COptionList`` / ``CTreeList``。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QLineEdit, QSizePolicy, QVBoxLayout, QWidget

from .dropdown import CDropdownField
from .input_style import RADIUS, colors, rounded_path
from .input_text import CInputText
from .overlay import COptionList, CTreeList
from ..paint_utils import draw_cross

#: 标签高（md 下 26px）
_CHIP_GAP = 4


class _InlineEdit(QLineEdit):
    """浮在芯片区里的透明输入框（AutoComplete 用）。"""

    clicked = Signal()

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().mousePressEvent(event)
        self.clicked.emit()


class CSelect(CDropdownField):
    """单选下拉框。"""

    selectionChanged = Signal(object)

    def __init__(
        self,
        options=(),
        value=None,
        placeholder: str = "Select",
        size: str = "md",
        filter: bool = False,
        parent=None,
    ):
        super().__init__(placeholder, size, parent=parent)
        self._options = list(options)
        self._index = self._options.index(value) if value in self._options else -1
        self._filter = filter
        self._list: COptionList | None = None
        self._filter_input: CInputText | None = None

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def options(self) -> list[str]:
        return list(self._options)

    def value(self):
        return self._options[self._index] if 0 <= self._index < len(self._options) else None

    def set_options(self, options, keep_value: bool = False) -> None:
        current = self.value() if keep_value else None
        self._options = list(options)
        self._index = self._options.index(current) if current in self._options else -1
        self.update()

    def set_value(self, value, emit: bool = True) -> None:
        index = self._options.index(value) if value in self._options else -1
        if index == self._index:
            return
        self._index = index
        self.update()
        if emit:
            self.selectionChanged.emit(self.value())

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        self._paint_box(painter)
        text = self.value()
        painter.setPen(QColor(palette["text"] if text else palette["placeholder"]))
        metrics = QFontMetrics(self.font())
        rect = QRectF(self._text_left(), 0, self._content_right() - self._text_left(), self.height())
        painter.drawText(
            rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            metrics.elidedText(text or self._placeholder, Qt.ElideRight, int(rect.width())),
        )
        self._paint_chevron(painter)
        painter.end()

    # ------------------------------------------------------------------
    # 弹层
    # ------------------------------------------------------------------
    def _build_popup(self) -> QWidget | None:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._filter_input = None
        if self._filter:
            self._filter_input = CInputText(placeholder="Filter", size="sm", parent=holder)
            self._filter_input.textChanged.connect(self._apply_filter)
            layout.addWidget(self._filter_input)

        selected = (self._index,) if self._index >= 0 else ()
        self._list = COptionList(self._options, selected=selected, parent=holder)
        self._list.activated.connect(self._choose)
        layout.addWidget(self._list)
        if self._filter_input is not None:
            QTimer.singleShot(0, self._filter_input.setFocus)
        return holder

    def _apply_filter(self, text: str) -> None:
        if self._list is not None:
            self._list.set_filter(text)

    def _on_popup_closed(self) -> None:
        super()._on_popup_closed()
        self._list = None
        self._filter_input = None

    def _choose(self, index: int) -> None:
        self._index = index
        self.close_popup()
        self.update()
        self.selectionChanged.emit(self.value())


class _ChipsField(CDropdownField):
    """带标签芯片的下拉字段（MultiSelect / AutoComplete 共用）。"""

    selectionChanged = Signal(list)

    def __init__(
        self,
        options=(),
        values=(),
        placeholder: str = "",
        size: str = "md",
        filter: bool = True,
        multiple: bool = True,
        editable: bool = False,
        parent=None,
    ):
        super().__init__(placeholder, size, parent=parent)
        self._options = list(options)
        self._values = [value for value in values if value in self._options]
        self._filter = filter
        self._multiple = multiple
        self._editable = editable
        self._list: COptionList | None = None
        self._edit: _InlineEdit | None = None
        self._chip_boxes: list[tuple[QRectF, str]] = []
        self._overflow = 0

        if editable:
            self._edit = _InlineEdit(self)
            self._edit.setFont(self.font())
            self._edit.setFrame(False)
            self._edit.setStyleSheet("background: transparent; border: none;")
            self._edit.setPlaceholderText(placeholder)
            self._edit.textEdited.connect(self._on_text_edited)
            self._edit.returnPressed.connect(self._on_return)
            self._edit.clicked.connect(self._ensure_popup)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def values(self) -> list[str]:
        return list(self._values)

    def value(self):
        return self._values[0] if self._values else None

    def set_values(self, values, emit: bool = True) -> None:
        self._values = [value for value in values if value in self._options]
        self._sync_edit()
        self.update()
        if emit:
            self.selectionChanged.emit(list(self._values))

    # ------------------------------------------------------------------
    # 芯片布局
    # ------------------------------------------------------------------
    def _chip_height(self) -> float:
        return self.height() - 14

    def _layout_chips(self) -> float:
        """计算芯片矩形，返回芯片区右边界（供输入框定位）。"""
        self._chip_boxes = []
        self._overflow = 0
        if not self._values:
            return self._text_left()

        metrics = QFontMetrics(self.font())
        x = self._text_left()
        height = self._chip_height()
        top = (self.height() - height) / 2
        limit = self._content_right() - 4
        for value in self._values:
            width = metrics.horizontalAdvance(value) + 34
            if x + width > limit and self._chip_boxes:
                self._overflow = len(self._values) - len(self._chip_boxes)
                break
            self._chip_boxes.append((QRectF(x, top, width, height), value))
            x += width + _CHIP_GAP
        if self._overflow:
            x += 34 + _CHIP_GAP
        return x

    def _sync_edit(self) -> None:
        if self._edit is None:
            return
        self._edit.setPlaceholderText(self._placeholder if not self._values else "")
        self._edit.setVisible(True)

    def _position_edit(self) -> None:
        if self._edit is None:
            return
        end = self._layout_chips()
        width = max(50.0, self._content_right() - end - 2)
        self._edit.setGeometry(int(end), 4, int(width), self.height() - 8)

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._position_edit()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        self._paint_box(painter)
        self._layout_chips()
        metrics = QFontMetrics(self.font())

        accent = QColor(palette["focus_border"])
        chip_bg = QColor(accent)
        chip_bg.setAlpha(40)
        for rect, value in self._chip_boxes:
            painter.setBrush(chip_bg)
            painter.setPen(QPen(QColor(accent), 1))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(palette["text"]))
            painter.drawText(
                QRectF(rect.left() + 8, rect.top(), rect.width() - 26, rect.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                metrics.elidedText(value, Qt.ElideRight, int(rect.width()) - 28),
            )
            draw_cross(painter, QRectF(rect.right() - 18, rect.center().y() - 5, 10, 10), palette["placeholder"], 1.3)

        if self._overflow:
            last = self._chip_boxes[-1][0] if self._chip_boxes else QRectF(self._text_left(), 0, 0, 0)
            rect = QRectF(last.right() + _CHIP_GAP, last.top(), 34, last.height())
            painter.setBrush(chip_bg)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(palette["text"]))
            painter.drawText(rect, Qt.AlignCenter, f"+{self._overflow}")

        if not self._values and self._edit is None:
            painter.setPen(QColor(palette["placeholder"]))
            rect = QRectF(self._text_left(), 0, self._content_right() - self._text_left(), self.height())
            painter.drawText(
                rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                metrics.elidedText(self._placeholder, Qt.ElideRight, int(rect.width())),
            )

        self._paint_chevron(painter)
        painter.end()

    # ------------------------------------------------------------------
    # 弹层
    # ------------------------------------------------------------------
    def _build_popup(self) -> QWidget | None:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        selected = tuple(self._options.index(value) for value in self._values if value in self._options)
        self._list = COptionList(self._options, selected=selected, multi=self._multiple, parent=holder)
        self._list.activated.connect(self._choose)
        layout.addWidget(self._list)
        return holder

    def _on_popup_closed(self) -> None:
        super()._on_popup_closed()
        self._list = None

    def _ensure_popup(self) -> None:
        if not self._open:
            self._toggle_popup()

    def _on_text_edited(self, text: str) -> None:
        self._ensure_popup()
        if self._list is not None:
            self._list.set_filter(text)

    def _on_return(self) -> None:
        if self._list is not None and self._list.visible_count():
            self._choose(self._list.first_visible_index())
            return
        if self._edit is not None and not self._multiple and self._edit.text().strip():
            self._values = [self._edit.text().strip()]
            self.selectionChanged.emit(list(self._values))

    def _choose(self, index: int) -> None:
        if not 0 <= index < len(self._options):
            return
        option = self._options[index]
        if self._multiple:
            if option in self._values:
                self._values.remove(option)
            else:
                self._values.append(option)
                self._values.sort(key=self._options.index)
            if self._edit is not None:
                self._edit.clear()
                self._edit.setFocus()
            if self._list is not None:
                self._list.set_selected(self._options.index(value) for value in self._values)
            self._sync_edit()
            self._position_edit()
            self.update()
            self.selectionChanged.emit(list(self._values))
            return

        self._values = [option]
        if self._edit is not None:
            self._edit.setText(option)
        self.close_popup()
        self.update()
        self.selectionChanged.emit(list(self._values))

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _chip_close_at(self, position) -> str | None:
        for rect, value in self._chip_boxes:
            close = QRectF(rect.right() - 22, rect.top(), 20, rect.height())
            if close.contains(position):
                return value
        return None

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self.isEnabled():
            value = self._chip_close_at(event.position())
            if value is not None:
                self._values.remove(value)
                self._sync_edit()
                self._position_edit()
                self.update()
                if self._list is not None:
                    self._list.set_selected(self._options.index(item) for item in self._values)
                self.selectionChanged.emit(list(self._values))
                event.accept()
                return
            if self._edit is not None:
                self._edit.setFocus(Qt.MouseFocusReason)
            self.setFocus(Qt.MouseFocusReason)
            self._toggle_popup()
            event.accept()
            return
        super().mousePressEvent(event)


class CMultiSelect(_ChipsField):
    """多选下拉框（芯片展示已选值）。"""

    def __init__(
        self, options=(), values=(), placeholder: str = "Select", size: str = "md", filter: bool = True, parent=None
    ):
        super().__init__(
            options=options,
            values=values,
            placeholder=placeholder,
            size=size,
            filter=filter,
            multiple=True,
            editable=False,
            parent=parent,
        )


class CAutoComplete(_ChipsField):
    """可输入的下拉建议框（默认多选 + 芯片，对应 Sakai 的 AutoComplete）。"""

    def __init__(
        self,
        options=(),
        values=(),
        placeholder: str = "Search",
        size: str = "md",
        multiple: bool = True,
        parent=None,
    ):
        super().__init__(
            options=options,
            values=values,
            placeholder=placeholder,
            size=size,
            filter=True,
            multiple=multiple,
            editable=True,
            parent=parent,
        )


class CTreeSelect(CDropdownField):
    """树形下拉选择。"""

    selectionChanged = Signal(str)

    def __init__(self, nodes=(), value: str = "", placeholder: str = "Select Item", size: str = "md", parent=None):
        super().__init__(placeholder, size, parent=parent)
        self._nodes = list(nodes)
        self._value = value

    def value(self) -> str:
        return self._value

    def set_value(self, value: str, emit: bool = True) -> None:
        self._value = value or ""
        self.update()
        if emit:
            self.selectionChanged.emit(self._value)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        self._paint_box(painter)
        painter.setPen(QColor(palette["text"] if self._value else palette["placeholder"]))
        metrics = QFontMetrics(self.font())
        rect = QRectF(self._text_left(), 0, self._content_right() - self._text_left(), self.height())
        painter.drawText(
            rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            metrics.elidedText(self._value or self._placeholder, Qt.ElideRight, int(rect.width())),
        )
        self._paint_chevron(painter)
        painter.end()

    def _build_popup(self) -> QWidget | None:
        tree = CTreeList(self._nodes)
        tree.activated.connect(self._choose)
        return tree

    def _choose(self, label: str) -> None:
        self._value = label
        self.close_popup()
        self.update()
        self.selectionChanged.emit(label)


class CListbox(QWidget):
    """内联列表框（带过滤输入）。"""

    selectionChanged = Signal(object)

    def __init__(self, options=(), value=None, filter: bool = True, height: int = 200, parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._value = value if value in self._options else None
        self._filter = filter
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._filter_input: CInputText | None = None
        if filter:
            self._filter_input = CInputText(placeholder="Filter", size="sm", parent=self)
            self._filter_input.textChanged.connect(self._apply_filter)
            layout.addWidget(self._filter_input)

        selected = (self._options.index(self._value),) if self._value is not None else ()
        self._list = COptionList(self._options, selected=selected, parent=self)
        self._list.activated.connect(self._choose)
        layout.addWidget(self._list, 1)
        self._list.set_preferred_height(height - (52 if filter else 20))

    def value(self):
        return self._value

    def set_value(self, value, emit: bool = True) -> None:
        index = self._options.index(value) if value in self._options else -1
        if index < 0:
            return
        self._value = value
        self._list.set_selected((index,))
        if emit:
            self.selectionChanged.emit(value)

    def _apply_filter(self, text: str) -> None:
        self._list.set_filter(text)

    def _choose(self, index: int) -> None:
        self._value = self._options[index]
        self._list.set_selected((index,))
        self.selectionChanged.emit(self._value)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = colors()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(palette["background"]))
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(rounded_path(rect, RADIUS))
        painter.end()


__all__ = ["CSelect", "CMultiSelect", "CAutoComplete", "CTreeSelect", "CListbox"]
