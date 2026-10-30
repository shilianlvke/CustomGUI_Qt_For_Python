"""按钮组件契约：形态、尺寸、状态与主题跟随。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from AppCore import get_theme_manager
from GuiCore import CButton, CButtonGroup, CPushButton, CSplitButton
from GuiCore.CustomUI.button.severity import Severity, Variant, colors_for, is_dark_theme


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _restore_theme():
    yield
    get_theme_manager().apply("default")


def test_all_severity_variant_combinations_render(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    for severity in Severity:
        for variant in Variant:
            layout.addWidget(CButton(text=severity.value.title(), severity=severity, variant=variant))
    host.show()
    QTest.qWait(80)

    image = host.grab()
    assert not image.isNull()
    host.hide()


def test_size_heights(qapp):
    for size, height in (("sm", 32), ("md", 40), ("lg", 48)):
        button = CButton(text="Size", size=size)
        assert button.height() == height


def test_icon_only_button_is_square(qapp):
    button = CButton(icon="icon_check")
    hint = button.sizeHint()
    assert hint.width() == hint.height()


def test_rounded_uses_capsule_radius(qapp):
    button = CButton(text="Rounded", rounded=True)
    assert button._radius() == button.height() / 2


def test_loading_blocks_click_until_finished(qapp):
    button = CButton(text="Search")
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))

    button.set_loading(True)
    assert button.is_loading()
    QTest.mouseClick(button, Qt.LeftButton)
    assert clicks == []

    button.set_loading(False)
    QTest.mouseClick(button, Qt.LeftButton)
    assert len(clicks) == 1


def test_disabled_button_ignores_click(qapp):
    button = CButton(text="Disabled")
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))
    button.setEnabled(False)

    QTest.mouseClick(button, Qt.LeftButton)
    assert clicks == []


def test_group_merges_outer_corners(qapp):
    first = CButton(text="Save")
    last = CButton(text="Cancel")
    CButtonGroup([first, last])

    assert first._corners == (True, False, False, True)
    assert last._corners == (False, True, True, False)


def test_split_button_keeps_both_segments(qapp):
    split = CSplitButton("Save", [("Update", "icon_refresh")])
    assert split.main_button().text() == "Save"
    assert split.arrow_button().height() == split.main_button().height()
    assert split.sizeHint().width() > split.main_button().sizeHint().width()


def test_colors_follow_theme_switch(qapp):
    before = colors_for(Severity.SUCCESS, Variant.SOLID)
    dark_before = is_dark_theme()

    get_theme_manager().apply("bright")
    after = colors_for(Severity.SUCCESS, Variant.SOLID)

    assert is_dark_theme() != dark_before
    assert before.background != after.background


def test_push_button_compatibility_shell(qapp):
    button = CPushButton(size=QSize(80, 32), text="Legacy")
    assert button.size() == QSize(80, 32)
    assert button.text() == "Legacy"
