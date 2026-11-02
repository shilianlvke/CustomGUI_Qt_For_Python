"""数据表格（复刻 PrimeVue Aura DataTable / Column / Paginator）。

实现要点：

- 数据层用 ``QAbstractTableModel``，行数据是 ``dict``，列由 :class:`CTableColumn`
  描述；排序、过滤、分页都在模型侧完成，视图只负责呈现；
- 视觉层复用设计令牌与 ``CTableDelegate``：语义状态列画成 ``CTag`` 同款胶囊，
  分组行整行合并并画成浅色分组头；
- 冻结列用第二个 ``QTableView`` 共用同一个模型与选择模型，隐藏非冻结/冻结列，
  两个视图的垂直滚动与表头排序指示保持同步；
- 分页条 ``CPaginator`` 与表格模型双向绑定，页码、每页条数变化即时重排。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..button.severity import contrast_text, normalize_severity, severity_color
from ..display.palette import tokens
from .paginator import CPaginator

#: 单元格语义标签：(severity, text)
TAG_ROLE = Qt.UserRole + 1
#: 分组头行标记
GROUP_ROLE = Qt.UserRole + 2
#: 单元格对应的原始行数据
RECORD_ROLE = Qt.UserRole + 3
#: 行展开详情行标记
DETAIL_ROLE = Qt.UserRole + 4

_ALIGN = {
    "left": Qt.AlignLeft | Qt.AlignVCenter,
    "center": Qt.AlignCenter,
    "right": Qt.AlignRight | Qt.AlignVCenter,
}


@dataclass
class CTableColumn:
    """表格列定义（对应 PrimeVue 的 ``Column``）。"""

    field: str
    header: str = ""
    width: int | None = None
    align: str = "left"
    min_width: int = 90
    sortable: bool = True
    filterable: bool = True
    frozen: bool = False
    formatter: Callable[[Any, dict], str] | None = None
    tag: Callable[[Any, dict], tuple[str, str] | None] | None = None
    expander: bool = False

    def text(self, value: Any, record: dict) -> str:
        if self.formatter is not None:
            return str(self.formatter(value, record))
        return "" if value is None else str(value)

    def tag_for(self, value: Any, record: dict) -> tuple[str, str] | None:
        if self.tag is None:
            return None
        result = self.tag(value, record)
        if result is None:
            return None
        severity, text = result
        return str(severity), str(text)


class CTableModel(QAbstractTableModel):
    """表格数据模型：过滤 → 排序 → 分组 → 分页。"""

    paginationChanged = Signal()

    def __init__(self, columns: list[CTableColumn] | None = None, rows: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self._columns: list[CTableColumn] = list(columns or [])
        self._rows: list[dict] = list(rows or [])
        self._arranged: list[tuple[str, Any]] = []
        self._filter_text = ""
        self._filter_field: str | None = None
        self._sort_field: str | None = None
        self._sort_order = Qt.AscendingOrder
        self._group_field: str | None = None
        self._page = 0
        self._page_size = 10
        self._rebuild()

    # ------------------------------------------------------------------
    # Qt 模型协议
    # ------------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):  # noqa: N802, B008 - 覆写 Qt 命名
        if parent.isValid():
            return 0
        return len(self._page_items())

    def columnCount(self, parent=QModelIndex()):  # noqa: N802, B008 - 覆写 Qt 命名
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        kind, payload = self._page_items()[index.row()]
        if kind == "detail":
            if role == DETAIL_ROLE:
                return True
            if role == RECORD_ROLE:
                return payload
            return None
        if kind == "group":
            if role == GROUP_ROLE:
                return True
            if role == Qt.DisplayRole:
                return payload
            if role == Qt.TextAlignmentRole:
                return Qt.AlignLeft | Qt.AlignVCenter
            if role == Qt.FontRole:
                font = QFont()
                font.setWeight(QFont.Weight.DemiBold)
                return font
            if role == Qt.ForegroundRole:
                return QColor(tokens()["muted"])
            return None

        column = self._columns[index.column()]
        value = payload.get(column.field)
        if role == Qt.DisplayRole:
            return column.text(value, payload)
        if role == Qt.TextAlignmentRole:
            return _ALIGN.get(column.align, _ALIGN["left"])
        if role == Qt.UserRole:
            return value
        if role == RECORD_ROLE:
            return payload
        if role == TAG_ROLE:
            return column.tag_for(value, payload)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802 - 覆写 Qt 命名
        if orientation != Qt.Horizontal:
            return None if role != Qt.DisplayRole else str(section + 1)
        if role == Qt.DisplayRole and 0 <= section < len(self._columns):
            column = self._columns[section]
            return column.header or column.field
        if role == Qt.TextAlignmentRole and 0 <= section < len(self._columns):
            return _ALIGN.get(self._columns[section].align, _ALIGN["left"])
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        kind, _ = self._page_items()[index.row()]
        if kind in ("group", "detail"):
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def sort(self, column: int, order=Qt.AscendingOrder):  # noqa: N802 - 覆写 Qt 命名
        if not (0 <= column < len(self._columns)):
            return
        self.beginResetModel()
        self._sort_field = self._columns[column].field
        self._sort_order = order
        self._page = 0
        self._rebuild()
        self.endResetModel()
        self.paginationChanged.emit()

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def columns(self) -> list[CTableColumn]:
        return list(self._columns)

    def set_columns(self, columns: list[CTableColumn]) -> None:
        self.beginResetModel()
        self._columns = list(columns)
        self._sort_field = None
        self._group_field = None
        self._rebuild()
        self.endResetModel()
        self.paginationChanged.emit()

    def rows(self) -> list[dict]:
        return list(self._rows)

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self._page = 0
        self._rebuild()
        self.endResetModel()
        self.paginationChanged.emit()

    def set_filter(self, text: str, field: str | None = None) -> None:
        self.beginResetModel()
        self._filter_text = str(text or "").strip().lower()
        self._filter_field = field
        self._page = 0
        self._rebuild()
        self.endResetModel()
        self.paginationChanged.emit()

    def filter_text(self) -> str:
        return self._filter_text

    def set_group_by(self, field: str | None) -> None:
        self.beginResetModel()
        self._group_field = field or None
        self._page = 0
        if self._group_field:
            self._page_size = 0
        self._rebuild()
        self.endResetModel()
        self.paginationChanged.emit()

    def sort_field(self) -> str | None:
        return self._sort_field

    def sort_order(self) -> Qt.SortOrder:
        return self._sort_order

    # ------------------------------------------------------------------
    # 分页
    # ------------------------------------------------------------------
    def page(self) -> int:
        return self._page

    def page_count(self) -> int:
        if self._page_size <= 0:
            return 1
        count = sum(1 for item in self._arranged if item[0] != "detail")
        return max(1, (count + self._page_size - 1) // self._page_size)

    def page_size(self) -> int:
        return self._page_size

    def set_page(self, page: int) -> None:
        target = max(0, min(int(page), self.page_count() - 1))
        if target == self._page:
            return
        self.beginResetModel()
        self._arranged = [item for item in self._arranged if item[0] != "detail"]
        self._page = target
        self.endResetModel()
        self.paginationChanged.emit()

    def set_page_size(self, page_size: int) -> None:
        size = max(0, int(page_size))
        if size == self._page_size:
            return
        self.beginResetModel()
        self._arranged = [item for item in self._arranged if item[0] != "detail"]
        self._page_size = size
        self._page = 0
        self.endResetModel()
        self.paginationChanged.emit()

    def expand_row(self, row: int, record: dict | None = None) -> int:
        """在当前页的第 ``row`` 行后插入一个详情占位行，返回详情行号。

        参考 Sakai 的 row expansion：详情行与普通行同属一个模型，由视图用
        跨列 ``setSpan`` + ``setIndexWidget`` 承载实际内容。再次展开会先移除
        旧详情行；翻页、过滤、排序时由 ``_rebuild`` 一并清除。
        """
        target_record = record if record is not None else self.record_at(row)
        if target_record is None:
            return -1
        clean = [item for item in self._page_items() if item[0] != "detail"]
        target = -1
        for index, item in enumerate(clean):
            if item[0] == "row" and item[1] is target_record:
                target = index
                break
        if target < 0:
            return -1
        self.beginResetModel()
        self._arranged = [item for item in self._arranged if item[0] != "detail"]
        page_start = self._page * self._page_size if self._page_size > 0 else 0
        absolute = page_start + target + 1
        self._arranged.insert(absolute, ("detail", target_record))
        self.endResetModel()
        return target + 1

    def collapse_expansion(self) -> None:
        """移除当前的详情占位行。"""
        if not any(item[0] == "detail" for item in self._arranged):
            return
        self.beginResetModel()
        self._arranged = [item for item in self._arranged if item[0] != "detail"]
        self.endResetModel()

    def total_count(self) -> int:
        return len(self._filtered)

    def filtered_count(self) -> int:
        return sum(1 for item in self._arranged if item[0] != "detail")

    def record_at(self, row: int) -> dict | None:
        items = self._page_items()
        if not (0 <= row < len(items)):
            return None
        kind, payload = items[row]
        return payload if kind == "row" else None

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _rebuild(self) -> None:
        filtered: list[tuple[dict, int]] = []
        for source_index, record in enumerate(self._rows):
            if self._matches_filter(record):
                filtered.append((record, source_index))
        self._filtered = filtered
        if self._sort_field:
            reverse = self._sort_order == Qt.DescendingOrder
            filtered.sort(key=lambda item: self._sort_key(item[0].get(self._sort_field)), reverse=reverse)
        self._arranged = []
        if self._group_field:
            last_group: object = object()
            for record, _source in filtered:
                group = record.get(self._group_field)
                label = "" if group is None else str(group)
                if label != last_group:
                    self._arranged.append(("group", label))
                    last_group = label
                self._arranged.append(("row", record))
        else:
            self._arranged = [("row", record) for record, _source in filtered]

    def _matches_filter(self, record: dict) -> bool:
        if not self._filter_text:
            return True
        if self._filter_field:
            values = [record.get(self._filter_field)]
        else:
            values = list(record.values())
        return any(self._filter_text in str(value).lower() for value in values if value is not None)

    @staticmethod
    def _sort_key(value):
        if value is None:
            return 3, ""
        if isinstance(value, (int, float)):
            return 0, value
        if isinstance(value, str):
            return 1, value.lower()
        return 2, str(value).lower()

    def _page_items(self) -> list[tuple[str, Any]]:
        if self._page_size <= 0:
            return self._arranged
        pages: list[list[tuple[str, Any]]] = [[]]
        data_count = 0
        for item in self._arranged:
            if item[0] == "detail":
                # 详情行永远跟随它上面的数据行，不占用每页条数
                pages[-1].append(item)
                continue
            if data_count and data_count % self._page_size == 0:
                pages.append([])
            pages[-1].append(item)
            data_count += 1
        index = max(0, min(self._page, len(pages) - 1))
        return pages[index]


class CTableDelegate(QStyledItemDelegate):
    """单元格绘制：分组头、语义标签、普通文本。"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: N802
        if index.data(GROUP_ROLE):
            self._paint_group(painter, option, index)
            return
        tag = index.data(TAG_ROLE)
        if tag:
            self._paint_tag(painter, option, index, tag)
            return
        super().paint(painter, option, index)

    @staticmethod
    def _paint_group(painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        colors = tokens()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect)
        painter.fillRect(rect, QColor(colors["surface"]))
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(colors["muted"]))
        text = str(index.data(Qt.DisplayRole) or "")
        text = painter.fontMetrics().elidedText(text, Qt.ElideRight, max(0, int(rect.width()) - 24))
        painter.drawText(rect.adjusted(12, 0, -12, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    @staticmethod
    def _paint_tag(painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex, tag) -> None:
        # 先让样式系统画选中/悬停底色（文字置空）
        styled = QStyleOptionViewItem(option)
        styled.text = ""
        widget = styled.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, widget)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        severity, text = tag
        base = severity_color(normalize_severity(severity))
        font = QFont(option.font)
        font.setPixelSize(max(10, font.pixelSize() - 2))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        rect = QRectF(option.rect)
        max_width = max(24, int(rect.width()) - 20)
        text = metrics.elidedText(text, Qt.ElideRight, max(0, max_width - 16))
        width = min(max_width, max(24, metrics.horizontalAdvance(text) + 16))
        height = 22
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
        painter.restore()

    def sizeHint(self, option, index):  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), 40))


