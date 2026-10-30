"""面板与布局组件契约：标签页、手风琴、面板、字段集、工具栏、分割器、表单、导航。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from GuiCore import (
    CAccordion,
    CBreadcrumb,
    CButton,
    CDialog,
    CDrawer,
    CFieldset,
    CFormGrid,
    CFormField,
    CInputText,
    CPanel,
    CSplitter,
    CSteps,
    CTabs,
    CToolbar,
)
from GuiCore.CustomUI.icon_utils import render_icon


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def host(qapp):
    widget = QWidget()
    widget.resize(800, 500)
    widget.show()
    yield widget
    widget.hide()
    widget.deleteLater()


# ----------------------------------------------------------------------
# CTabs
# ----------------------------------------------------------------------
def test_tabs_add_and_switch(qapp):
    tabs = CTabs()
    tabs.add_tab("One", QLabel("1"))
    tabs.add_tab("Two", QLabel("2"))
    assert tabs.count() == 2
    assert tabs.current_index() == 0

    seen = []
    tabs.currentChanged.connect(seen.append)
    tabs.set_current_index(1)
    assert seen == [1]
    assert tabs.current_widget() is tabs.widget(1)
    assert tabs.tab_text(1) == "Two"


def test_tabs_disabled_tab_not_reachable_by_keyboard(qapp):
    tabs = CTabs()
    tabs.add_tab("One", QLabel("1"))
    tabs.add_tab("Locked", QLabel("2"), enabled=False)
    tabs.add_tab("Three", QLabel("3"))
    assert tabs.current_index() == 0
    bar = tabs.tab_bar()
    bar.setFocus()
    QTest.keyClick(bar, Qt.Key_Right)
    # 禁用项被跳过：0 -> 2
    assert tabs.current_index() == 2


def test_tabs_close_removes(qapp):
    tabs = CTabs(closable=True)
    tabs.add_tab("One", QLabel("1"))
    tabs.add_tab("Two", QLabel("2"))
    tabs.tabCloseRequested.connect(tabs.remove_tab)
    tabs.remove_tab(0)
    assert tabs.count() == 1
    assert tabs.tab_text(0) == "Two"


# ----------------------------------------------------------------------
# CAccordion
# ----------------------------------------------------------------------
def test_accordion_single_mode_exclusive(qapp):
    accordion = CAccordion()
    first = accordion.add_panel("A", QLabel("a"))
    second = accordion.add_panel("B", QLabel("b"))
    first.set_expanded(True)
    second.set_expanded(True)
    assert first.is_expanded() is False
    assert second.is_expanded() is True
    assert accordion.active_index() == 1


def test_accordion_multiple_mode(qapp):
    accordion = CAccordion(multiple=True)
    first = accordion.add_panel("A", QLabel("a"))
    second = accordion.add_panel("B", QLabel("b"))
    first.set_expanded(True)
    second.set_expanded(True)
    assert first.is_expanded() and second.is_expanded()


def test_accordion_toggle_and_signals(qapp):
    accordion = CAccordion()
    seen = []
    accordion.panelToggled.connect(lambda index, expanded: seen.append((index, expanded)))
    panel = accordion.add_panel("A", QLabel("a"))
    panel.toggle()
    assert panel.is_expanded() is True
    assert seen == [(0, True)]


# ----------------------------------------------------------------------
# CPanel / CFieldset
# ----------------------------------------------------------------------
def test_panel_toggle(qapp):
    panel = CPanel("Title", "Subtitle", toggleable=True, collapsed=True)
    assert panel.is_expanded() is False
    panel.toggle()
    assert panel.is_expanded() is True


def test_fieldset_toggle(qapp):
    fieldset = CFieldset("Legend", toggleable=True, collapsed=True)
    fieldset.set_expanded(True)
    assert fieldset.is_expanded() is True


# ----------------------------------------------------------------------
# CToolbar
# ----------------------------------------------------------------------
def test_toolbar_holds_widgets(qapp):
    bar = CToolbar()
    bar.add_start(CButton("Start"))
    bar.add_center(CInputText(placeholder="Search"))
    bar.add_end(CButton("End"))
    assert bar.start_layout.count() == 1
    assert bar.center_layout.count() == 1
    assert bar.end_layout.count() == 1


# ----------------------------------------------------------------------
# CSplitter
# ----------------------------------------------------------------------
def test_splitter_weights_applied_after_show(qapp, host):
    splitter = CSplitter("horizontal")
    splitter.add_panel(QLabel("1"), size=1)
    splitter.add_panel(QLabel("2"), size=1)
    splitter.setParent(host)
    splitter.show()
    QTest.qWait(50)
    sizes = splitter.sizes()
    assert len(sizes) == 2
    assert sizes[0] > 0 and sizes[1] > 0
    assert abs(sizes[0] - sizes[1]) <= 2


# ----------------------------------------------------------------------
# CFormGrid / CFormField
# ----------------------------------------------------------------------
def test_form_grid_add_row_and_fields(qapp):
    grid = CFormGrid(columns=2)
    created = grid.add_row(
        [
            ("First", CInputText(), "", True),
            ("Last", CInputText()),
        ]
    )
    assert len(created) == 2 and all(isinstance(item, CFormField) for item in created)
    bio = grid.add_field("Bio", QLabel("x"), help_text="help")
    assert bio is not None
    assert grid.count() == 3


# ----------------------------------------------------------------------
# CBreadcrumb / CSteps
# ----------------------------------------------------------------------
def test_breadcrumb_items(qapp):
    clicked = []
    crumb = CBreadcrumb([{"label": "Home"}, {"label": "Lib"}, {"label": "Apps"}])
    crumb.itemClicked.connect(clicked.append)
    assert len(crumb.items()) == 3


def test_steps_active_and_signal(qapp):
    steps = CSteps(["One", "Two", "Three"], active=0)
    seen = []
    steps.stepClicked.connect(seen.append)
    steps.set_active(2)
    assert steps.active() == 2
    QTest.mouseClick(steps, Qt.LeftButton)
    # 点击坐标落在第一个步骤块内
    QTest.mouseClick(steps, Qt.LeftButton, pos=steps.rect().center())
    assert seen


# ----------------------------------------------------------------------
# 技术债回归
# ----------------------------------------------------------------------
def test_button_hover_transition_runs(qapp, host):
    button = CButton("Save")
    button.setParent(host)
    button.show()
    QTest.qWait(30)
    button._set_state("hover")
    assert button._state == "hover"
    # 过渡动画运行中允许 progress < 1；结束（或瞬切）后应到位
    QTest.qWait(260)
    assert button._display_state == "hover"
    assert button._progress == pytest.approx(1.0)
    button._set_state("normal")
    QTest.qWait(260)
    assert button._display_state == "normal"


def test_dialog_body_wrapped_in_scroll(qapp, host):
    dialog = CDialog("Title", "Body", parent=host)
    body_scroller = None
    for child in dialog.card().children():
        get_widget = getattr(child, "widget", None)
        if callable(get_widget) and get_widget() is not None:
            body_scroller = child
            break
    assert body_scroller is not None
    assert body_scroller.widget() is dialog.content_layout.parentWidget()
    dialog.deleteLater()


def test_drawer_resize_from_grip(qapp, host):
    drawer = CDrawer("Panel", position="right", size=300, parent=host)
    drawer.open_dialog()
    QTest.qWait(260)
    # 右侧抽屉向左拖（dx<0）变宽
    drawer._resize_from_grip(300, QPoint(-50, 0))
    assert drawer._size == 350
    # 拖得太宽受窗口尺寸约束
    drawer._resize_from_grip(350, QPoint(400, 0))
    assert drawer._size == 200
    drawer.deleteLater()


def test_render_icon_dpr_cache(qapp):
    first = render_icon("icon_check", QColor("#ffffff"), 16, 2.0)
    second = render_icon("icon_check", QColor("#ffffff"), 16, 2.0)
    assert first is second
    assert first.devicePixelRatio() == 2.0
    other = render_icon("icon_check", QColor("#ff0000"), 16, 2.0)
    assert other is not first
    one_x = render_icon("icon_check", QColor("#ffffff"), 16, 1.0)
    assert one_x.devicePixelRatio() == 1.0
    assert one_x.width() == 16
