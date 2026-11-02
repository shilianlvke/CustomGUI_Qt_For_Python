"""列表类数据视图（复刻 PrimeVue DataView / PickList / OrderList）。

实现要点：

- 三个组件都用**自绘**呈现列表内容，颜色在 ``paintEvent`` 中实时读取
  :func:`~..panels.style.panel_colors`，主题切换后重绘即生效，不缓存色值；
- :class:`CDataView` 用 ``QScrollArea`` 承载条目，模板部件由调用方提供，
  外层统一包一层可点击卡片，点击时回传原始行数据；
- :class:`CPickList` / :class:`COrderList` 的列表项由 ``QStyledItemDelegate``
  绘制成圆角条目，中间的移动按钮复用 :class:`CButton`，几何与圆角和现有
  组件保持一致。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from customgui.appcore import get_theme_manager

from ..button import CButton
from ..panels.style import RADIUS, paint_surface, panel_colors, rounded_path
from ..scroll import CScrollArea

#: 单个列表条目的高度（与表格行高一致）
_ITEM_HEIGHT = 34
#: 条目内文字左右留白
_ITEM_PADDING = 10


def _payload_label(item: Any) -> str:
    """把 ``str`` / ``dict`` 数据转成列表里显示的文字。"""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("label", "name", "text", "title"):
            value = item.get(key)
            if value is not None:
                return str(value)
        for value in item.values():
            if value is not None:
                return str(value)
        return ""
    return str(item)


def _selected_index(widget: QListWidget, indexes: Iterable[int] | None) -> list[int]:
    """取本次操作的行号；``indexes`` 为空时使用列表当前选择。"""
    if indexes is not None:
        selected = {int(index) for index in indexes}
    else:
        selected = {index.row() for index in widget.selectedIndexes()}
    return sorted(index for index in selected if 0 <= index < widget.count())


def _wrap_in_shell(widget: QWidget, parent: QWidget | None = None) -> QFrame:
    """把列表包进带圆角描边的外壳（对外保持组件的简洁 API）。"""
    shell = _ListShell(parent)
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(3, 3, 3, 3)
    layout.setSpacing(0)
    layout.addWidget(widget)
    return shell


class _ItemDelegate(QStyledItemDelegate):
    """列表条目绘制：圆角底、选中态强调色、悬停底色。"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 2, -4, -2)
        if selected:
            background = QColor(colors["accent"])
            text_color = QColor(colors["on_accent"])
        elif hovered:
            background = QColor(colors["hover"])
            text_color = QColor(colors["text"])
        else:
            background = None
            text_color = QColor(colors["text"])
        if background is not None:
            painter.fillPath(rounded_path(rect, 6), background)

        metrics = QFontMetrics(option.font)
        text = str(index.data(Qt.DisplayRole) or "")
        text = metrics.elidedText(text, Qt.ElideRight, max(0, int(rect.width()) - _ITEM_PADDING * 2))
        painter.setPen(text_color)
        painter.drawText(
            rect.adjusted(_ITEM_PADDING, 0, -_ITEM_PADDING, 0),
            Qt.AlignLeft | Qt.AlignVCenter,
            text,
        )
        painter.restore()

    def sizeHint(self, option, index):  # noqa: N802 - 覆写 Qt 命名
        return QSize(160, _ITEM_HEIGHT)


class _TokenList(QListWidget):
    """透明底、多选的列表部件（配色交给外层外壳与委托）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._payloads: list[Any] = []
        self.setObjectName("CDataView_List")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        self.setItemDelegate(_ItemDelegate(self))
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QListWidget { background: transparent; border: none; }")

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def set_payloads(self, payloads: Iterable[Any]) -> None:
        """整体替换列表数据（保留原始对象，供上层读取）。"""
        self._payloads = list(payloads)
        self.clear()
        for payload in self._payloads:
            entry = QListWidgetItem(_payload_label(payload))
            entry.setData(Qt.UserRole, payload)
            entry.setSizeHint(QSize(0, _ITEM_HEIGHT))
            self.addItem(entry)

    def payloads(self) -> list[Any]:
        return list(self._payloads)

    def selected_indexes(self) -> list[int]:
        return sorted({index.row() for index in self.selectedIndexes()})

    def restore_selection(self, indexes: Iterable[int]) -> None:
        """重新选中指定行（数据刷新后恢复选中状态）。"""
        for index in indexes:
            entry = self.item(int(index))
            if entry is not None:
                entry.setSelected(True)

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self.viewport().update()


class _ListShell(QFrame):
    """带圆角底色与描边的列表外壳（颜色实时取自面板配色）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_surface(painter, rect, RADIUS, border=panel_colors()["border"])
        painter.end()

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self.update()


