"""左侧菜单按钮的选中态过渡与主题跟随。

契约：页面选中与导航 tab 共用一条 0→1 的进度属性，``paintEvent`` 按进度插值
高亮块、文字与图标；按钮批量取消选中（``select_only_one`` 会遍历所有按钮）时，
仍处于 tab 态的按钮必须保持高亮；颜色不缓存，切换主题后重绘即生效。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from AppCore import ColorPalette, get_theme_manager
from GuiCore.WindowDefineUI.left_menu.menu_button import CLeftMenuButton, _mix_color

_FONT = "微软雅黑"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _restore_theme():
    yield
    get_theme_manager().apply("default")


@pytest.fixture
def host(qapp):
    widget = QWidget()
    widget.resize(240, 160)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)
    yield widget, layout
    widget.hide()
    widget.deleteLater()


def _button(host, layout, name, **kwargs):
    btn = CLeftMenuButton(
        host,
        name,
        btn_id=f"btn_{name}",
        icon_path="icon_setting",
        minimum_width=50,
        maximum_width=240,
        font_family=_FONT,
        **kwargs,
    )
    layout.addWidget(btn)
    return btn


def test_initial_progress_matches_state(host):
    widget, layout = host
    active = _button(widget, layout, "active", is_active=True)
    normal = _button(widget, layout, "normal")
    tab = _button(widget, layout, "tab", is_active_tab=True)
    widget.show()
    QTest.qWait(30)

    assert active._active_progress == pytest.approx(1.0)
    assert normal._active_progress == pytest.approx(0.0)
    assert tab._active_progress == pytest.approx(1.0)


def test_selection_transitions_smoothly(host):
    widget, layout = host
    old = _button(widget, layout, "old", is_active=True)
    new = _button(widget, layout, "new")
    widget.show()
    QTest.qWait(30)

    old.set_active(False)
    new.set_active(True)

    # 过渡中：旧按钮淡出、新按钮淡入，且不会瞬间跳到终值
    QTest.qWait(60)
    assert 0.0 < old._active_progress < 1.0
    assert 0.0 < new._active_progress < 1.0

    QTest.qWait(400)
    assert old._active_progress == pytest.approx(0.0)
    assert new._active_progress == pytest.approx(1.0)


def test_tab_keeps_highlight_when_bulk_deselect(host):
    widget, layout = host
    tab = _button(widget, layout, "tab", is_active_tab=True)
    widget.show()
    QTest.qWait(30)

    # select_only_one 会遍历全部按钮调用 set_active(False)
    tab.set_active(False)
    QTest.qWait(60)

    assert tab._active_progress == pytest.approx(1.0)
    assert tab.is_active_tab() is True


def test_mix_color_endpoints():
    start = ColorPalette.custom_icon_color
    end = ColorPalette.custom_context_color

    assert _mix_color(start, end, 0).name().lower() == start.lower()
    assert _mix_color(start, end, 1).name().lower() == end.lower()


def test_button_colors_follow_theme(host):
    """颜色不能被缓存在按钮里，否则切换主题后仍是旧配色。"""
    widget, layout = host
    button = _button(widget, layout, "theme")
    widget.show()
    QTest.qWait(30)
    before_bg = button._normal_bg_color()
    before_icon = button._normal_icon_color()

    get_theme_manager().apply("bright")
    button.update()
    QTest.qWait(30)

    assert button._normal_bg_color() != before_bg
    assert button._normal_icon_color() != before_icon
