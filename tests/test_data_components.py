"""数据组件契约：表格模型、冻结列、分页与选择。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from customgui.guicore import CDataTable, CPaginator, CTableColumn, CTableModel
from customgui.guicore.custom_ui.data.table import GROUP_ROLE, TAG_ROLE


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


ROWS = [
    {"name": "Bamboo Watch", "category": "Accessories", "price": 65, "status": "INSTOCK"},
    {"name": "Black Watch", "category": "Accessories", "price": 72, "status": "LOWSTOCK"},
    {"name": "Blue T-Shirt", "category": "Clothing", "price": 29, "status": "INSTOCK"},
    {"name": "Game Controller", "category": "Electronics", "price": 99, "status": "INSTOCK"},
]


def _columns() -> list[CTableColumn]:
    return [
        CTableColumn("name", "Name", 180),
        CTableColumn("category", "Category", 130),
        CTableColumn("price", "Price", 110, "right", formatter=lambda value, _row: f"${value}"),
        CTableColumn(
            "status",
            "Status",
            120,
            "center",
            tag=lambda value, _row: ("success", value) if value == "INSTOCK" else ("danger", value),
        ),
    ]


def test_column_formatter_and_tag():
    column = _columns()[2]
    assert column.text(65, {}) == "$65"
    tag_column = _columns()[3]
    assert tag_column.tag_for("INSTOCK", {}) == ("success", "INSTOCK")
    assert tag_column.tag_for("OTHER", {}) == ("danger", "OTHER")


def test_model_filter_sort_and_pagination(qapp):
    model = CTableModel(_columns(), ROWS)
    model.set_page_size(2)
    assert model.page_count() == 2
    assert model.rowCount() == 2
    assert model.total_count() == 4

    model.set_filter("watch")
    assert model.total_count() == 2
    assert model.page_count() == 1
    model.set_filter("")

    model.sort(2, Qt.DescendingOrder)
    assert model.record_at(0)["price"] == 99
    assert model.record_at(1)["price"] == 72

    model.set_page(1)
    assert model.page() == 1
    assert model.rowCount() == 2


def test_model_grouping(qapp):
    model = CTableModel(_columns(), ROWS)
    model.set_group_by("category")
    assert model.page_size() == 0
    assert model.rowCount() == 7
    assert model.index(0, 0).data(GROUP_ROLE) is True
    assert model.index(0, 0).data(Qt.DisplayRole) == "Accessories"
    assert model.index(1, 0).data(GROUP_ROLE) is None
    assert model.index(1, 2).data(TAG_ROLE) is None
    assert model.index(1, 3).data(TAG_ROLE) == ("success", "INSTOCK")


def test_paginator_signals(qapp):
    pager = CPaginator(page=0, page_count=3, page_size=10, total=26)
    changed = []
    size_changed = []
    pager.pageChanged.connect(changed.append)
    pager.pageSizeChanged.connect(size_changed.append)
    pager.set_page(2)
    assert changed == [2]
    pager.set_page_size(20)
    assert size_changed == [20]
    assert pager.page() == 0


def test_data_table_selection_and_frozen_columns(qapp):
    table = CDataTable(_columns(), ROWS, page_size=2, frozen_columns=1)
    table.resize(820, 420)
    table.show()
    table._main.selectRow(0)
    records = table.selected_records()
    assert records and records[0]["name"] == "Bamboo Watch"
    assert table._frozen is not None
    assert table._main.isColumnHidden(0) is True
    assert table._frozen.isColumnHidden(0) is False
    table.set_frozen_columns(0)
    assert table._main.isColumnHidden(0) is False
    table.hide()
    table.deleteLater()


def test_data_table_filter_and_group(qapp):
    table = CDataTable(_columns(), ROWS, page_size=2)
    table.set_filter("Electronics")
    assert table.model().total_count() == 1
    table.set_filter("")
    table.set_group_by("category")
    assert table.model().rowCount() == 7
    assert table._paginator.isVisible() is False
