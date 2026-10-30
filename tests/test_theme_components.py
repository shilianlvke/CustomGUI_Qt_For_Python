"""CustomUI 组件主题实时性回归测试。

样式统一后的契约（与 ``CPushButton`` 一致）：

- 组件实例只声明 ``objectName``，颜色/状态/字体一律定义在 ``GuiCore/styles.py``；
- **几何量不进中央样式表**：圆角、边框宽度、内边距、固定宽高、偏移一律由组件
  本地用一条只含几何属性的样式表提供；
- 组件几何**全部取设计令牌**（``AppCore.SYS.module.token_module``）：组件暴露的
  几何参数默认取 ``None`` 并回落到对应令牌，显式传参可覆盖；
- 主题切换由 ``CWindow.apply_style()`` 重建中央样式表并下发，组件自身不订阅主题。
"""

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

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


def test_scroll_area_transparent_by_default(qapp):
    """默认透明：viewport 与内容部件不自绘，透出上层容器的主题底色。

    透明即 QStyleSheetStyle polish 的目标状态，不会被 repolish 重置。
    """
    manager = get_theme_manager()
    manager.apply("default")

    area = CScrollArea(object_name="demo_scroller")
    # 不得使用 QSS：不带选择器的规则会级联到滚动区内所有子控件，破坏其自身样式
    assert area.styleSheet() == ""
    assert not area.viewport().autoFillBackground()
    assert not area.autoFillBackground()

    # 挂载内容部件后同样保持透明（对抗 QScrollArea 内部对内容部件的强制自绘）
    content = QWidget()
    area.setWidget(content)
    assert not content.autoFillBackground()

    # 透明态在主题切换下保持不变
    manager.apply("eye")
    assert not area.viewport().autoFillBackground()
    assert not content.autoFillBackground()
    manager.apply("default")
    assert not area.viewport().autoFillBackground()


def test_scroll_area_custom_background(qapp):
    area = CScrollArea(background="#123456")
    content = QWidget()
    area.setWidget(content)

    # 显式背景经属性选择器 QSS 着色内容部件（与 CCard 同机制，repolish 后由
    # 样式表系统自动维持）；viewport 永不自绘
    assert content.property(CScrollArea.BG_PROP) is True
    assert f'QWidget[{CScrollArea.BG_PROP}="true"]' in area.styleSheet()
    assert "background-color: #123456" in area.styleSheet()
    assert not area.viewport().autoFillBackground()
    assert not content.autoFillBackground()

    get_theme_manager().apply("eye")  # 自定义背景不随主题变化
    assert "background-color: #123456" in area.styleSheet()

    area.set_background(None)
    assert area.styleSheet() == ""
    assert content.property(CScrollArea.BG_PROP) is None
    assert not content.autoFillBackground()  # 恢复默认透明
    assert not area.viewport().autoFillBackground()


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


def test_menu_button_indicator_geometry_follows_token(qapp):
    """CMenuButton 下拉箭头的内边距与位移取设计令牌，不再硬编码。"""
    tokens = get_design_tokens()
    sheet = CMenuButton().styleSheet()
    assert f"padding-right: {tokens.spacing.menu_indicator_right}px" in sheet
    assert f"top: {tokens.spacing.menu_indicator_offset}px" in sheet
    assert f"left: {tokens.spacing.menu_indicator_offset}px" in sheet


def test_menu_geometry_follows_token(qapp):
    """CMenu 的圆角/边框宽度与菜单项内边距取设计令牌，显式传参可覆盖。"""
    tokens = get_design_tokens()
    sheet = CMenu(colorpalette=ColorPalette).styleSheet()
    assert f"border-radius: {tokens.radius.window}px" in sheet
    assert f"border-width: {tokens.border.width}px" in sheet
    assert f"padding-left: {tokens.spacing.menu_item_left}px" in sheet
    assert f"padding-top: {tokens.spacing.menu_item_vertical}px" in sheet
    assert f"padding-bottom: {tokens.spacing.menu_item_vertical}px" in sheet

    custom = CMenu(radius=3, border_size=1)
    assert "border-radius: 3px" in custom.styleSheet()
    assert "border-width: 1px" in custom.styleSheet()