class _EmptyText(QLabel):
    """空态提示：文字色随主题变化，居中显示。"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(120)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setPen(QColor(panel_colors()["muted"]))
        painter.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, self.text())
        painter.end()


class _DataViewItem(QFrame):
    """DataView 条目卡片：圆角底 + 悬停底色，点击回传原始行数据。"""

    clicked = Signal(object)

    def __init__(self, record: dict, template: QWidget, parent=None):
        super().__init__(parent)
        self._record = record
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(56)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(template)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_surface(
            painter,
            rect,
            RADIUS,
            background=colors["hover"] if self._hovered else colors["background"],
            border=colors["border"],
        )
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._record)
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self.update()


class CDataView(QWidget):
    """数据视图（列表 / 网格两种排布）。

    ``item_template`` 负责把一行 ``dict`` 转成条目部件；视图在外层套一张可点击
    卡片，点击条目时发出 :attr:`itemClicked`，带上原始行数据。
    """

    itemClicked = Signal(object)

    def __init__(
        self,
        rows: list[dict] | None = None,
        item_template: Callable[[dict], QWidget] | None = None,
        layout: str = "list",
        columns: int = 2,
        empty_text: str = "No records found",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CDataView_Widget")
        self._rows = list(rows or [])
        self._item_template = item_template
        self._layout_mode = "grid" if layout == "grid" else "list"
        self._columns = max(1, int(columns))
        self._empty_text = empty_text
        self._items: list[_DataViewItem] = []
        self._content: QWidget | None = None
        self._setup_ui()
        self._rebuild()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._header = QWidget(self)
        self._header_layout = QHBoxLayout(self._header)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(8)
        layout.addWidget(self._header)

        self._scroll = CScrollArea(self)
        self._scroll.setObjectName("CDataView_Scroll")
        self._scroll.setWidgetResizable(True)
        layout.addWidget(self._scroll, 1)

    def add_header_widget(self, widget: QWidget) -> None:
        """向顶部 header 插槽追加部件（搜索框、排序下拉等）。"""
        self._header_layout.addWidget(widget)

    # ------------------------------------------------------------------
    # 数据 / 布局
    # ------------------------------------------------------------------
    def rows(self) -> list[dict]:
        return list(self._rows)

    def set_rows(self, rows: list[dict]) -> None:
        """整体替换行数据并重建条目。"""
        self._rows = list(rows)
        self._rebuild()

    def layout_mode(self) -> str:
        return self._layout_mode

    def set_layout(self, layout: str) -> None:
        """切换 ``list`` / ``grid`` 排布（非法值回落到列表）。"""
        mode = "grid" if layout == "grid" else "list"
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        self._rebuild()

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self._rebuild()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _rebuild(self) -> None:
        old = self._scroll.takeWidget()
        if old is not None:
            old.deleteLater()

        content = QWidget()
        self._items = []
        if self._layout_mode == "grid":
            layout: QVBoxLayout | QGridLayout = QGridLayout(content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            for column in range(self._columns):
                layout.setColumnStretch(column, 1)
        else:
            layout = QVBoxLayout(content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

        if not self._rows:
            empty = _EmptyText(self._empty_text, content)
            if isinstance(layout, QGridLayout):
                layout.addWidget(empty, 0, 0, 1, self._columns)
            else:
                layout.addWidget(empty)
                layout.addStretch(1)
        else:
            for index, record in enumerate(self._rows):
                item = self._build_item(record, content)
                self._items.append(item)
                if isinstance(layout, QGridLayout):
                    layout.addWidget(item, index // self._columns, index % self._columns)
                else:
                    layout.addWidget(item)
            if isinstance(layout, QGridLayout):
                rows = (len(self._rows) + self._columns - 1) // self._columns
                layout.setRowStretch(rows, 1)
            else:
                layout.addStretch(1)

        self._content = content
        self._scroll.setWidget(content)

    def _build_item(self, record: dict, parent: QWidget) -> _DataViewItem:
        template = self._item_template(record) if self._item_template is not None else QLabel(str(record))
        item = _DataViewItem(record, template, parent)
        item.clicked.connect(self.itemClicked.emit)
        return item

    def _theme_changed(self) -> None:
        """主题切换后重绘条目与空态（颜色在 paintEvent 中实时读取）。"""
        self.update()
        for item in self._items:
            item.update()
        if self._content is not None:
            self._content.update()

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(560, 360)


class CPickList(QWidget):
    """双列表穿梭框（源列表 ↔ 目标列表）。

    两个列表的数据既可以是 ``str``，也可以是 ``dict``（显示时优先取
    ``label`` / ``name`` / ``text`` / ``title``）。移动操作发出 ``changed``
    信号，携带源、目标两份列表的浅拷贝。
    """

    changed = Signal(list, list)

    def __init__(self, source=None, target=None, parent=None):
        super().__init__(parent)
        self.setObjectName("CPickList_Widget")
        self._source = list(source or [])
        self._target = list(target or [])
        self._setup_ui()
        self._refresh()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._source_list = _TokenList(self)
        self._target_list = _TokenList(self)
        self._source_shell = _wrap_in_shell(self._source_list, self)
        self._target_shell = _wrap_in_shell(self._target_list, self)
        layout.addWidget(self._source_shell, 1)
        layout.addLayout(self._build_controls())
        layout.addWidget(self._target_shell, 1)

    def _build_controls(self) -> QVBoxLayout:
        controls = QVBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        controls.addStretch(1)
        self._to_target = self._move_button("icon_arrow_right", "Move to target")
        self._all_to_target = self._move_button("", "Move all to target", text="»")
        self._all_to_source = self._move_button("", "Move all to source", text="«")
        self._to_source = self._move_button("icon_arrow_left", "Move to source")
        self._to_target.clicked.connect(lambda: self.move_to_target())
        self._all_to_target.clicked.connect(self.move_all_to_target)
        self._all_to_source.clicked.connect(self.move_all_to_source)
        self._to_source.clicked.connect(lambda: self.move_to_source())
        for button in (self._to_target, self._all_to_target, self._all_to_source, self._to_source):
            controls.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        controls.addStretch(1)
        return controls

    def _move_button(self, icon: str, tooltip: str, text: str = "") -> CButton:
        button = CButton(
            text,
            icon=icon or None,
            size="sm",
            variant="text",
            severity="secondary",
            fixed_width=34,
            parent=self,
        )
        button.setToolTip(tooltip)
        return button

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def values(self) -> tuple[list, list]:
        return list(self._source), list(self._target)

    def set_values(self, values: tuple[list, list], emit: bool = True) -> None:
        """整体设置 (源列表, 目标列表)，默认发出 ``changed``。"""
        source, target = values
        self._source = list(source)
        self._target = list(target)
        self._refresh()
        if emit:
            self._emit_changed()

    def _refresh(self) -> None:
        self._source_list.set_payloads(self._source)
        self._target_list.set_payloads(self._target)

    def _emit_changed(self) -> None:
        self.changed.emit(list(self._source), list(self._target))

    def _theme_changed(self) -> None:
        """主题切换后重绘外壳与两个列表。"""
        for widget in (self, self._source_shell, self._target_shell, self._source_list, self._target_list):
            widget.update()
        self._source_list.viewport().update()
        self._target_list.viewport().update()

    # ------------------------------------------------------------------
    # 移动
    # ------------------------------------------------------------------
    def move_to_target(self, indexes: Iterable[int] | None = None) -> None:
        """把源列表中选中的行（或指定行）移到目标列表末尾。"""
        selected = _selected_index(self._source_list, indexes)
        if not selected:
            return
        moving = [self._source[index] for index in selected]
        self._source = [item for index, item in enumerate(self._source) if index not in set(selected)]
        self._target.extend(moving)
        self._refresh()
        self._emit_changed()

    def move_to_source(self, indexes: Iterable[int] | None = None) -> None:
        """把目标列表中选中的行（或指定行）移到源列表末尾。"""
        selected = _selected_index(self._target_list, indexes)
        if not selected:
            return
        moving = [self._target[index] for index in selected]
        self._target = [item for index, item in enumerate(self._target) if index not in set(selected)]
        self._source.extend(moving)
        self._refresh()
        self._emit_changed()

    def move_all_to_target(self) -> None:
        """全选移动：源列表全部数据移到目标列表。"""
        if not self._source:
            return
        self._target.extend(self._source)
        self._source = []
        self._refresh()
        self._emit_changed()

    def move_all_to_source(self) -> None:
        """全选移动：目标列表全部数据移回源列表。"""
        if not self._target:
            return
        self._source.extend(self._target)
        self._target = []
        self._refresh()
        self._emit_changed()


class COrderList(QWidget):
    """单列表排序框：上移 / 下移 / 删除。

    数据可以是 ``str`` 或 ``dict``；排序与删除都发出 ``changed`` 信号，
    携带当前列表的浅拷贝。
    """

    changed = Signal(list)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self.setObjectName("COrderList_Widget")
        self._items = list(items or [])
        self._setup_ui()
        self._refresh()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._list = _TokenList(self)
        self._shell = _wrap_in_shell(self._list, self)
        layout.addWidget(self._shell, 1)

        controls = QVBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        controls.addStretch(1)
        self._up = self._action_button("icon_arrow_up", "Move up")
        self._down = self._action_button("icon_arrow_down", "Move down")
        self._remove = self._action_button("icon_trash", "Remove selected", severity="danger")
        self._up.clicked.connect(lambda: self.move_up())
        self._down.clicked.connect(lambda: self.move_down())
        self._remove.clicked.connect(lambda: self.remove_selected())
        for button in (self._up, self._down, self._remove):
            controls.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        controls.addStretch(1)
        layout.addLayout(controls)

    def _action_button(self, icon: str, tooltip: str, severity: str = "secondary") -> CButton:
        button = CButton(
            "",
            icon=icon,
            size="sm",
            variant="text",
            severity=severity,
            fixed_width=34,
            parent=self,
        )
        button.setToolTip(tooltip)
        return button

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def items(self) -> list:
        return list(self._items)

    def set_items(self, items, emit: bool = True) -> None:
        """整体替换数据，默认发出 ``changed``。"""
        self._items = list(items)
        self._refresh()
        if emit:
            self._emit_changed()

    def _refresh(self) -> None:
        self._list.set_payloads(self._items)

    def _emit_changed(self) -> None:
        self.changed.emit(list(self._items))

    def _theme_changed(self) -> None:
        """主题切换后重绘外壳与列表。"""
        for widget in (self, self._shell, self._list):
            widget.update()
        self._list.viewport().update()

    # ------------------------------------------------------------------
    # 排序 / 删除
    # ------------------------------------------------------------------
    def move_up(self, indexes: Iterable[int] | None = None) -> None:
        """把选中行（或指定行）整体上移一格。"""
        selected = _selected_index(self._list, indexes)
        if not selected:
            return
        kept = set(selected)
        changed = False
        for index in range(len(self._items)):
            if index in kept and index > 0 and index - 1 not in kept:
                self._items[index - 1], self._items[index] = self._items[index], self._items[index - 1]
                kept.remove(index)
                kept.add(index - 1)
                changed = True
        if not changed:
            return
        self._refresh()
        self._list.restore_selection(kept)
        self._emit_changed()

    def move_down(self, indexes: Iterable[int] | None = None) -> None:
        """把选中行（或指定行）整体下移一格。"""
        selected = _selected_index(self._list, indexes)
        if not selected:
            return
        kept = set(selected)
        changed = False
        for index in range(len(self._items) - 1, -1, -1):
            if index in kept and index + 1 < len(self._items) and index + 1 not in kept:
                self._items[index], self._items[index + 1] = self._items[index + 1], self._items[index]
                kept.remove(index)
                kept.add(index + 1)
                changed = True
        if not changed:
            return
        self._refresh()
        self._list.restore_selection(kept)
        self._emit_changed()

    def remove_selected(self, indexes: Iterable[int] | None = None) -> None:
        """删除选中行（或指定行）。"""
        selected = _selected_index(self._list, indexes)
        if not selected:
            return
        removed = set(selected)
        self._items = [item for index, item in enumerate(self._items) if index not in removed]
        self._refresh()
        self._emit_changed()


__all__ = ["CDataView", "CPickList", "COrderList"]
