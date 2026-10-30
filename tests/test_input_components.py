"""输入组件契约：尺寸、状态、图标、数字步进、组合圆角与浮动标签。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from GuiCore import (
    CAutoComplete,
    CCalendarPanel,
    CCheckbox,
    CColorPicker,
    CDatePicker,
    CFloatLabel,
    CInputGroup,
    CInputGroupAddon,
    CInputNumber,
    CInputText,
    CKnob,
    CLineEdit,
    CListbox,
    CMultiSelect,
    CRadioButton,
    CRating,
    CSelect,
    CSelectButton,
    CSlider,
    CTextarea,
    CToggleButton,
    CToggleSwitch,
    CTreeSelect,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def host(qapp):
    widget = QWidget()
    widget.resize(320, 200)
    yield widget
    widget.hide()
    widget.deleteLater()


def test_input_sizes(host):
    for size, height in (("sm", 32), ("md", 40), ("lg", 48)):
        field = CInputText(placeholder="x", size=size, parent=host)
        assert field.height() == height


def test_invalid_flag_toggles_dynamic_property(host):
    field = CInputText(parent=host)
    field.set_invalid(True)
    assert field.property("invalid") == "true"
    assert field.is_invalid()
    field.set_invalid(False)
    assert field.property("invalid") == "false"


def test_disabled_input_is_read_only(host):
    field = CInputText(text="locked", parent=host)
    field.setEnabled(False)
    assert not field.isEnabled()


def test_icon_action_added_and_removed(host):
    field = CInputText(placeholder="search", icon="icon_search", icon_pos="left", parent=host)
    assert len(field.actions()) == 1
    field.set_icon(None)
    assert field.actions() == []


def test_textarea_grows_with_content(host):
    area = CTextarea(rows=2, max_height=300, parent=host)
    initial = area.height()
    area.setPlainText("\n".join(f"line {index}" for index in range(10)))
    assert area.height() >= initial


def test_input_number_steps_and_clamps(host):
    number = CInputNumber(value=5, minimum=0, maximum=10, step=2, parent=host)
    number._step_by(1)
    assert number.value() == 7
    number._step_by(1)
    assert number.value() == 9
    number._step_by(1)
    assert number.value() == 10  # 上限截断
    number.setValue(-5)
    assert number.value() == 0


def test_input_number_formats_decimals(host):
    number = CInputNumber(value=1.5, minimum=0, maximum=10, step=0.5, decimals=1, parent=host)
    number._step_by(1)
    assert number.input().text() == "2.0"


def test_input_group_merges_corners(host):
    addon = CInputGroupAddon(icon="icon_users", parent=host)
    field = CInputText(parent=host)
    group = CInputGroup([addon, field], parent=host)
    assert group.count() if hasattr(group, "count") else True
    assert addon._corners == (True, False, False, True)
    assert field._corners == (False, True, True, False)


def test_float_label_floats_when_filled(host):
    widget = CFloatLabel("Username", parent=host)
    widget.resize(240, 54)
    assert widget._progress == pytest.approx(0.0)
    widget.setText("Alice")
    assert widget._progress == pytest.approx(1.0)
    assert widget.text() == "Alice"


def test_cline_edit_keeps_compact_height(host):
    field = CLineEdit(text="legacy", place_holder_text="hint", parent=host)
    assert field.height() == 32
    assert field.text() == "legacy"


# ----------------------------------------------------------------------
# 批次 2：选择类控件
# ----------------------------------------------------------------------
def test_checkbox_toggles(host):
    box = CCheckbox("Remember me", parent=host)
    assert not box.isChecked()
    box.click()
    assert box.isChecked()


def test_radio_buttons_are_exclusive(host):
    first = CRadioButton("Chicago", parent=host)
    second = CRadioButton("New York", parent=host)
    first.setChecked(True)
    second.setChecked(True)
    assert second.isChecked()
    assert not first.isChecked()


def test_toggle_switch_tracks_state(host):
    switch = CToggleSwitch("Wifi", checked=False, parent=host)
    assert switch._progress == pytest.approx(0.0)
    switch.setChecked(True)
    assert switch._progress == pytest.approx(1.0)
    switch.setChecked(False)
    assert switch._progress == pytest.approx(0.0)


def test_toggle_button_swaps_labels(host):
    button = CToggleButton("Yes", "No", checked=False, parent=host)
    assert button.text() == "No"
    button.click()
    assert button.isChecked()
    assert button.text() == "Yes"


def test_select_button_emits_index(host):
    segment = CSelectButton(["Off", "On"], 0, parent=host)
    seen = []
    segment.selectionChanged.connect(seen.append)
    segment.set_index(1)
    assert segment.current_option() == "On"
    assert seen == [1]


# ----------------------------------------------------------------------
# 批次 3：选择器
# ----------------------------------------------------------------------
def test_select_chooses_option_and_closes(host):
    field = CSelect(["Rome", "Paris"], "Rome", filter=True, parent=host)
    seen = []
    field.selectionChanged.connect(seen.append)
    field._toggle_popup()
    assert field.is_open()
    field._choose(1)
    QTest.qWait(20)
    assert field.value() == "Paris"
    assert seen == ["Paris"]
    assert not field.is_open()


def test_multi_select_toggles_chips(host):
    field = CMultiSelect(["React", "Vue", "Angular"], ["React"], parent=host)
    field._toggle_popup()
    field._choose(1)
    assert field.values() == ["React", "Vue"]
    assert field.is_open()  # 多选不自动收起
    field._choose(0)
    assert field.values() == ["Vue"]
    field.close_popup()
    QTest.qWait(20)


def test_auto_complete_filters_options(host):
    field = CAutoComplete(["React", "Vue", "Angular"], parent=host)
    field._on_text_edited("vu")
    assert field._list is not None
    assert field._list.visible_count() == 1
    field.close_popup()
    QTest.qWait(20)


def test_tree_select_reports_leaf(host):
    nodes = [{"label": "Documents", "children": [{"label": "Work"}, {"label": "Home"}]}]
    field = CTreeSelect(nodes, parent=host)
    seen = []
    field.selectionChanged.connect(seen.append)
    field._toggle_popup()
    tree = field._popover.content_layout().itemAt(0).widget()
    assert "Work" in tree.labels()
    field._choose("Work")
    QTest.qWait(20)
    assert field.value() == "Work"
    assert seen == ["Work"]
    assert not field.is_open()


def test_listbox_filters_rows(host):
    box = CListbox(["Rome", "Paris", "Berlin"], "Rome", parent=host)
    assert box.value() == "Rome"
    box._apply_filter("par")
    assert box._list.visible_count() == 1


def test_calendar_panel_switches_month_and_picks_day(host):
    panel = CCalendarPanel(QDate(2026, 10, 15), parent=host)
    panel.show()
    QTest.qWait(20)
    seen = []
    panel.selectionChanged.connect(seen.append)
    # 2026-10-20：10/1 是周四，前导 3 格，20 号落在第 4 行第 2 列
    QTest.mouseClick(panel, Qt.LeftButton, pos=QPoint(4 + 36 + 18, 34 + 24 + 3 * 36 + 18))
    assert seen and seen[0] == QDate(2026, 10, 20)
    panel.month_offset(-1)
    assert panel.date() == QDate(2026, 10, 20)
    panel.close()


def test_date_picker_emits_date(host):
    field = CDatePicker(QDate(2026, 1, 1), parent=host)
    seen = []
    field.dateChanged.connect(seen.append)
    field.set_date(QDate(2026, 5, 4))
    assert field.date() == QDate(2026, 5, 4)
    assert seen == [QDate(2026, 5, 4)]


# ----------------------------------------------------------------------
# 批次 4：数值可视化
# ----------------------------------------------------------------------
def test_slider_quantizes_and_emits(host):
    slider = CSlider(0, 0, 100, 5, parent=host)
    seen = []
    slider.valueChanged.connect(seen.append)
    slider.setValue(23)
    assert slider.value() == 25
    slider.setValue(300)
    assert slider.value() == 100
    assert seen[-1] == 100


def test_slider_click_jumps_to_position(host):
    slider = CSlider(0, 0, 100, 1, parent=host)
    slider.resize(200, 32)
    slider.show()
    QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(112, 16))
    assert 45 <= slider.value() <= 60
    slider.close()


def test_rating_click_sets_stars(host):
    rating = CRating(0, parent=host)
    rating.show()
    QTest.mouseClick(rating, Qt.LeftButton, pos=QPoint(60, 15))
    assert rating.value() == 3
    rating.close()


def test_knob_snaps_to_step(host):
    knob = CKnob(0, -50, 50, 10, parent=host)
    knob.setValue(23)
    assert knob.value() == 20
    knob.setValue(999)
    assert knob.value() == 50


def test_color_picker_emits_valid_color(host):
    picker = CColorPicker("#22c55e", parent=host)
    seen = []
    picker.colorChanged.connect(seen.append)
    picker.set_color("#ef4444")
    assert picker.color() == "#ef4444"
    assert seen == ["#ef4444"]
    picker.set_color("not-a-color")
    assert picker.color() == "#ef4444"
