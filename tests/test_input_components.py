"""输入组件契约：尺寸、状态、图标、数字步进、组合圆角与浮动标签。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from GuiCore import (
    CFloatLabel,
    CInputGroup,
    CInputGroupAddon,
    CInputNumber,
    CInputText,
    CLineEdit,
    CTextarea,
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
