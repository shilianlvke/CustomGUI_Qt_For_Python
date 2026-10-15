"""CustomUI 组件主题实时性回归测试。

样式统一后的契约（与 ``CPushButton`` 一致）：

- 组件实例只声明 ``objectName``，颜色/状态/字体一律定义在 ``GuiCore/styles.py``；
- **几何量不进中央样式表**：圆角、边框宽度、内边距、固定宽高、偏移一律由组件
  本地用一条只含几何属性的样式表提供；
- 组件暴露的几何参数默认取 ``None`` 并回落到设计令牌；
- 主题切换由 ``CWindow.apply_style()`` 重建中央样式表并下发，组件自身不订阅主题。
"""

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from AppCore import ColorPalette, get_design_tokens, get_theme_manager
from GuiCore import (
    CLineEdit,
    CMenu,
    CMenuButton,
    CScrollArea,
    CShowCard,
    CStatusButton,
    CToolTip,
    Styles,
)

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


def _central_block(selector):
    """取出中央样式表中某个选择器块的声明文本（到第一个 ``}`` 为止）。"""
    sheet = Styles().style
    start = sheet.find(selector)
    assert start >= 0, f"中央样式表缺少选择器 {selector!r}"
    return sheet[start : sheet.find("}", start)]


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


# --------------------------------------------------------------------------
# 几何量与颜色/字体的职责边界：几何一律在组件本地，不进中央样式表
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("selector", "keyword"),
    [
        ("#CLeftMenu_Bg_Frame", "border-radius"),
        ("#CMenuButton_PushButton {", "border-width"),
        ("#CMenuButton_PushButton {", "border-radius"),
        ("#CMenuButton_PushButton::menu-indicator {", "padding-right"),
        ("#CMenu_Menu::item {", "padding-left"),
        ("#CMenu_Menu::item {", "padding-top"),
        ("#CLeftColumnTitle_Label", "padding-bottom"),
        ("#CLeftColumnTitle_Label", "font:"),
        ("#CLineEdit_LineEdit {", "height:"),
        ("#CComboBox_ComboBox::drop-down", "width:"),
        ("#label_tooltip {", "border-radius"),
        ("#label_tooltip {", "padding-left"),
    ],
)
def test_geometry_not_in_central_stylesheet(qapp, selector, keyword):
    """几何量不得出现在中央样式表里（只允许颜色/状态/字体与令牌化尺寸）。"""
    assert keyword not in _central_block(selector), f"{selector} 仍残留几何声明 {keyword}"


def test_menu_button_geometry_follows_params(qapp):
    """CMenuButton 的圆角/边框宽度由实例参数决定，未传时回落设计令牌。"""
    tokens = get_design_tokens()
    default = CMenuButton()
    assert f"border-radius: {tokens.radius.window}px" in default.styleSheet()
    assert f"border-width: {tokens.border.width}px" in default.styleSheet()

    custom = CMenuButton(radius=4, border_size=6)
    assert "border-radius: 4px" in custom.styleSheet()
    assert "border-width: 6px" in custom.styleSheet()


def test_menu_item_padding_is_local(qapp):
    """CMenu 的菜单项内边距由组件本地提供。"""
    sheet = CMenu(colorpalette=ColorPalette).styleSheet()
    assert "padding-left: 20px" in sheet
    assert "padding-top: 5px" in sheet
    assert "padding-bottom: 5px" in sheet


def test_tooltip_geometry_follows_params(qapp):
    """CToolTip 的圆角/内边距由实例参数决定，未传时回落设计令牌。"""
    tokens = get_design_tokens()
    tip = CToolTip(None, "提示", accent="right")
    assert tip.objectName() == "label_tooltip"
    assert tip.property("accent") == "right"
    assert f"border-radius: {tokens.radius.tooltip}px" in tip.styleSheet()

    custom = CToolTip(None, "提示", radius=3, padding=2)
    assert "border-radius: 3px" in custom.styleSheet()
    assert "padding-left: 2px" in custom.styleSheet()
    assert "padding-right: 2px" in custom.styleSheet()


def test_left_menu_radius_falls_back_to_token(qapp):
    """CLeftMenu 的圆角默认回落设计令牌，且由组件本地提供。"""
    from AppCore import AppLanguages, AppSettings, Language
    from GuiCore import CLeftMenu

    # CLeftMenu 构造期会读取语言资源，测试里按应用启动的方式初始化一次
    Language.update(AppLanguages[AppSettings.language].data)

    menu = CLeftMenu()
    assert f"border-radius: {get_design_tokens().radius.window}px" in menu.bg.styleSheet()

    custom = CLeftMenu(radius=3)
    assert "border-radius: 3px" in custom.bg.styleSheet()


def test_line_edit_height_is_local(qapp):
    """CLineEdit 的固定高度由组件本地提供。"""
    assert "height: 32px" in CLineEdit().styleSheet()
