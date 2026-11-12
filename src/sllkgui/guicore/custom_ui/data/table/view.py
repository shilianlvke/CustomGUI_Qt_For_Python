"""表格容器 ``CDataTable``：表格 + 冻结列 + 空态 + 分页条。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QItemSelectionModel, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..paginator import CPaginator
from .column import CTableColumn
from .delegate import CTableDelegate
from .model import CTableModel
from .roles import GROUP_ROLE


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
        # QAbstractScrollArea 默认会用不透明的 QPalette.Base 填 viewport，
        # QSS 里的半透明底色根本透不出来；关掉自动填充后表格才真正叠在
        # 宿主卡片/区域玻璃上。
        view.setAutoFillBackground(False)
        view.viewport().setAutoFillBackground(False)
        # 单元格在没有背景规则时回退到 QPalette.Base（不透明），
        # 这里把 Base / Window 都置空，普通行才会真正透出宿主玻璃；
        # 斑马行仍由 QSS 的 alternate-background-color 叠一层淡色。
        palette = view.palette()
        palette.setBrush(QPalette.ColorRole.Base, QBrush(Qt.BrushStyle.NoBrush))
        palette.setBrush(QPalette.ColorRole.Window, QBrush(Qt.BrushStyle.NoBrush))
        view.setPalette(palette)
        header = view.horizontalHeader()
        header.setAutoFillBackground(False)
        header.viewport().setAutoFillBackground(False)
        header_palette = header.palette()
        header_palette.setBrush(QPalette.ColorRole.Base, QBrush(Qt.BrushStyle.NoBrush))
        header_palette.setBrush(QPalette.ColorRole.Window, QBrush(Qt.BrushStyle.NoBrush))
        header.setPalette(header_palette)
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

    def current_row(self) -> int:
        """当前行号；无选中行时返回 -1。"""
        index = self._main.currentIndex()
        return index.row() if index.isValid() else -1

    def select_row(self, row: int, clear: bool = True) -> bool:
        """按行号选中整行并滚动到可见位置（供宿主像列表一样驱动选中态）。"""
        if not (0 <= row < self._model.rowCount()):
            return False
        column = self._main.currentIndex().column() if self._main.currentIndex().isValid() else 0
        index = self._model.index(row, max(0, column))
        if clear:
            self._main.clearSelection()
        self._main.setCurrentIndex(index)
        self._main.selectRow(row)
        self._main.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
        return True

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
            self._frozen.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
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
        # 排序会走模型 reset，selectionModel 随之清空；先记住选中记录，
        # 排序完成后再按记录本体恢复选中，避免「点一下表头选中就没了」。
        selected = self.selected_records()
        self._model.sort(column, order)
        self._sync_sort_indicator(column, order)
        self._restore_selection(selected)

    def _restore_selection(self, records: list[dict]) -> None:
        if not records or self._selection_mode == "none":
            return
        model = self._model
        selection = self._main.selectionModel()
        wanted = {id(record) for record in records}
        selection.blockSignals(True)
        for row in range(model.rowCount()):
            record = model.record_at(row)
            if record is not None and id(record) in wanted:
                selection.select(
                    model.index(row, 0),
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )
        selection.blockSignals(False)
        self._on_selection_changed()

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


__all__ = ["CDataTable"]
