"""树形表格 ``CTreeTable``：``QTreeView + QStandardItemModel``，列复用 ``CTableColumn``。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QItemSelectionModel, QModelIndex, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ...display.palette import tokens
from ...panels.style import panel_colors, qss_color
from ..table import CTableColumn
from .delegate import _TreeTableDelegate
from .paint import _alignment, _check_state, _node_key, _row_metrics
from .roles import KEY_ROLE, NODE_ROLE


class _TreeTableView(QTreeView):
    """内部树形表格视图：拦截第一列的箭头 / 复选框点击。"""

    def __init__(self, owner: CTreeTable, parent=None):
        super().__init__(parent)
        self._owner = owner
        self.setObjectName("CTreeTable_View")

    def mousePressEvent(self, event):  # noqa: N802
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        if index.isValid() and index.column() == 0:
            arrow, box, _icon_x, _text_x = _row_metrics(
                QRectF(self.visualRect(index)), index, self._owner._checkbox
            )
            if arrow is not None and arrow.contains(QPointF(pos)):
                self.setExpanded(index, not self.isExpanded(index))
                return
            if box is not None and box.contains(QPointF(pos)):
                item = self._owner._model.itemFromIndex(index)
                if item is not None:
                    self._owner._toggle_checked_item(item)
                return
        super().mousePressEvent(event)


class CTreeTable(QWidget):
    """树形表格：带 ``children`` 的 ``list[dict]`` + :class:`CTableColumn` 列定义。

    Args:
        columns: 列定义（复用 :class:`~..table.CTableColumn`）。
        rows: ``list[dict]``，节点可带 ``children/checked/expanded/disabled``。
        checkbox: 是否在第一列显示复选框。
        selection_mode: 非复选模式下的 ``"single"`` / ``"multiple"``。

    Signals:
        selectionChanged(list): 复选模式下为勾选节点；否则为选中行记录。
    """

    selectionChanged = Signal(list)

    def __init__(
        self,
        columns: list[CTableColumn] | None = None,
        rows: list[dict] | None = None,
        checkbox: bool = True,
        selection_mode: str = "single",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CTreeTable_Widget")
        self._columns = list(columns or [])
        self._rows = list(rows or [])
        self._checkbox = bool(checkbox)
        self._selection_mode = selection_mode if selection_mode in ("single", "multiple") else "single"
        self._theme_signature: tuple | None = None
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = _TreeTableView(self, self)
        layout.addWidget(self._view)
        self._configure_view()

        self._model = QStandardItemModel(self._view)
        self._view.setModel(self._model)
        self._delegate = _TreeTableDelegate(self._columns, self._checkbox, self._view)
        self._view.setItemDelegate(self._delegate)

        self._rebuild()
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._model.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # 数据 / 列
    # ------------------------------------------------------------------
    def columns(self) -> list[CTableColumn]:
        return list(self._columns)

    def set_columns(self, columns: list[CTableColumn]) -> None:
        self._columns = list(columns)
        self._delegate._columns = self._columns
        self._rebuild()

    def rows(self) -> list[dict]:
        return list(self._rows)

    def set_rows(self, rows: list[dict]) -> None:
        self._rows = list(rows)
        self._rebuild()

    def view(self) -> QTreeView:
        return self._view

    # ------------------------------------------------------------------
    # 选择
    # ------------------------------------------------------------------
    def selection_keys(self) -> list:
        """复选模式返回勾选键，否则返回选中行的键。"""
        if self._checkbox:
            return self.checked_keys()
        indexes = self._view.selectionModel().selectedRows(0)
        return [index.data(KEY_ROLE) for index in indexes]

    def set_selection_keys(self, keys: list) -> None:
        """按节点键设置勾选（复选）或选中（单选 / 多选）。"""
        wanted = set(keys)
        if self._checkbox:
            self._updating = True
            try:
                for item in self._all_items():
                    if item.isCheckable():
                        item.setCheckState(Qt.CheckState.Unchecked)
                for item in self._all_items():
                    if item.data(KEY_ROLE) in wanted:
                        self._set_subtree_check(item, Qt.CheckState.Checked)
                self._recompute_parent_states()
            finally:
                self._updating = False
            self._view.viewport().update()
        else:
            selection = self._view.selectionModel()
            selection.blockSignals(True)
            try:
                selection.clearSelection()
                flags = (
                    QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QItemSelectionModel.SelectionFlag.Rows
                )
                current = QModelIndex()
                for item in self._all_items():
                    if item.data(KEY_ROLE) in wanted and item.isEnabled():
                        selection.select(item.index(), flags)
                        current = item.index()
                if current.isValid():
                    self._view.setCurrentIndex(current)
            finally:
                selection.blockSignals(False)
            self._view.viewport().update()
        self._emit_selection()

    def set_checked_keys(self, keys: list) -> None:
        """按节点键设置复选框状态（等价于 :meth:`set_selection_keys`）。"""
        self.set_selection_keys(keys)

    def checked_keys(self) -> list:
        """所有完全勾选节点的键（按树顺序）。"""
        return [
            item.data(KEY_ROLE)
            for item in self._all_items()
            if _check_state(item.checkState()) == Qt.CheckState.Checked
        ]

    def checked_records(self) -> list[dict]:
        """所有完全勾选节点的原始记录。"""
        return [
            item.data(NODE_ROLE)
            for item in self._all_items()
            if _check_state(item.checkState()) == Qt.CheckState.Checked
            and isinstance(item.data(NODE_ROLE), dict)
        ]

    def selected_records(self) -> list[dict]:
        """当前选中行的原始记录（非复选模式）。"""
        records = []
        for index in self._view.selectionModel().selectedRows(0):
            node = index.data(NODE_ROLE)
            if isinstance(node, dict):
                records.append(node)
        return records

    # ------------------------------------------------------------------
    # 展开 / 收起
    # ------------------------------------------------------------------
    def expand_all(self) -> None:
        """展开全部节点。"""
        self._view.expandAll()

    def collapse_all(self) -> None:
        """收起全部节点。"""
        self._view.collapseAll()

    # ------------------------------------------------------------------
    # 主题 / 几何
    # ------------------------------------------------------------------
    def update(self, *args):  # noqa: N802
        self._apply_theme()
        super().update()
        view = getattr(self, "_view", None)
        if view is not None:
            view.viewport().update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(720, 420)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(280, 160)

    # ------------------------------------------------------------------
    # 内部：构建
    # ------------------------------------------------------------------
    def _configure_view(self) -> None:
        view = self._view
        view.setRootIsDecorated(False)
        view.setIndentation(0)
        view.setUniformRowHeights(True)
        view.setAllColumnsShowFocus(True)
        view.setMouseTracking(True)
        view.setAlternatingRowColors(False)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        if self._checkbox:
            view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        elif self._selection_mode == "multiple":
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        header = view.header()
        header.setStretchLastSection(True)
        header.setTextElideMode(Qt.ElideRight)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionsClickable(False)

    def _rebuild(self) -> None:
        self._updating = True
        try:
            self._model.clear()
            self._model.setHorizontalHeaderLabels(
                [column.header or column.field for column in self._columns]
            )
            root = self._model.invisibleRootItem()
            for node in self._rows:
                if isinstance(node, dict):
                    self._append_node(root, node)
        finally:
            self._updating = False
        self._configure_columns()
        self._apply_theme()
        self._view.viewport().update()

    def _append_node(self, parent: QStandardItem, node: dict) -> None:
        if not self._columns:
            return
        items: list[QStandardItem] = []
        for column in self._columns:
            item = QStandardItem()
            value = node.get(column.field)
            item.setText(column.text(value, node))
            item.setTextAlignment(_alignment(column.align))
            item.setEditable(False)
            item.setData(node, NODE_ROLE)
            items.append(item)

        first = items[0]
        first.setData(_node_key(node), KEY_ROLE)
        if self._checkbox:
            first.setCheckable(True)
            first.setCheckState(
                Qt.CheckState.Checked if node.get("checked") else Qt.CheckState.Unchecked
            )
        if node.get("disabled"):
            for item in items:
                item.setEnabled(False)
        parent.appendRow(items)
        for child in node.get("children") or []:
            if isinstance(child, dict):
                self._append_node(first, child)
        if node.get("expanded"):
            self._view.setExpanded(first.index(), True)

    def _configure_columns(self) -> None:
        header = self._view.header()
        for index, column in enumerate(self._columns):
            header.setMinimumSectionSize(column.min_width)
            if column.width is not None:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                self._view.setColumnWidth(index, column.width)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)

    # ------------------------------------------------------------------
    # 内部：复选与信号
    # ------------------------------------------------------------------
    def _all_items(self):
        root = self._model.invisibleRootItem()
        stack = [root.child(row, 0) for row in reversed(range(root.rowCount()))]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            yield item
            stack.extend(item.child(row, 0) for row in reversed(range(item.rowCount())))

    def _set_subtree_check(self, item: QStandardItem, state: Qt.CheckState) -> None:
        if item.isCheckable():
            item.setCheckState(state)
        for row in range(item.rowCount()):
            child = item.child(row, 0)
            if child is not None:
                self._set_subtree_check(child, state)

    def _refresh_ancestors(self, item: QStandardItem) -> None:
        parent = item.parent()
        while parent is not None:
            states = [
                _check_state(parent.child(row, 0).checkState()) for row in range(parent.rowCount())
            ]
            if all(state == Qt.CheckState.Checked for state in states):
                state = Qt.CheckState.Checked
            elif all(state == Qt.CheckState.Unchecked for state in states):
                state = Qt.CheckState.Unchecked
            else:
                state = Qt.CheckState.PartiallyChecked
            parent.setCheckState(state)
            parent = parent.parent()

    def _recompute_parent_states(self) -> None:
        root = self._model.invisibleRootItem()

        def walk(parent: QStandardItem) -> None:
            for row in range(parent.rowCount()):
                child = parent.child(row, 0)
                if child is None:
                    continue
                walk(child)
                if child.rowCount() == 0:
                    continue
                states = [
                    _check_state(child.child(index, 0).checkState())
                    for index in range(child.rowCount())
                ]
                if all(state == Qt.CheckState.Checked for state in states):
                    state = Qt.CheckState.Checked
                elif all(state == Qt.CheckState.Unchecked for state in states):
                    state = Qt.CheckState.Unchecked
                else:
                    state = Qt.CheckState.PartiallyChecked
                child.setCheckState(state)

        walk(root)

    def _toggle_checked_item(self, item: QStandardItem) -> None:
        if not self._checkbox or not item.isCheckable() or not item.isEnabled():
            return
        target = (
            Qt.CheckState.Unchecked
            if _check_state(item.checkState()) == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._updating = True
        try:
            self._set_subtree_check(item, target)
            self._refresh_ancestors(item)
        finally:
            self._updating = False
        self._view.viewport().update()
        self._emit_selection()

    def _emit_selection(self) -> None:
        records = self.checked_records() if self._checkbox else self.selected_records()
        self.selectionChanged.emit(records)

    def _on_selection_changed(self, *_args) -> None:
        if not self._checkbox:
            self._emit_selection()

    def _on_item_changed(self, _item: QStandardItem) -> None:
        if not self._updating and self._checkbox:
            self._emit_selection()

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._theme_signature = None
            self._apply_theme()

    def _apply_theme(self) -> None:
        view = getattr(self, "_view", None)
        if view is None:
            return
        colors = panel_colors()
        base = tokens()
        signature = (tuple(sorted(colors.items())), tuple(sorted(base.items())))
        if signature == self._theme_signature:
            return
        self._theme_signature = signature
        view.setStyleSheet(
            f"""
            QTreeView#CTreeTable_View {{
                background-color: {qss_color(colors["background"])};
                border: 1px solid {qss_color(colors["border"])};
                border-radius: 6px;
                outline: 0;
                alternate-background-color: {qss_color(colors["hover"])};
            }}
            QTreeView#CTreeTable_View::item {{
                border: none;
            }}
            QTreeView#CTreeTable_View QHeaderView {{
                background-color: {qss_color(colors["header_solid"])};
            }}
            QTreeView#CTreeTable_View QHeaderView::section {{
                background-color: {qss_color(colors["header_solid"])};
                color: {colors["text"]};
                border: none;
                border-bottom: 1px solid {qss_color(colors["border"])};
                padding: 6px 10px;
                font-weight: 600;
            }}
            """
        )


__all__ = ["CTreeTable"]
