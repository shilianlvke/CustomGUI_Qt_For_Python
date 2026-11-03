"""表格数据模型 ``CTableModel``：过滤 → 排序 → 分组 → 分页。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont

from ...display.palette import tokens
from .column import CTableColumn
from .roles import DETAIL_ROLE, GROUP_ROLE, RECORD_ROLE, TAG_ROLE

_ALIGN = {
    "left": Qt.AlignLeft | Qt.AlignVCenter,
    "center": Qt.AlignCenter,
    "right": Qt.AlignRight | Qt.AlignVCenter,
}


class CTableModel(QAbstractTableModel):
    """表格数据模型：过滤 → 排序 → 分组 → 分页。"""

    paginationChanged = Signal()

    def __init__(self, columns: list[CTableColumn] | None = None, rows: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self._columns: list[CTableColumn] = list(columns or [])
        self._rows: list[dict] = list(rows or [])
        self._arranged: list[tuple[str, Any]] = []
        self._filtered: list[tuple[dict, int]] = []
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


__all__ = ["CTableModel"]
