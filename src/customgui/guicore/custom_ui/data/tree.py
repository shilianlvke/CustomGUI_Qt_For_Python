"""树与树形表格（复刻 Sakai / PrimeVue 的 Tree 与 TreeTable）。

设计要点：

- 数据统一用 ``list[dict]`` 表达，节点字段为 ``label/key/icon/children/disabled``；
- ``CTree`` 内部使用 ``QTreeWidget``，惰性展开与折叠交给 Qt，行外观由
  :class:`_CTreeDelegate` 完全自绘（展开箭头、复选框、图标、文字）；
- ``CTreeTable`` 内部使用 ``QTreeView + QStandardItemModel``，列定义复用
  :class:`~.table.CTableColumn`，语义标签复用其 ``tag`` 回调；
- 所有颜色在绘制时实时读取 :func:`~..display.palette.tokens` 与
  :func:`~..panels.style.panel_colors`，主题切换后调用 ``update()`` 即可重绘。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..button.severity import contrast_text, normalize_severity, severity_color
from ..display.icon import tinted_pixmap
from ..display.palette import tokens
from ..paint_utils import draw_check, draw_chevron
from ..panels.style import panel_colors, with_alpha
from .table import CTableColumn

#: 节点原始 ``dict``
NODE_ROLE = Qt.UserRole + 10
#: 节点选择键
KEY_ROLE = Qt.UserRole + 11

#: 每级缩进
INDENT = 18
#: 展开箭头占位
ARROW_SIZE = 16
#: 复选框尺寸
CHECKBOX_SIZE = 14
#: 节点图标尺寸
ICON_SIZE = 16
#: 行高
ROW_HEIGHT = 34

_ALIGN = {
    "left": Qt.AlignLeft | Qt.AlignVCenter,
    "center": Qt.AlignCenter,
    "right": Qt.AlignRight | Qt.AlignVCenter,
}


def _alignment(name: str) -> Qt.AlignmentFlag:
    return _ALIGN.get(name, _ALIGN["left"])


def _node_key(node: dict) -> Any:
    """节点选择键：优先 ``key``，其次 ``label``。"""
    if node.get("key") is not None:
        return node["key"]
    if node.get("label") is not None:
        return node["label"]
    return ""


def _node_label(node: dict) -> str:
    """节点展示文字：优先 ``label``，其次 ``key``。"""
    if node.get("label") is not None:
        return str(node["label"])
    if node.get("key") is not None:
        return str(node["key"])
    return ""


def _index_depth(index: QModelIndex) -> int:
    """索引在树中的层级（根为 0）。"""
    depth = 0
    parent = index.parent()
    while parent.isValid():
        depth += 1
        parent = parent.parent()
    return depth


def _row_metrics(
    rect: QRectF, index: QModelIndex, checkbox: bool
) -> tuple[QRectF | None, QRectF | None, float | None, float]:
    """计算一行中箭头、复选框、图标与文字的水平位置。"""
    x = rect.left() + 8 + _index_depth(index) * INDENT
    center_y = rect.center().y()

    arrow: QRectF | None = None
    model = index.model()
    if model is not None and model.rowCount(index) > 0:
        arrow = QRectF(x, center_y - ARROW_SIZE / 2, ARROW_SIZE, ARROW_SIZE)
        x += ARROW_SIZE + 2

    box: QRectF | None = None
    if checkbox:
        box = QRectF(x, center_y - CHECKBOX_SIZE / 2, CHECKBOX_SIZE, CHECKBOX_SIZE)
        x += CHECKBOX_SIZE + 6

    icon_x: float | None = None
    node = index.data(NODE_ROLE)
    if isinstance(node, dict) and node.get("icon") is not None:
        icon_x = x
        x += ICON_SIZE + 6

    return arrow, box, icon_x, x


def _paint_row_background(painter: QPainter, option: QStyleOptionViewItem) -> None:
    """按选中 / 悬停状态铺一层令牌色底。"""
    rect = QRectF(option.rect)
    if option.state & QStyle.StateFlag.State_Selected:
        painter.fillRect(rect, with_alpha(tokens()["accent"], 36))
    elif option.state & QStyle.StateFlag.State_MouseOver:
        painter.fillRect(rect, QColor(panel_colors()["hover"]))


def _paint_checkbox(painter: QPainter, box: QRectF, state: Qt.CheckState) -> None:
    colors = tokens()
    path = QPainterPath()
    path.addRoundedRect(box, 3, 3)
    if state == Qt.CheckState.Checked:
        painter.fillPath(path, QColor(colors["accent"]))
        draw_check(
            painter,
            box.adjusted(2, 2, -2, -2),
            contrast_text(QColor(colors["accent"])),
            1.8,
        )
        return
    if state == Qt.CheckState.PartiallyChecked:
        painter.fillPath(path, QColor(colors["accent"]))
        painter.setPen(QPen(contrast_text(QColor(colors["accent"])), 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(
            QPointF(box.left() + 3, box.center().y()),
            QPointF(box.right() - 3, box.center().y()),
        )
        return
    painter.fillPath(path, QColor(colors["surface"]))
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(colors["border"]), 1))
    painter.drawPath(path)


def _paint_icon(
    painter: QPainter,
    index: QModelIndex,
    icon_x: float | None,
    center_y: float,
    color: QColor,
    dpr: float = 1.0,
) -> None:
    if icon_x is None:
        return
    node = index.data(NODE_ROLE)
    icon = node.get("icon") if isinstance(node, dict) else None
    if icon is None:
        return
    pixmap = tinted_pixmap(icon, color, ICON_SIZE, max(1.0, float(dpr)))
    if pixmap is not None:
        painter.drawPixmap(QPointF(icon_x, center_y - ICON_SIZE / 2), pixmap)


def _check_state(value: Any) -> Qt.CheckState:
    if value is None:
        return Qt.CheckState.Unchecked
    try:
        return Qt.CheckState(value)
    except (TypeError, ValueError):
        return Qt.CheckState.Unchecked


class _CTreeDelegate(QStyledItemDelegate):
    """CTree 行绘制：箭头、复选框、图标与文字。"""

    def __init__(self, checkbox: bool, parent=None):
        super().__init__(parent)
        self._checkbox = checkbox

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        _paint_row_background(painter, option)

        rect = QRectF(option.rect)
        arrow, box, icon_x, text_x = _row_metrics(rect, index, self._checkbox)
        colors = tokens()
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        text_color = QColor(colors["text" if enabled else "muted"])

        if arrow is not None:
            view = option.widget
            expanded = view.isExpanded(index) if view is not None and hasattr(view, "isExpanded") else False
            draw_chevron(
                painter,
                arrow.center(),
                colors["muted"],
                size=9,
                direction="up" if expanded else "down",
            )

        if box is not None:
            _paint_checkbox(painter, box, _check_state(index.data(Qt.ItemDataRole.CheckStateRole)))

        _paint_icon(
            painter,
            index,
            icon_x,
            rect.center().y(),
            text_color,
            option.widget.devicePixelRatioF() if option.widget is not None else 1.0,
        )

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        available = max(0.0, rect.right() - 10 - text_x)
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(available))
        painter.setPen(QPen(text_color))
        painter.drawText(
            QRectF(text_x, rect.top(), available, rect.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            elided,
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), ROW_HEIGHT))


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


class _TreeTableDelegate(QStyledItemDelegate):
    """CTreeTable 单元格绘制：第一列画树形结构，其余列复用语义标签。"""

    def __init__(self, columns: list[CTableColumn], checkbox: bool, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._checkbox = checkbox

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        _paint_row_background(painter, option)
        if index.column() == 0:
            self._paint_tree_cell(painter, option, index)
        else:
            self._paint_content_cell(painter, option, index)
        painter.restore()

    def _paint_tree_cell(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        rect = QRectF(option.rect)
        arrow, box, icon_x, text_x = _row_metrics(rect, index, self._checkbox)
        colors = tokens()
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        text_color = QColor(colors["text" if enabled else "muted"])

        if arrow is not None:
            view = option.widget
            expanded = view.isExpanded(index) if view is not None and hasattr(view, "isExpanded") else False
            draw_chevron(painter, arrow.center(), colors["muted"], size=9, direction="up" if expanded else "down")
        if box is not None:
            _paint_checkbox(painter, box, _check_state(index.data(Qt.ItemDataRole.CheckStateRole)))
        _paint_icon(
            painter,
            index,
            icon_x,
            rect.center().y(),
            text_color,
            option.widget.devicePixelRatioF() if option.widget is not None else 1.0,
        )

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        available = max(0.0, rect.right() - 10 - text_x)
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(available))
        painter.setPen(QPen(text_color))
        painter.drawText(
            QRectF(text_x, rect.top(), available, rect.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            elided,
        )

    def _paint_content_cell(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if not (0 <= index.column() < len(self._columns)):
            return
        column = self._columns[index.column()]
        node = index.data(NODE_ROLE)
        if not isinstance(node, dict):
            node = {}
        value = node.get(column.field)
        tag = column.tag_for(value, node)
        if tag is not None:
            self._paint_tag(painter, option, index, tag)
            return

        colors = tokens()
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        painter.setPen(QPen(QColor(colors["text" if enabled else "muted"])))
        rect = QRectF(option.rect).adjusted(10, 0, -10, 0)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(max(0, rect.width())))
        painter.drawText(rect, option.displayAlignment, elided)

    @staticmethod
    def _paint_tag(
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        tag: tuple[str, str],
    ) -> None:
        severity, text = tag
        base = severity_color(normalize_severity(severity))
        font = QFont(option.font)
        font.setPixelSize(max(10, font.pixelSize() - 2))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = max(24, metrics.horizontalAdvance(text) + 16)
        height = 22
        rect = QRectF(option.rect)
        x = rect.left() + 10
        if option.displayAlignment & Qt.AlignRight:
            x = rect.right() - width - 10
        elif option.displayAlignment & Qt.AlignHCenter:
            x = rect.center().x() - width / 2
        y = rect.center().y() - height / 2

        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, width, height), height / 2, height / 2)
        painter.fillPath(path, base)
        painter.setPen(contrast_text(base))
        painter.drawText(QRectF(x, y, width, height), Qt.AlignCenter, text)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), 38))


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
        columns: 列定义（复用 :class:`~.table.CTableColumn`）。
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
        header.setStretchLastSection(False)
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
                background-color: {colors["background"]};
                border: 1px solid {base["border"]};
                border-radius: 6px;
                outline: 0;
                alternate-background-color: {base["surface"]};
            }}
            QTreeView#CTreeTable_View::item {{
                border: none;
            }}
            QTreeView#CTreeTable_View QHeaderView::section {{
                background-color: {colors["header"]};
                color: {base["text"]};
                border: none;
                border-bottom: 1px solid {base["border"]};
                padding: 6px 10px;
                font-weight: 600;
            }}
            """
        )


__all__ = ["CTree", "CTreeTable", "NODE_ROLE", "KEY_ROLE"]
