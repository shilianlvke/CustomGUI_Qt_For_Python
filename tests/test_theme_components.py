"""CustomUI 组件主题实时性回归测试。

样式统一后的契约（与 ``CPushButton`` 一致）：

- 组件实例只声明 ``objectName``，颜色/状态/字体一律定义在 ``GuiCore/styles.py``；
- 组件实例上仅保留**与主题无关的几何量**（圆角、边框宽度）；
- 主题切换由 ``CWindow.apply_style()`` 重建中央样式表并下发，组件自身不订阅主题。
"""

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from AppCore import ColorPalette, get_theme_manager
from GuiCore import CScrollArea, CShowCard, CMenu, CStatusButton, Styles

_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_KEYWORDS = ("background", "color:", "rgb(", "rgba(")


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


def _assert_geometry_only(sheet, selector):
    """组件实例样式表只允许出现几何属性；颜色必须来自中央样式表。"""
    assert selector in sheet, f"实例样式表缺少 objectName 选择器：{sheet}"
    assert not _HEX_COLOR_RE.search(sheet), f"实例样式表不应含颜色字面量：{sheet}"
    lowered = sheet.lower()
    for keyword in _COLOR_KEYWORDS:
        assert keyword not in lowered, f"实例样式表不应含 {keyword!r}：{sheet}"


def test_show_card_style_lives_in_central_stylesheet(qapp):
    """CShowCard 颜色集中在中央样式表；实例样式表只留几何量且与主题无关。"""
    manager = get_theme_manager()
    manager.apply("default")

    card = CShowCard(bottom_text="demo")
    own = card.styleSheet()
    _assert_geometry_only(own, "#CShowCard")

    default_central = Styles().style
    assert "#CShowCard #topArea" in default_central

    manager.apply("eye")
    assert card.styleSheet() == own  # 组件不再自带构造时主题快照
    assert Styles().style != default_central  # 颜色随主题重建于中央样式表

    manager.apply("default")
    assert Styles().style == default_central


def test_menu_style_lives_in_central_stylesheet(qapp):
    """CMenu 颜色集中在中央样式表；实例样式表只留几何量。"""
    manager = get_theme_manager()
    manager.apply("default")

    menu = CMenu(colorpalette=ColorPalette)
    own = menu.styleSheet()
    _assert_geometry_only(own, "#CMenu_Menu")

    default_central = Styles().style
    assert "#CMenu_Menu::item:selected" in default_central

    manager.apply("eye")
    assert menu.styleSheet() == own
    assert Styles().style != default_central

    manager.apply("default")
    assert Styles().style == default_central


def test_status_button_style_lives_in_central_stylesheet(qapp):
    """CStatusButton 颜色/状态集中在中央样式表；实例样式表只留几何量。"""
    manager = get_theme_manager()
    manager.apply("default")

    btn = CStatusButton()
    own = btn.styleSheet()
    _assert_geometry_only(own, "#CStatusButton_PushButton")

    default_central = Styles().style
    assert '#CStatusButton_PushButton[status="1"]' in default_central
    assert '#CStatusButton_PushButton[status="-1"]' in default_central

    manager.apply("eye")
    assert btn.styleSheet() == own
    assert Styles().style != default_central

    manager.apply("default")
    assert Styles().style == default_central


def test_status_button_exposes_status_property(qapp):
    """状态经动态属性 ``status`` 表达，供中央样式表的属性选择器着色。"""
    btn = CStatusButton()
    assert btn.objectName() == "CStatusButton_PushButton"
    assert btn.property("status") == btn.status


def test_grips_qsizegrip_child_rule_present(qapp):
    """四角夹点内的 QSizeGrip 必须显式着色。

    历史实现用裸规则覆盖夹点，该规则会级联到子控件 QSizeGrip 使其不再绘制原生
    点阵；改为 ID 选择器后必须补一条后代规则，否则四角会重新出现灰色点阵。
    """
    sheet = Styles().style
    assert "#top_left_grip QSizeGrip" in sheet
    assert "#bottom_right_grip QSizeGrip" in sheet


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
