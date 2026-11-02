"""列表类数据视图契约：DataView 排布 / PickList 穿梭 / OrderList 排序。

全部在 offscreen 平台运行，不依赖真实窗口。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QVBoxLayout

from customgui.guicore.custom_ui.data import CDataView, COrderList, CPickList


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


ROWS = [
    {"name": "Bamboo Watch", "price": 65},
    {"name": "Black Watch", "price": 72},
    {"name": "Blue T-Shirt", "price": 29},
]


def test_dataview_construction_layout_and_click(qapp):
    view = CDataView(ROWS, lambda row: QLabel(row["name"]), empty_text="Nothing here")
    view.resize(560, 360)
    view.show()

    assert view.layout_mode() == "list"
    assert view.rows() == ROWS
    assert len(view._items) == len(ROWS)
    assert isinstance(view._content.layout(), QVBoxLayout)

    search = QLabel("Search")
    view.add_header_widget(search)
    assert view._header_layout.indexOf(search) >= 0

    clicked = []
    view.itemClicked.connect(clicked.append)
    QTest.mouseClick(view._items[1], Qt.MouseButton.LeftButton)
    assert clicked == [ROWS[1]]

    view.set_layout("grid")
    assert view.layout_mode() == "grid"
    assert isinstance(view._content.layout(), QGridLayout)
    grid = view._content.layout()
    assert grid.itemAtPosition(0, 0).widget() is not None
    assert grid.itemAtPosition(1, 0).widget() is not None

    view.set_layout("unknown")
    assert view.layout_mode() == "list"
    assert isinstance(view._content.layout(), QVBoxLayout)

    view.set_rows([])
    assert view._items == []
    empties = [label for label in view._content.findChildren(QLabel) if label.text() == "Nothing here"]
    assert empties

    view.hide()
    view.deleteLater()


def test_picklist_moves_and_values(qapp):
    source = [{"id": 1, "name": "Bamboo Watch"}, "Black Watch", {"id": 3, "label": "Blue T-Shirt"}]
    target = ["Game Controller"]
    pick = CPickList(source, target)
    assert pick.values() == (source, target)
    assert pick._source_list.count() == len(source)
    assert pick._source_list.item(0).text() == "Bamboo Watch"

    changed = []
    pick.changed.connect(lambda left, right: changed.append((left, right)))

    pick._source_list.setCurrentRow(0)
    pick.move_to_target()
    assert pick.values()[1][-1] == {"id": 1, "name": "Bamboo Watch"}
    assert len(pick.values()[0]) == 2
    assert changed[-1][1][-1] == {"id": 1, "name": "Bamboo Watch"}

    pick.move_all_to_target()
    assert pick.values()[0] == []
    assert pick.values()[1][0] == "Game Controller"

    pick.set_values((["A"], ["B"]), emit=False)
    assert pick.values() == (["A"], ["B"])
    assert pick._source_list.count() == 1
    assert pick._target_list.count() == 1

    pick.move_to_source([0])
    assert pick.values() == (["A", "B"], [])

    pick.set_values(([], ["C", "D"]), emit=False)
    pick.move_all_to_source()
    assert pick.values() == (["C", "D"], [])

    pick.deleteLater()


def test_order_list_reorder_and_remove(qapp):
    order = COrderList(["one", "two", "three"])
    assert order.items() == ["one", "two", "three"]

    changed = []
    order.changed.connect(changed.append)

    order._list.setCurrentRow(0)
    order.move_down()
    assert order.items() == ["two", "one", "three"]
    assert order._list.item(1).isSelected()

    order.move_up()
    assert order.items() == ["one", "two", "three"]

    order._list.clearSelection()
    order._list.setCurrentRow(2)
    order.remove_selected()
    assert order.items() == ["one", "two"]
    assert changed[-1] == ["one", "two"]

    order.set_items(["x", "y"], emit=False)
    assert order.items() == ["x", "y"]

    order.deleteLater()