class CDataTable(QWidget):
    """数据表格容器：表格 + 冻结列 + 空态 + 分页条。"""

    selectionChanged = Signal(list)
    rowDoubleClicked = Signal(object)

    def __init__(
        self,
        columns: list[CTableColumn] | None = None,
        rows: list[dict] | None = None,
        page_size: int = 10,
        paginator: bool = True,
        selection_mode: str = "single",
        striped: bool = True,
        gridlines: bool = False,
        frozen_columns: int = 0,
        group_by: str | None = None,
        empty_text: str = "No records found",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CDataTable_Widget")
        self._columns = list(columns or [])
        self._page_size = max(0, int(page_size))
        self._paginator_enabled = bool(paginator)
        self._selection_mode = selection_mode
        self._striped = bool(striped)
        self._gridlines = bool(gridlines)
        self._frozen_count = max(0, int(frozen_columns))
        self._group_by = group_by
        self._empty_text = empty_text
        self._frozen: QTableView | None = None
        self._syncing_scroll = False
        self._detail_widget: QWidget | None = None
        self._detail_overlay: QWidget | None = None
        self._detail_row: int | None = None
        self._detail_record: dict | None = None
        self._row_detail_provider: Callable[[dict], QWidget | None] | None = None
        self._setup_ui()

        self._model = CTableModel(self._columns, rows or [], parent=self)
        self._model.set_page_size(self._page_size)
        self._model.paginationChanged.connect(self._refresh_paginator)
        self._model.modelReset.connect(self._on_model_changed)
        self._model.layoutChanged.connect(self._on_model_changed)
        self._main.setModel(self._model)
        self._main.setItemDelegate(CTableDelegate(self._main))
        self._configure_columns()
        self._main.selectionModel().selectionChanged.connect(self._on_selection_changed)
        if self._frozen_count:
            self.set_frozen_columns(self._frozen_count)
        if self._group_by:
            self._model.set_group_by(self._group_by)
            self._model.set_page_size(0)
            self._paginator.setVisible(False)
        self._refresh_paginator()
        self._on_model_changed()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._stack = QStackedWidget(self)
        self._host = QWidget(self._stack)
        host_layout = QHBoxLayout(self._host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)

        self._main = self._make_view("CDataTable_View")
        host_layout.addWidget(self._main, 1)

        self._empty = QLabel(self._empty_text, self._stack)
        self._empty.setObjectName("CDataTable_Empty")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        self._loading = QLabel("Loading...", self._stack)
        self._loading.setObjectName("CDataTable_Loading")
        self._loading.setAlignment(Qt.AlignCenter)
        self._loading.setWordWrap(True)

        self._stack.addWidget(self._host)
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._loading)
        layout.addWidget(self._stack, 1)

        self._paginator = CPaginator(parent=self)
        self._paginator.setVisible(self._paginator_enabled)
        self._paginator.pageChanged.connect(self._on_page_changed)
        self._paginator.pageSizeChanged.connect(self._on_page_size_changed)
        layout.addWidget(self._paginator)

    def _make_view(self, object_name: str) -> QTableView:
        view = QTableView(self)
        view.setObjectName(object_name)
        view.setAlternatingRowColors(self._striped)
        view.setShowGrid(self._gridlines)
        view.setWordWrap(False)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
            if self._selection_mode == "multiple"
            else QAbstractItemView.SelectionMode.SingleSelection
            if self._selection_mode == "single"
            else QAbstractItemView.SelectionMode.NoSelection
        )
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(40)
        view.horizontalHeader().setHighlightSections(False)
        view.horizontalHeader().setSectionsClickable(True)
        view.horizontalHeader().setStretchLastSection(True)
        view.horizontalHeader().setTextElideMode(Qt.ElideRight)
        view.horizontalHeader().setSortIndicatorShown(True)
        view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        return view

    # ------------------------------------------------------------------
    # 数据 / 列
    # ------------------------------------------------------------------
    def model(self) -> CTableModel:
        return self._model

    def set_rows(self, rows: list[dict]) -> None:
        self._model.set_rows(rows)

    def rows(self) -> list[dict]:
        return self._model.rows()

    def columns(self) -> list[CTableColumn]:
        return self._model.columns()

    def set_columns(self, columns: list[CTableColumn]) -> None:
        self._columns = list(columns)
        self._model.set_columns(columns)
        self._configure_columns()

    def set_filter(self, text: str, field: str | None = None) -> None:
        self._model.set_filter(text, field)

    def set_group_by(self, field: str | None) -> None:
        self._group_by = field
        self._model.set_group_by(field)
        if field:
            self._model.set_page_size(0)
            self._paginator.setVisible(False)
        else:
            self._model.set_page_size(self._page_size or 10)
            self._paginator.setVisible(self._paginator_enabled)
        self._on_model_changed()

    # ------------------------------------------------------------------
    # 分页
    # ------------------------------------------------------------------
    def set_page_size(self, page_size: int) -> None:
        self._page_size = max(0, int(page_size))
        self._model.set_page_size(self._page_size)

    def page_size(self) -> int:
        return self._model.page_size()

    def page(self) -> int:
        return self._model.page()

    def page_count(self) -> int:
        return self._model.page_count()

    def _on_page_changed(self, page: int) -> None:
        self._model.set_page(page)

    def _on_page_size_changed(self, page_size: int) -> None:
        self._model.set_page_size(page_size)

    def _refresh_paginator(self) -> None:
        self._paginator.set_state(
            self._model.page(),
            self._model.page_count(),
            max(1, self._model.page_size() or max(1, self._page_size)),
            self._model.total_count(),
        )
        self._paginator.setVisible(self._paginator_enabled and self._model.page_size() > 0)

    # ------------------------------------------------------------------
    # 选择
    # ------------------------------------------------------------------
    def selected_records(self) -> list[dict]:
        rows = sorted(index.row() for index in self._main.selectionModel().selectedRows())
        records = []
        for row in rows:
            record = self._model.record_at(row)
            if record is not None:
                records.append(record)
        return records

    def current_record(self) -> dict | None:
        index = self._main.currentIndex()
        return self._model.record_at(index.row()) if index.isValid() else None

    def _on_selection_changed(self, *_args) -> None:
        records = self.selected_records()
        if records:
            self.selectionChanged.emit(records)
        else:
            self.selectionChanged.emit([])

    # ------------------------------------------------------------------
    # 冻结列
    # ------------------------------------------------------------------
    def set_frozen_columns(self, count: int) -> None:
        count = max(0, min(int(count), len(self._model.columns())))
        self._frozen_count = count
        if count <= 0:
            if self._frozen is not None:
                self._frozen.setVisible(False)
            for column in range(self._model.columnCount()):
                self._main.setColumnHidden(column, False)
            return

        if self._frozen is None:
            self._frozen = self._make_view("CDataTable_FrozenView")
            self._frozen.setModel(self._model)
            self._frozen.setItemDelegate(CTableDelegate(self._frozen))
            self._frozen.setSelectionModel(self._main.selectionModel())
            self._frozen.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._frozen.horizontalHeader().setStretchLastSection(False)
            self._frozen.verticalScrollBar().valueChanged.connect(self._sync_frozen_scroll)
            self._main.verticalScrollBar().valueChanged.connect(self._sync_main_scroll)
            self._main.verticalScrollBar().valueChanged.connect(lambda _value: self._position_detail_overlay())
            self._main.verticalHeader().sectionResized.connect(self._sync_row_height)
            if self._row_detail_provider is not None:
                self._frozen.doubleClicked.connect(self._show_row_detail)
            self._host.layout().insertWidget(0, self._frozen)
            self._frozen.show()

        for column in range(self._model.columnCount()):
            frozen = column < count
            self._main.setColumnHidden(column, frozen)
            self._frozen.setColumnHidden(column, not frozen)
        self._configure_columns()
        self._update_frozen_width()

    def _sync_frozen_scroll(self, value: int) -> None:
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self._main.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _sync_main_scroll(self, value: int) -> None:
        if self._syncing_scroll or self._frozen is None:
            return
        self._syncing_scroll = True
        self._frozen.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _sync_row_height(self, row: int, _old: int, height: int) -> None:
        """冻结列表格的行高与主表保持一致。"""
        if self._frozen is not None and 0 <= row < self._frozen.verticalHeader().count():
            self._frozen.setRowHeight(row, height)

    def _on_header_clicked(self, column: int) -> None:
        if not (0 <= column < len(self._model.columns())):
            return
        spec = self._model.columns()[column]
        if not spec.sortable:
            return
        if self._model.sort_field() == spec.field:
            order = (
                Qt.DescendingOrder
                if self._model.sort_order() == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            order = Qt.AscendingOrder
        self._model.sort(column, order)
        self._sync_sort_indicator(column, order)

    def _sync_sort_indicator(self, column: int, order) -> None:
        for view in (self._main, self._frozen):
            if view is None:
                continue
            header = view.horizontalHeader()
            header.blockSignals(True)
            header.setSortIndicator(column, order)
            header.blockSignals(False)

    def _update_frozen_width(self) -> None:
        if self._frozen is None or self._frozen_count <= 0:
            return
        width = 0
        for column in range(self._frozen_count):
            spec = self._model.columns()[column]
            width += max(spec.width or 160, spec.min_width)
        width += 2
        self._frozen.setFixedWidth(width)

    # ------------------------------------------------------------------
    # 列几何
    # ------------------------------------------------------------------
    def _configure_columns(self) -> None:
        header = self._main.horizontalHeader()
        for column, spec in enumerate(self._model.columns()):
            header.setMinimumSectionSize(spec.min_width)
            if spec.width is not None:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
                self._main.setColumnWidth(column, spec.width)
            else:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        if self._frozen is not None:
            frozen_header = self._frozen.horizontalHeader()
            for column in range(self._frozen_count):
                spec = self._model.columns()[column]
                frozen_header.setMinimumSectionSize(spec.min_width)
                frozen_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
                self._frozen.setColumnWidth(column, max(spec.width or 160, spec.min_width))
            self._update_frozen_width()

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self._empty.setText(text)

    def set_loading(self, loading: bool, text: str = "Loading...") -> None:
        self._loading.setText(text)
        if loading:
            self._stack.setCurrentWidget(self._loading)
        else:
            self._on_model_changed()

    def set_row_detail_provider(self, provider: Callable[[dict], QWidget | None] | None) -> None:
        """双击行时在表格下方展示详情部件（对应 Sakai 的行展开）。"""
        self._row_detail_provider = provider
        self._main.doubleClicked.connect(self._show_row_detail)
        if self._frozen is not None:
            self._frozen.doubleClicked.connect(self._show_row_detail)

    def _show_row_detail(self, index) -> None:
        record = self._model.record_at(index.row())
        if record is None or self._row_detail_provider is None:
            return
        old_record = self._detail_record
        old_row = self._detail_row
        self._clear_detail_widget(old_row)
        if old_record is record:
            self._model.collapse_expansion()
            self._detail_record = None
            return

        widget = self._row_detail_provider(record)
        if widget is None:
            return
        row = self._model.expand_row(index.row(), record)
        if row < 0:
            widget.deleteLater()
            return
        detail_index = self._model.index(row, 0)
        for view in (self._main, self._frozen):
            if view is not None:
                view.setSpan(row, 0, 1, self._model.columnCount())
                view.setRowHeight(row, max(48, widget.sizeHint().height()))
        if self._frozen is None:
            self._main.setIndexWidget(detail_index, widget)
        else:
            # 冻结列由两个视图拼接而成，单个 indexWidget 只能覆盖右半边；
            # 详情内容改挂到 host 上，横跨冻结列与主表。
            widget.setParent(self._host)
            self._detail_overlay = widget
            widget.show()
            QTimer.singleShot(0, self._position_detail_overlay)
        self._detail_widget = widget
        self._detail_row = row
        self._detail_record = record
        self.rowDoubleClicked.emit(record)

    def _position_detail_overlay(self) -> None:
        if self._detail_overlay is None or self._detail_row is None or self._frozen is None:
            return
        row = self._detail_row
        if row >= self._model.rowCount():
            return
        y = self._main.viewport().mapTo(self._host, QPoint(0, self._main.rowViewportPosition(row))).y()
        height = self._main.rowHeight(row)
        width = self._frozen.width() + self._main.viewport().width()
        if 0 <= y < self._host.height():
            self._detail_overlay.setGeometry(0, y, max(0, width), height)
            self._detail_overlay.show()
            self._detail_overlay.raise_()
        else:
            self._detail_overlay.hide()

    def _clear_detail_widget(self, row: int | None) -> None:
        if row is not None and row < self._model.rowCount():
            detail_index = self._model.index(row, 0)
            for view in (self._main, self._frozen):
                if view is not None:
                    view.setIndexWidget(detail_index, None)
        if self._detail_overlay is not None:
            self._detail_overlay.deleteLater()
            self._detail_overlay = None
        self._detail_widget = None
        self._detail_row = None

    # ------------------------------------------------------------------
    # 模型变化
    # ------------------------------------------------------------------
    def _on_model_changed(self) -> None:
        # 任何 reset（翻页/排序/过滤）都会清掉详情行，这里的引用同步失效
        if self._detail_overlay is not None:
            self._detail_overlay.deleteLater()
            self._detail_overlay = None
        self._detail_widget = None
        self._detail_row = None
        self._detail_record = None
        self._stack.setCurrentWidget(self._host)
        self._empty.setVisible(self._model.rowCount() == 0)
        self._stack.setCurrentWidget(self._host if self._model.rowCount() > 0 else self._empty)
        self._apply_group_spans()
        self._refresh_paginator()

    def _apply_group_spans(self) -> None:
        views = [self._main]
        if self._frozen is not None:
            views.append(self._frozen)
        for view in views:
            view.clearSpans()
        if not self._group_by:
            return
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if index.data(GROUP_ROLE):
                for view in views:
                    view.setSpan(row, 0, 1, self._model.columnCount())

    # ------------------------------------------------------------------
    # 尺寸
    # ------------------------------------------------------------------
    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_frozen_width()
        self._position_detail_overlay()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(760, 420)

    def _paint_debug(self, painter: QPainter) -> None:  # pragma: no cover - 仅用于调试
        painter.end()


__all__ = ["CTableColumn", "CTableModel", "CTableDelegate", "CDataTable", "TAG_ROLE", "GROUP_ROLE", "RECORD_ROLE"]