def test_show_card_geometry_follows_token(qapp):
    """CShowCard 的圆角与透明边框宽度取设计令牌，显式传参可覆盖。"""
    tokens = get_design_tokens()
    sheet = CShowCard(bottom_text="demo").styleSheet()
    assert f"border-radius: {tokens.radius.window}px" in sheet
    assert f"border: {tokens.size.card_inset}px solid transparent" in sheet

    custom = CShowCard(bottom_text="demo", radius=3, border_size=1)
    assert "border-radius: 3px" in custom.styleSheet()
    assert "border: 1px solid transparent" in custom.styleSheet()


def test_status_button_geometry_follows_token(qapp):
    """CStatusButton 的圆角与边框宽度取设计令牌，显式传参可覆盖。"""
    tokens = get_design_tokens()
    sheet = CStatusButton().styleSheet()
    assert f"border-radius: {tokens.radius.window}px" in sheet
    assert f"border-width: {tokens.border.width}px" in sheet

    custom = CStatusButton(radius=3, border_size=1)
    assert "border-radius: 3px" in custom.styleSheet()
    assert "border-width: 1px" in custom.styleSheet()


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


def _init_language():
    """CLeftMenu / CLeftColumn 构造期会读取语言资源，按应用启动的方式初始化一次。"""
    from AppCore import AppLanguages, AppSettings, Language

    Language.update(AppLanguages[AppSettings.language].data)


def test_left_menu_radius_falls_back_to_token(qapp):
    """CLeftMenu 的圆角默认回落设计令牌，且由组件本地提供。"""
    from GuiCore import CLeftMenu

    _init_language()

    menu = CLeftMenu()
    assert f"border-radius: {get_design_tokens().radius.window}px" in menu.bg.styleSheet()

    custom = CLeftMenu(radius=3)
    assert "border-radius: 3px" in custom.bg.styleSheet()


def test_left_column_geometry_follows_token(qapp):
    """CLeftColumn 的圆角与标题标签几何取设计令牌，显式传参可覆盖。"""
    from GuiCore import CLeftColumn

    _init_language()
    tokens = get_design_tokens()

    column = CLeftColumn(
        app_parent=None,
        text_title="",
        text_title_size=tokens.typography.size_title,
        icon_path="icon_menu",
        icon_close_path="icon_menu_close",
        font_family=tokens.typography.family,
    )
    assert f"border-radius: {tokens.radius.window}px" in column.title_bg_frame.styleSheet()

    label_sheet = column.title_label.styleSheet()
    assert f"padding-bottom: {tokens.spacing.label_padding_bottom}px" in label_sheet
    assert f"{tokens.typography.weight_label} {tokens.typography.size_label}pt" in label_sheet

    custom = CLeftColumn(
        app_parent=None,
        text_title="",
        text_title_size=tokens.typography.size_title,
        icon_path="icon_menu",
        icon_close_path="icon_menu_close",
        font_family=tokens.typography.family,
        radius=3,
    )
    assert "border-radius: 3px" in custom.title_bg_frame.styleSheet()


def test_line_edit_height_follows_token(qapp):
    """CLineEdit 的固定高度取设计令牌。"""
    tokens = get_design_tokens()
    assert f"height: {tokens.size.control_height}px" in CLineEdit().styleSheet()


def test_combo_box_drop_down_width_follows_token(qapp):
    """CComboBox 的下拉箭头区域宽度取设计令牌。"""
    from GuiCore import CComboBox

    tokens = get_design_tokens()
    sheet = CComboBox().styleSheet()
    assert f"width: {tokens.size.drop_down_width}px" in sheet
