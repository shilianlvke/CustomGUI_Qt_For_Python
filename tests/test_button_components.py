"""按钮组件契约：形态、尺寸、状态与主题跟随。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from sllkgui.appcore import ColorPalette, get_theme_manager
from sllkgui.guicore import CButton, CButtonGroup, CPushButton, CSplitButton
from sllkgui.guicore.custom_ui.button.severity import Severity, Variant, colors_for, is_dark_theme


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
    for size, height in (("sm", 28), ("md", 32), ("lg", 40)):
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


def test_focus_ring_only_on_keyboard_focus(qapp):
    """鼠标点击（等效 CSS 的 :focus）不画焦点框，Tab 聚焦（:focus-visible）才画。"""
    host = QWidget()
    layout = QVBoxLayout(host)
    button = CButton(text="Focus")
    layout.addWidget(button)
    host.show()
    QTest.qWait(30)

    QTest.mouseClick(button, Qt.LeftButton)
    assert button.hasFocus()
    assert button._focus_visible is False

    button.clearFocus()
    button.setFocus(Qt.TabFocusReason)
    assert button._focus_visible is True

    button.set_focus_ring(False)
    assert button._focus_ring is False
    host.hide()


def test_raised_reserves_space_for_shadow(qapp):
    """阴影画在 body 之外，控件必须为它留出透明边距，否则会被裁掉。"""
    button = CButton(text="Raised", raised=True)
    assert button._body_rect().height() == 32
    assert button.height() > 32
    assert button.sizeHint().height() == button.height()

    button.set_raised(False)
    assert button.height() == 32
    assert button._body_rect().height() == 32


def test_raised_shadow_covers_every_variant(qapp):
    """Sakai 的 Rounded Text（text + raised + rounded）同样有阴影。"""
    for variant in Variant:
        button = CButton(text="X", variant=variant, raised=True, rounded=True)
        assert button._shadow_layers(), f"{variant} 缺少 raised 阴影"


def test_outlined_border_uses_theme_semantic_color(qapp):
    """Fluent 语义色来自当前主题，不再写死 PrimeVue Aura 色阶。"""
    assert is_dark_theme()
    colors = colors_for(Severity.SUCCESS, Variant.OUTLINED)
    assert colors.text.name() == QColor(ColorPalette.custom_green).name()
    assert colors.border.alpha() == 200

    get_theme_manager().apply("bright")
    colors = colors_for(Severity.SUCCESS, Variant.OUTLINED)
    assert colors.text.name() == QColor(ColorPalette.custom_green).name()
    assert colors.border.alpha() == 200


def test_split_button_menu_uses_separator(qapp):
    """分体按钮右侧点击弹出菜单（曾经因相对导入路径写错而崩）。"""
    split = CSplitButton(
        "Save",
        [("Update", "icon_refresh"), ("Delete", "icon_close"), None, ("Home", "icon_home")],
    )
    host = QWidget()
    QVBoxLayout(host).addWidget(split)
    host.show()
    QTest.qWait(30)

    split._show_menu()
    menu = split.menu()
    assert menu is not None
    # 顺序与 PrimeVue 的 items 一致，None 表示分隔线
    assert menu.entries() == ["Update", "Delete", None, "Home"]
    # 浮层外观由 CPopover 提供（与下拉字段共用），最小宽度按 Aura 的 12.5rem
    popover = split.popover()
    assert popover is not None and popover.body_width() >= 200
    assert menu.height() > 0 and menu.width() > 0
    host.hide()


def test_split_button_menu_activates_item(qapp):
    """点击菜单项要发出 actionTriggered 并关闭浮层（分隔线不可点）。"""
    split = CSplitButton("Save", [("Update", "icon_refresh"), None, ("Home", "icon_home")])
    host = QWidget()
    QVBoxLayout(host).addWidget(split)
    host.show()
    QTest.qWait(30)

    seen: list[str] = []
    split.actionTriggered.connect(seen.append)
    split._show_menu()
    menu = split.menu()
    assert menu is not None and menu.isVisible()

    # 分隔线位置（第 2 行）点了不该触发
    separator_rect = menu._rows[1][3]
    QTest.mouseClick(menu, Qt.LeftButton, pos=separator_rect.center())
    assert seen == []
    assert menu.isVisible()

    home_rect = menu._rows[2][3]
    QTest.mouseClick(menu, Qt.LeftButton, pos=home_rect.center())
    assert seen == ["Home"]
    assert not menu.isVisible()
    host.hide()


def test_loading_keeps_label(qapp):
    """Aura 的 loading 只替换前置图标，文案保留（不会让按钮看起来空掉）。"""
    button = CButton(text="Search", icon="icon_search")
    button.set_loading(True)
    assert button.is_loading()
    assert button.text() == "Search"

    image = button.grab()
    assert not image.isNull()


def _luminance(rgb: tuple[int, int, int]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _composite_over(color: QColor, base: QColor) -> tuple[int, int, int]:
    alpha = color.alphaF()
    return (
        round(color.red() * alpha + base.red() * (1 - alpha)),
        round(color.green() * alpha + base.green() * (1 - alpha)),
        round(color.blue() * alpha + base.blue() * (1 - alpha)),
    )


@pytest.mark.parametrize("theme", ["default", "bright", "dracula", "eye"])
def test_hover_fade_from_transparent_never_darkens(qapp, theme):
    """透明底按钮（text / outlined 及其圆角变体）hover 渐变时不能先变暗。

    逐分量插值 RGBA 会让 ``(0,0,0,0) -> 不透明浅色`` 的中途经过「半透明灰」，
    叠到卡片上就是先变暗再变亮——浅色主题下肉眼看到的就是 hover 时闪一下。
    改为预乘 alpha 插值后，中间帧亮度必须始终落在两端之间。
    """
    get_theme_manager().apply(theme)
    button = CButton(text="Fade", variant="text")
    card = QColor("#e2e6eb")

    for end in (QColor("#f0f9ff"), QColor("#608edb")):
        start = QColor(0, 0, 0, 0)
        base_lum = _luminance(_composite_over(start, card))
        end_lum = _luminance(_composite_over(end, card))
        for step in range(11):
            mid = button._lerp_color(start, end, step / 10)
            value = _luminance(_composite_over(mid, card))
            assert min(base_lum, end_lum) - 0.5 <= value <= max(base_lum, end_lum) + 0.5, (
                f"{theme}: t={step / 10} 中间色越界 {mid.getRgb()} -> {value:.1f}"
            )

    # 中点应当仍是目标色的色相（只是半透明），而不是被拉向黑色
    mid = button._lerp_color(QColor(0, 0, 0, 0), QColor("#f0f9ff"), 0.5)
    assert mid.alpha() in (127, 128)
    assert mid.red() > 230 and mid.green() > 235 and mid.blue() > 240
