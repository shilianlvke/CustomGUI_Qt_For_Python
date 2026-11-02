"""树、树形表格与时间线的契约测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from customgui.guicore.custom_ui.data import CTimeline, CTree, CTreeTable
from customgui.guicore.custom_ui.data.table import CTableColumn
from customgui.guicore.custom_ui.data.tree import KEY_ROLE


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


NODES = [
    {
        "label": "Documents",
        "key": "docs",
        "expanded": True,
        "children": [
            {
                "label": "Work",
                "key": "work",
                "children": [
                    {"label": "Report", "key": "report"},
                    {"label": "Budget", "key": "budget"},
                ],
            },
            {"label": "Personal", "key": "personal"},
        ],
    },
    {
        "label": "Images",
        "key": "images",
        "children": [
            {"label": "Vacation", "key": "vacation"},
        ],
    },
]

COLUMNS = [
    CTableColumn("name", "Name", 180),
    CTableColumn(
        "status",
        "Status",
        120,
        "center",
        tag=lambda value, _row: ("success", value) if value == "OK" else ("danger", value),
    ),
]

ROWS = [
    {
        "name": "Root",
        "key": "root",
        "status": "OK",
        "children": [
            {"name": "Child", "key": "child", "status": "WARN"},
            {"name": "Second", "key": "second", "status": "OK"},
        ],
    }
]

EVENTS = [
    {
        "date": "2026-11-01",
        "title": "Started",
        "description": "Timeline begins",
        "severity": "success",
    },
    {
        "date": "2026-11-02",
        "title": "In progress",
        "description": "Timeline continues",
        "severity": "warn",
    },
]


def _item_by_key(tree: CTree, key: str):
    for item in tree._iter_items():
        if item.data(0, KEY_ROLE) == key:
            return item
    raise AssertionError(f"missing key: {key}")


def _tree_item_state(item) -> Qt.CheckState:
    return Qt.CheckState(item.checkState(0))


def _standard_item_state(item) -> Qt.CheckState:
    return Qt.CheckState(item.checkState())


def test_ctree_construction_and_expand_collapse(qapp):
    tree = CTree(NODES)
    assert tree.tree().topLevelItemCount() == 2
    assert tree.tree().selectionMode().name == "SingleSelection"
    assert tree.selection_keys() == []

    tree.collapse_all()
    assert tree.tree().topLevelItem(0).isExpanded() is False
    tree.expand_all()
    assert tree.tree().topLevelItem(0).isExpanded() is True
    assert _item_by_key(tree, "work").isExpanded() is True
    tree.collapse_all()
    assert _item_by_key(tree, "work").isExpanded() is False

    tree.hide()
    tree.deleteLater()


def test_ctree_single_and_multiple_selection(qapp):
    single = CTree(NODES, selection_mode="single")
    selection: list = []
    single.selectionChanged.connect(selection.append)
    single.set_selection_keys(["report"])
    assert single.selection_keys() == ["report"]
    assert selection[-1] == ["report"]

    multi = CTree(NODES, selection_mode="multiple")
    multi.set_selection_keys(["report", "vacation"])
    assert set(multi.selection_keys()) == {"report", "vacation"}

    single.deleteLater()
    multi.deleteLater()


def test_ctree_checkbox_selection(qapp):
    tree = CTree(NODES, selection_mode="checkbox")
    assert tree.tree().selectionMode().name == "NoSelection"
    assert tree.selection_keys() == []

    tree.set_selection_keys(["report"])
    report = _item_by_key(tree, "report")
    work = _item_by_key(tree, "work")
    docs = _item_by_key(tree, "docs")
    assert _tree_item_state(report) == Qt.Checked
    assert _tree_item_state(work) == Qt.PartiallyChecked
    assert _tree_item_state(docs) == Qt.PartiallyChecked
    assert tree.selection_keys() == ["report"]

    tree.set_selection_keys(["docs"])
    keys = tree.selection_keys()
    assert "docs" in keys
    assert "report" in keys
    assert "personal" in keys
    assert _tree_item_state(_item_by_key(tree, "images")) == Qt.Unchecked

    tree._toggle_check(_item_by_key(tree, "report"))
    assert _tree_item_state(report) == Qt.Unchecked
    assert _tree_item_state(work) == Qt.PartiallyChecked

    tree.deleteLater()


def test_tree_table_checkbox_selection_and_expansion(qapp):
    table = CTreeTable(COLUMNS, ROWS, checkbox=True)
    assert table.view().model().rowCount() == 1
    assert table.checked_keys() == []

    root_index = table.view().model().index(0, 0)
    table.expand_all()
    assert table.view().isExpanded(root_index) is True
    table.collapse_all()
    assert table.view().isExpanded(root_index) is False

    records: list = []
    table.selectionChanged.connect(records.append)
    table.set_checked_keys(["child"])
    assert set(table.checked_keys()) == {"child"}
    assert any(record["key"] == "child" for record in table.checked_records())
    assert any(record["key"] == "child" for record in records[-1])

    root_item = table._model.item(0, 0)
    assert _standard_item_state(root_item) == Qt.PartiallyChecked
    table.set_checked_keys(["root"])
    assert "root" in table.checked_keys()
    assert "child" in table.checked_keys()

    table.resize(640, 320)
    table.show()
    table.hide()
    table.deleteLater()


def test_tree_table_row_selection_without_checkbox(qapp):
    table = CTreeTable(COLUMNS, ROWS, checkbox=False, selection_mode="multiple")
    table.expand_all()
    table.set_selection_keys(["child"])
    assert table.selection_keys() == ["child"]
    assert table.selected_records()[0]["key"] == "child"
    table.deleteLater()


def test_widgets_render_without_exception(qapp):
    tree = CTree(NODES, selection_mode="checkbox")
    tree.resize(420, 320)
    tree.show()
    tree.expand_all()
    qapp.processEvents()
    assert tree.grab().isNull() is False
    tree.hide()
    tree.deleteLater()

    table = CTreeTable(COLUMNS, ROWS, checkbox=True)
    table.resize(640, 320)
    table.show()
    table.expand_all()
    qapp.processEvents()
    assert table.grab().isNull() is False
    table.hide()
    table.deleteLater()

    timeline = CTimeline(EVENTS)
    timeline.resize(560, 460)
    timeline.show()
    qapp.processEvents()
    assert timeline.grab().isNull() is False
    timeline.hide()
    timeline.deleteLater()


def test_timeline_align_and_layout_switch(qapp):
    timeline = CTimeline(EVENTS)
    timeline.resize(560, 460)
    timeline.show()
    qapp.processEvents()

    assert len(timeline.cards()) == 2
    assert timeline.align() == "left"
    assert timeline.layout_mode() == "vertical"
    assert timeline.cards()[0].geometry().left() > 0

    timeline.set_align("right")
    right_x = timeline.cards()[0].geometry().left()
    timeline.set_align("left")
    left_x = timeline.cards()[0].geometry().left()
    assert left_x > right_x

    timeline.set_align("alternate")
    assert timeline.cards()[0].geometry().left() > timeline.cards()[1].geometry().left()

    timeline.set_layout("horizontal")
    assert timeline.layout_mode() == "horizontal"
    assert timeline.cards()[1].geometry().left() > timeline.cards()[0].geometry().left()

    clicks: list = []
    timeline.itemClicked.connect(clicks.append)
    QTest.mouseClick(timeline.cards()[0], Qt.LeftButton)
    assert clicks == [0]

    timeline.set_events(EVENTS[:1])
    assert len(timeline.cards()) == 1
    timeline.set_layout("vertical")
    assert timeline.layout_mode() == "vertical"

    timeline.hide()
    timeline.deleteLater()
