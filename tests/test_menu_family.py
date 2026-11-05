"""菜单族与步骤容器契约：点击、子菜单、右键定位、标签切换、步骤导航。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from sllkgui.guicore.custom_ui.menu import (
    CContextMenu,
    CMegaMenu,
    CMenubar,
    CMenuList,
    CPanelMenu,
    CStepper,
    CTabMenu,
    CTieredMenu,
    MenuItem,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _click(widget, rect) -> None:
    center = rect.center()
    QTest.mouseClick(widget, Qt.LeftButton, pos=QPoint(int(center.x()), int(center.y())))


# ----------------------------------------------------------------------
# CMenuList / CTieredMenu
# ----------------------------------------------------------------------
def test_menu_list_click_emits_and_runs_command(qapp):
    calls = []
    menu = CMenuList(
        [
            MenuItem("Open", key="open", command=lambda: calls.append("open")),
            MenuItem(separator=True),
            MenuItem("Disabled", disabled=True),
        ]
    )
    seen = []
    menu.itemClicked.connect(seen.append)
    menu.show()

    _click(menu, menu.row_rect(0))
    assert [item.key for item in seen] == ["open"]
    assert calls == ["open"]

    _click(menu, menu.row_rect(2))
    assert len(seen) == 1
    menu.hide()


def test_tiered_menu_expands_and_clicks_child(qapp):
    calls = []
    menu = CTieredMenu(
        [
            MenuItem(
                "File",
                items=[
                    MenuItem("New", command=lambda: calls.append("new")),
                    MenuItem("Open"),
                ],
            )
        ]
    )
    seen = []
    menu.itemClicked.connect(seen.append)
    menu.show()

    assert menu.row_count() == 1
    _click(menu, menu.row_rect(0))
    assert menu.row_count() == 3
    assert menu.is_expanded("/0")

    _click(menu, menu.row_rect(1))
    assert [item.label for item in seen] == ["New"]
    assert calls == ["new"]

    _click(menu, menu.row_rect(0))
    assert menu.row_count() == 1
    assert menu.expanded_paths() == []
    menu.hide()


# ----------------------------------------------------------------------
# 菜单栏 / MegaMenu / 面板菜单
# ----------------------------------------------------------------------
def test_menubar_hover_opens_dropdown(qapp):
    bar = CMenubar([MenuItem("File", items=[MenuItem("New")])])
    bar.resize(300, bar.height())
    bar.show()
    QTest.mouseMove(bar, bar.item_rect(0).center().toPoint())
    QTest.qWait(30)
    assert bar.is_menu_open()
    assert bar.active_index() == 0
    bar.close_menu()
    assert not bar.is_menu_open()
    bar.hide()


def test_mega_menu_columns_and_panel_menu_accordion(qapp):
    mega = CMegaMenu(
        [
            MenuItem(
                "Tools",
                items=[MenuItem("A"), MenuItem("B"), MenuItem("C")],
            )
        ],
        columns=2,
    )
    assert mega.columns() == 2
    mega.open_menu(0)
    assert mega.is_menu_open()
    mega.close_menu()

    panel = CPanelMenu(
        [
            MenuItem("Group 1", items=[MenuItem("One")]),
            MenuItem("Group 2", items=[MenuItem("Two")]),
        ]
    )
    panel.expand_index(0)
    assert panel.row_count() == 3
    panel.toggle_index(0)
    panel.expand_index(1)
    assert panel.row_count() == 3
    assert panel.expanded_paths() == ["/1"]


# ----------------------------------------------------------------------
# CContextMenu
# ----------------------------------------------------------------------
def test_context_menu_shows_at_global_position(qapp):
    context = CContextMenu([MenuItem("Copy", key="copy"), MenuItem("Paste")])
    seen = []
    context.itemClicked.connect(seen.append)

    position = QPoint(130, 90)
    context.show_at(position)
    assert context.pos() == position
    assert context.isVisible()

    _click(context, context.row_rect(0))
    assert [item.key for item in seen] == ["copy"]
    assert not context.isVisible()


# ----------------------------------------------------------------------
# CTabMenu
# ----------------------------------------------------------------------
def test_tab_menu_switch(qapp):
    tabs = CTabMenu(["One", "Two", "Three"], current=0)
    tabs.resize(360, tabs.height())
    tabs.show()
    seen = []
    tabs.tabChanged.connect(seen.append)

    _click(tabs, tabs.tab_rect(1))
    assert tabs.current_index() == 1
    assert seen == [1]

    tabs.set_current(2)
    assert seen == [1, 2]

    _click(tabs, tabs.tab_rect(2))
    assert seen == [1, 2]
    tabs.hide()


# ----------------------------------------------------------------------
# CStepper
# ----------------------------------------------------------------------
def test_stepper_next_and_finish_signals(qapp):
    stepper = CStepper(
        [
            {"title": "填写", "content": QLabel("content")},
            {"title": "确认", "content": "summary"},
            "完成",
        ],
        current=0,
    )
    changed = []
    done = []
    stepper.stepChanged.connect(changed.append)
    stepper.finished.connect(lambda: done.append(True))
    stepper.show()

    assert stepper.current_index() == 0
    assert stepper.next_button.text() == "下一步"
    assert not stepper.prev_button.isEnabled()

    stepper.next_button.click()
    assert stepper.current_index() == 1
    assert changed == [1]
    assert stepper.prev_button.isEnabled()

    stepper.next_button.click()
    assert stepper.current_index() == 2
    assert changed == [1, 2]
    assert stepper.next_button.text() == "完成"

    stepper.next_button.click()
    assert done == [True]
    stepper.hide()


def test_stepper_left_position_and_add_step(qapp):
    stepper = CStepper(["One"], position="left")
    assert stepper.position() == "left"
    assert stepper.add_step("Two", QLabel("two")) == 1
    assert stepper.step_count() == 2
    stepper.set_current(1)
    assert stepper.current_index() == 1
