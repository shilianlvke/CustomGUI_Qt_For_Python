"""通用树 ``CTree``：惰性展开、单选 / 多选 / 复选，行外观完全自绘。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QItemSelectionModel, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...display.palette import tokens
from ...panels.style import panel_colors
from .delegate import _CTreeDelegate
from .paint import _check_state, _node_key, _node_label, _row_metrics
from .roles import KEY_ROLE, NODE_ROLE


class _CTreeWidget(QTreeWidget):
    """内部树视图：拦截箭头 / 复选框点击，其余交给 Qt。"""

    def __init__(self, owner: CTree, checkbox: bool, parent=None):
        super().__init__(parent)
        self._owner = owner
        self._checkbox = checkbox

    def mousePressEvent(self, event):  # noqa: N802
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        if index.isValid() and index.column() == 0:
            arrow, box, _icon_x, _text_x = _row_metrics(QRectF(self.visualRect(index)), index, self._checkbox)
            if arrow is not None and arrow.contains(QPointF(pos)):
                item = self.itemFromIndex(index)
                if item is not None:
                    item.setExpanded(not item.isExpanded())
                return
            if box is not None and box.contains(QPointF(pos)):
                item = self.itemFromIndex(index)
                if item is not None:
                    self._owner._toggle_check(item)
                    self._owner._on_item_clicked(item, 0)
                return
        super().mousePressEvent(event)


class CTree(QWidget):
    """通用树组件：展开 / 收起、单选 / 多选 / 复选。

    Args:
        nodes: ``list[dict]``，节点字段 ``label/key/icon/children/disabled``。
        selection_mode: ``"single"`` / ``"multiple"`` / ``"checkbox"``。

    Signals:
        selectionChanged(list): 选中键列表（复选模式下为完全勾选的键）。
        itemClicked(dict): 点击节点时发出该节点原始 ``dict``。
    """

    selectionChanged = Signal(list)
    itemClicked = Signal(dict)

    def __init__(
        self,
        nodes: list[dict] | None = None,
        selection_mode: str = "single",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CTree_Widget")
        self._nodes: list[dict] = list(nodes or [])
        self._selection_mode = (
            selection_mode if selection_mode in ("single", "multiple", "checkbox") else "single"
        )
        self._theme_signature: tuple | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tree = _CTreeWidget(self, self._selection_mode == "checkbox", self)
        self._tree.setObjectName("CTree_TreeWidget")
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(0)
        self._tree.setUniformRowHeights(True)
        self._tree.setAllColumnsShowFocus(True)
        self._tree.setMouseTracking(True)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.setSelectionMode(self._view_selection_mode())
        self._tree.setItemDelegate(_CTreeDelegate(self._selection_mode == "checkbox", self._tree))
        layout.addWidget(self._tree)

        self._rebuild()
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._apply_theme()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def nodes(self) -> list[dict]:
        return list(self._nodes)

    def set_nodes(self, nodes: list[dict]) -> None:
        self._nodes = list(nodes)
        self._rebuild()

    def tree(self) -> QTreeWidget:
        return self._tree

    # ------------------------------------------------------------------
    # 选择
    # ------------------------------------------------------------------
    def selection_keys(self) -> list:
        """当前选中 / 勾选的节点键（按树顺序）。"""
        if self._selection_mode == "checkbox":
            return [
                item.data(0, KEY_ROLE)
                for item in self._iter_items()
                if _check_state(item.checkState(0)) == Qt.Checked
            ]
        return [index.data(KEY_ROLE) for index in self._tree.selectionModel().selectedRows(0)]

    def set_selection_keys(self, keys: list) -> None:
        """按节点键设置选择状态（复选模式会向下级联并回填父节点）。"""
        wanted = set(keys)
        self._tree.blockSignals(True)
        try:
            if self._selection_mode == "checkbox":
                for item in self._iter_items():
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                for item in self._iter_items():
                    if item.data(0, KEY_ROLE) in wanted:
                        self._set_check_down(item, Qt.CheckState.Checked)
                for row in range(self._tree.topLevelItemCount()):
                    self._refresh_parent_states(self._tree.topLevelItem(row))
            else:
                selection = self._tree.selectionModel()
                selection.blockSignals(True)
                try:
                    selection.clearSelection()
                    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
                    for item in self._iter_items():
                        if item.data(0, KEY_ROLE) in wanted and item.flags() & Qt.ItemIsEnabled:
                            selection.select(self._tree.indexFromItem(item), flags)
                finally:
                    selection.blockSignals(False)
                self._tree.viewport().update()
        finally:
            self._tree.blockSignals(False)
        self._emit_selection()

    # ------------------------------------------------------------------
    # 展开 / 收起
    # ------------------------------------------------------------------
    def expand_all(self) -> None:
        """展开全部节点。"""
        self._tree.expandAll()

    def collapse_all(self) -> None:
        """收起全部节点。"""
        self._tree.collapseAll()

    # ------------------------------------------------------------------
    # 主题与几何
    # ------------------------------------------------------------------
    def update(self, *args):  # noqa: N802
        self._apply_theme()
        super().update()
        tree = getattr(self, "_tree", None)
        if tree is not None:
            tree.viewport().update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(360, 320)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 120)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _view_selection_mode(self) -> QAbstractItemView.SelectionMode:
        if self._selection_mode == "checkbox":
            return QAbstractItemView.SelectionMode.NoSelection
        if self._selection_mode == "multiple":
            return QAbstractItemView.SelectionMode.ExtendedSelection
        return QAbstractItemView.SelectionMode.SingleSelection

    def _rebuild(self) -> None:
        self._tree.blockSignals(True)
        try:
            self._tree.clear()
            for node in self._nodes:
                if isinstance(node, dict):
                    item = self._build_item(node)
                    self._tree.addTopLevelItem(item)
                    self._apply_expanded(item, node)
        finally:
            self._tree.blockSignals(False)

    def _build_item(self, node: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.DisplayRole, _node_label(node))
        item.setData(0, NODE_ROLE, node)
        item.setData(0, KEY_ROLE, _node_key(node))
        disabled = bool(node.get("disabled"))
        flags = Qt.NoItemFlags if disabled else Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._selection_mode == "checkbox" and not disabled:
            flags |= Qt.ItemIsUserCheckable
        item.setFlags(flags)
        if self._selection_mode == "checkbox":
            item.setCheckState(
                0,
                Qt.CheckState.Checked if node.get("checked") else Qt.CheckState.Unchecked,
            )
        for child in node.get("children") or []:
            if isinstance(child, dict):
                item.addChild(self._build_item(child))
        return item

    def _apply_expanded(self, item: QTreeWidgetItem, node: dict) -> None:
        if node.get("expanded"):
            item.setExpanded(True)
        children = [child for child in node.get("children") or [] if isinstance(child, dict)]
        for index, child in enumerate(children):
            if index < item.childCount():
                self._apply_expanded(item.child(index), child)

    def _iter_items(self):
        stack = [
            self._tree.topLevelItem(row)
            for row in reversed(range(self._tree.topLevelItemCount()))
        ]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            yield item
            stack.extend(item.child(index) for index in reversed(range(item.childCount())))

    def _set_check_down(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        item.setCheckState(0, state)
        for index in range(item.childCount()):
            self._set_check_down(item.child(index), state)

    def _refresh_parent_states(self, item: QTreeWidgetItem) -> None:
        for index in range(item.childCount()):
            self._refresh_parent_states(item.child(index))
        if item.childCount() == 0:
            return
        states = [_check_state(item.child(index).checkState(0)) for index in range(item.childCount())]
        if all(state == Qt.CheckState.Checked for state in states):
            state = Qt.CheckState.Checked
        elif all(state == Qt.CheckState.Unchecked for state in states):
            state = Qt.CheckState.Unchecked
        else:
            state = Qt.CheckState.PartiallyChecked
        item.setCheckState(0, state)

    def _refresh_ancestors(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()
        while parent is not None:
            states = [_check_state(parent.child(index).checkState(0)) for index in range(parent.childCount())]
            if all(state == Qt.CheckState.Checked for state in states):
                state = Qt.CheckState.Checked
            elif all(state == Qt.CheckState.Unchecked for state in states):
                state = Qt.CheckState.Unchecked
            else:
                state = Qt.CheckState.PartiallyChecked
            parent.setCheckState(0, state)
            parent = parent.parent()

    def _toggle_check(self, item: QTreeWidgetItem) -> None:
        if not (item.flags() & Qt.ItemIsEnabled) or self._selection_mode != "checkbox":
            return
        target = (
            Qt.CheckState.Unchecked
            if _check_state(item.checkState(0)) == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._tree.blockSignals(True)
        try:
            self._set_check_down(item, target)
            self._refresh_ancestors(item)
        finally:
            self._tree.blockSignals(False)
        self._tree.viewport().update()
        self._emit_selection()

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(self.selection_keys())

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        node = item.data(0, NODE_ROLE)
        if isinstance(node, dict):
            self.itemClicked.emit(node)

    def _on_selection_changed(self) -> None:
        if self._selection_mode == "checkbox":
            return
        self._emit_selection()

    def _on_item_changed(self, _item: QTreeWidgetItem, column: int) -> None:
        if column == 0 and self._selection_mode == "checkbox":
            self._emit_selection()

    def changeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._theme_signature = None
            self._apply_theme()

    def _apply_theme(self) -> None:
        tree = getattr(self, "_tree", None)
        if tree is None:
            return
        colors = panel_colors()
        base = tokens()
        signature = (tuple(sorted(colors.items())), tuple(sorted(base.items())))
        if signature == self._theme_signature:
            return
        self._theme_signature = signature
        tree.setStyleSheet(
            f"""
            QTreeWidget#CTree_TreeWidget {{
                background-color: {colors["background"]};
                border: 1px solid {base["border"]};
                border-radius: 6px;
                outline: 0;
            }}
            QTreeWidget#CTree_TreeWidget::item {{
                border: none;
            }}
            """
        )


__all__ = ["CTree"]
