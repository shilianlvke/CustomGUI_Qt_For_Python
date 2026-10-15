"""CustomUI 组件主题实时性回归测试（内联样式不得使用构造时快照）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from AppCore import ColorPalette, get_theme_manager
from GuiCore import CScrollArea, CShowCard, CMenu, CStatusButton


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _restore_theme():
    yield
    get_theme_manager().apply("default")


def _viewport_bg(area):
    """CScrollArea 通过 viewport 调色板着色（而非 QSS，避免裸规则级联污染子控件）。"""
    return area.viewport().palette().color(QPalette.ColorRole.Window).name()


def test_show_card_style_follows_theme(qapp):
    manager = get_theme_manager()
    manager.apply("default")  # 建立基准（避免调色板类默认值与 default 主题值的差异）

    card = CShowCard(bottom_text="demo")
    before = card.styleSheet()

    manager.apply("eye")
    assert card.styleSheet() != before

    manager.apply("default")
    assert card.styleSheet() == before


def test_menu_style_follows_theme(qapp):
    manager = get_theme_manager()
    manager.apply("default")

    menu = CMenu(colorpalette=ColorPalette)
    before = menu.styleSheet()

    manager.apply("eye")
    assert menu.styleSheet() != before


def test_status_button_style_follows_theme(qapp):
    manager = get_theme_manager()
    manager.apply("default")

    btn = CStatusButton()
    before = btn.styleSheet()

    manager.apply("eye")
    assert btn.styleSheet() != before

    manager.apply("default")
    assert btn.styleSheet() == before


def test_scroll_area_background_follows_theme(qapp):
    manager = get_theme_manager()
    manager.apply("default")

    area = CScrollArea(object_name="demo_scroller")
    # 不得使用 QSS：不带选择器的规则会级联到滚动区内所有子控件，破坏其自身样式
    assert area.styleSheet() == ""
    assert _viewport_bg(area) == QColor(ColorPalette.custom_dark_three).name()

    manager.apply("eye")
    assert _viewport_bg(area) == QColor(ColorPalette.custom_dark_three).name()

    manager.apply("default")
    assert _viewport_bg(area) == QColor(ColorPalette.custom_dark_three).name()


def test_scroll_area_custom_background(qapp):
    area = CScrollArea(background="#123456")
    assert _viewport_bg(area) == "#123456"

    get_theme_manager().apply("eye")
    assert _viewport_bg(area) == "#123456"  # 自定义背景不随主题变化

    area.set_background(None)
    assert _viewport_bg(area) == QColor(ColorPalette.custom_dark_three).name()  # 恢复跟随主题


def test_window_frame_override(qapp):
    from GuiCore import CWindow

    window = CWindow()
    default_style = window.styleSheet()

    # 最大化：覆盖为无圆角无边框
    window.set_stylesheet(border_radius=0, border_size=0)
    assert "border-radius: 0px" in window.styleSheet()
    assert "border: 0px solid" in window.styleSheet()

    # 主题重建后覆盖保持
    get_theme_manager().apply("eye")
    window.apply_style()
    assert "border-radius: 0px" in window.styleSheet()

    # 还原：清除覆盖，恢复主题默认
    get_theme_manager().apply("default")
    window.set_stylesheet()
    assert window.styleSheet() == default_style
