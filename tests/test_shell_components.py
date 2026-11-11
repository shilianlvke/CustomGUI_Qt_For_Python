"""Windows Fluent Design 壳层组件测试（offscreen）。

覆盖外观配置抽屉的开合与主题 / 语言信号、顶栏的搜索 / 通知 / 用户菜单信号，
以及嵌套侧边菜单的展开与单选激活。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from sllkgui.appcore import get_theme_manager
from sllkgui.guicore.window.app_configurator import CAppConfigurator
from sllkgui.guicore.window.app_menu import CAppMenu
from sllkgui.guicore.window.app_topbar import CAppTopbar


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
    widget.resize(920, 640)
    widget.show()
    QTest.qWait(20)
    yield widget
    widget.hide()
    widget.deleteLater()


def _wait_animation():
    # 覆盖率插桩会拖慢事件循环，留足一次抽屉动画的余量
    QTest.qWait(500)


# ----------------------------------------------------------------------
# Configurator
# ----------------------------------------------------------------------
def test_configurator_open_close_and_theme_signal(host):
    panel = CAppConfigurator(host)
    changed = []
    closed = []
    panel.themeChanged.connect(changed.append)
    panel.closed.connect(lambda: closed.append(True))

    panel.open()
    _wait_animation()
    assert panel.is_open()
    assert panel.isVisible()
    assert panel.x() == host.width() - panel.width()

    assert panel.set_theme("bright")
    assert changed == ["bright"]
    assert panel.current_theme() == "bright"

    panel.close()
    assert not panel.is_open()
    _wait_animation()
    assert not panel.isVisible()
    assert closed == [True]


def test_configurator_background_accordion_expand_and_apply(host, tmp_path):
    """背景手风琴默认收起，展开后可选择图片并发出变更信号。"""
    from PySide6.QtGui import QImage

    panel = CAppConfigurator(host)
    panel.open()
    _wait_animation()
    assert not panel.is_background_expanded()
    assert not panel._background_content.isVisible()

    # 背景是独立子页：先切到“背景”再测试手风琴展开。
    panel.tabs.set_index(2)
    QTest.qWait(50)
    assert panel.stack.currentIndex() == 2
    panel.background_toggle.click()
    _wait_animation()
    assert panel.is_background_expanded()
    assert panel._background_content.isVisible()

    image_path = tmp_path / "wall.png"
    image = QImage(80, 48, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    assert image.save(str(image_path))

    changed: list[tuple[str, str]] = []
    panel.backgroundChanged.connect(lambda path, fit: changed.append((path, fit)))
    assert panel._apply_background_path(str(image_path))
    assert panel.background_path() == str(image_path)
    assert changed and changed[-1] == (str(image_path), "fill")

    fit_labels = panel._background_fit_labels()
    panel.background_fit_select.set_value(fit_labels[1])
    assert panel.background_fit() == "fit"
    assert changed[-1] == (str(image_path), "fit")

    panel.background_type_select.set_value(panel._background_type_labels()[0])
    assert panel.background_path() == ""
    assert changed[-1][0] == ""


def test_configurator_menu_mode_and_dark_mode(host):
    panel = CAppConfigurator(host)
    modes = []
    dark = []
    panel.menuModeChanged.connect(modes.append)
    panel.darkModeChanged.connect(dark.append)

    panel.set_menu_mode("overlay")
    assert panel.menu_mode() == "overlay"
    assert modes == ["overlay"]
    panel.set_menu_mode("static")
    assert modes == ["overlay", "static"]

    panel.open()
    _wait_animation()
    before = panel.dark_switch.isChecked()
    panel.dark_switch.setChecked(not before)
    assert dark[-1] is (not before)
    panel.dark_switch.setChecked(before)
    assert dark[-1] is before
    panel.close()


def test_configurator_language_selection_and_retranslate(host):
    from sllkgui.appcore import LANGUAGE_OPTIONS, Language

    panel = CAppConfigurator(host)
    picked = []
    panel.languageChanged.connect(picked.append)

    current = Language.current()
    target = next((code for code in LANGUAGE_OPTIONS if code != current), None)
    assert target is not None
    # 直接选中目标语言：发出 languageChanged，由宿主应用到窗口
    panel.language_select.selectionChanged.emit(panel._language_label(target))
    assert picked == [target]

    Language.apply("en_us")
    assert panel.header_title.text() == "Appearance"
    Language.apply(current)
    panel.deleteLater()


def test_configurator_appearance_sliders(host):
    from sllkgui.guicore import (
        MIN_WINDOW_GLASS_ALPHA,
        acrylic_transparency,
        glass_alpha,
        glass_strength,
        reset_appearance_overrides,
        set_glass_strength,
    )

    reset_appearance_overrides()
    panel = CAppConfigurator(host)
    transparency_changes = []
    strength_changes = []
    committed = []
    panel.transparencyChanged.connect(transparency_changes.append)
    panel.glassStrengthChanged.connect(strength_changes.append)
    panel.appearanceCommitted.connect(lambda: committed.append(True))
    try:
        panel.transparency_slider.setValue(35)
        assert acrylic_transparency() == 35
        assert transparency_changes[-1] == 35
        assert panel.transparency_value.text() == "35%"

        panel.glass_strength_slider.setValue(60)
        assert glass_strength() == 60
        assert strength_changes[-1] == 60
        assert panel.glass_strength_value.text() == "60%"
        # 强度越高，表面层不透明度越低（透出更多系统模糊材质）
        assert glass_alpha(0.5) == pytest.approx(0.2)
        # 窗口底色兜底：Alpha=0 会让分层窗口出现鼠标穿透
        set_glass_strength(100)
        assert glass_alpha(0.5, minimum=MIN_WINDOW_GLASS_ALPHA) == pytest.approx(MIN_WINDOW_GLASS_ALPHA)

        # 静默同步：只更新控件与运行期值，不再发预览信号
        panel.set_appearance(transparency=70, strength=80)
        assert panel.transparency() == 70
        assert panel.appearance_strength() == 80
        assert transparency_changes[-1] == 35
        assert strength_changes[-1] == 60

        panel.appearanceCommitted.emit()
        assert committed == [True]
    finally:
        reset_appearance_overrides()
        panel.deleteLater()


def test_left_settings_panel_has_three_single_screen_tabs(qapp):
    from PySide6.QtWidgets import QScrollArea

    from sllkgui.guicore.window.left_column.settings_panel import CSettingsPanel

    panel = CSettingsPanel()
    try:
        assert panel._stack.count() == 3
        assert len(panel._tabs._options) == 3
        assert not panel.findChildren(QScrollArea)
        for index in range(3):
            panel._tabs.set_index(index)
            assert panel._stack.currentIndex() == index
    finally:
        panel.deleteLater()


def test_left_column_supports_subtitle_and_language_key_title(qapp):
    from sllkgui.appcore import AppSettings, Language
    from sllkgui.guicore import CLeftColumn

    host = QWidget()
    column = CLeftColumn(
        host,
        "custom.title",
        18,
        "",
        "",
        AppSettings.family,
        text_subtitle="custom.subtitle",
    )
    try:
        assert column.title_label.text() == "custom.title"
        assert column.subtitle_label.text() == "custom.subtitle"
        column.set_title("language.UI.ui_Settings")
        assert column._title_key == "language.UI.ui_Settings"
        assert column.title_label.text() == Language.resolve_key("language.UI.ui_Settings")
    finally:
        column.deleteLater()


def test_menu_colors_theme_contrast_and_glass_surface(monkeypatch):
    import sllkgui.guicore.acrylic as acrylic_module
    from sllkgui.guicore import glass_surface, reset_appearance_overrides, set_glass_strength
    from sllkgui.guicore.custom_ui.menu.menu_list import menu_colors

    try:
        for theme in ("bright", "dracula"):
            get_theme_manager().apply(theme)
            palette = menu_colors()
            background = QColor(palette["background"])
            hover = QColor(palette["hover"])
            # 悬停行必须与菜单底色有差异（旧实现亮色主题用纯白，几乎不可见）
            assert hover.name() != background.name()
            # 强调色前景按实际对比度自动取黑/白：dracula 浅粉配近黑字，亮色主题配白字
            lightness = QColor(palette["on_accent"]).lightness()
            assert lightness < 128 if theme == "dracula" else lightness > 128

        monkeypatch.setattr(acrylic_module, "acrylic_active", lambda: True)
        set_glass_strength(0)
        assert glass_surface("#000000", 0.5).alpha() == 128
        set_glass_strength(100)
        # 浮层表面保留可读性下限，不会随强度归零
        assert glass_surface("#000000", 0.5, minimum=0.2).alpha() == 51
    finally:
        reset_appearance_overrides()
        get_theme_manager().apply("default")


# ----------------------------------------------------------------------
# Topbar
# ----------------------------------------------------------------------
def test_topbar_search_notification_and_user_signals(host):
    bar = CAppTopbar()
    bar.resize(900, bar.height())
    bar.show()
    QTest.qWait(20)

    searches = []
    notifications = []
    user_requests = []
    bar.searchChanged.connect(searches.append)
    bar.notificationsClicked.connect(lambda: notifications.append(True))
    bar.userMenuRequested.connect(lambda: user_requests.append(True))

    bar.search_box.setText("alpha")
    assert searches[-1] == "alpha"

    QTest.mouseClick(bar.notification_button, Qt.LeftButton)
    assert notifications == [True]

    QTest.mouseClick(bar.user_button, Qt.LeftButton)
    assert user_requests == [True]
    bar._user_menu.hide()

    bar.deleteLater()


def test_topbar_unread_badge_and_action_button(host):
    bar = CAppTopbar()
    bar.resize(900, bar.height())
    bar.show()
    QTest.qWait(20)

    bar.set_unread_count(5)
    assert bar.unread_count() == 5
    assert bar.notification_badge.text() == "5"
    bar.set_unread_count(0)
    assert bar.notification_badge.isHidden()

    fired = []
    bar.actionTriggered.connect(fired.append)
    button = bar.add_action_button("设置", key="settings", icon="icon_setting")
    button.click()
    assert fired == ["settings"]
    assert bar.action_buttons["settings"] is button

    bar.set_user({"name": "Ada Lovelace"})
    assert bar.user_name() == "Ada Lovelace"
    assert bar.user_button.avatar.label() == "A"
    bar.deleteLater()


# ----------------------------------------------------------------------
# App menu
# ----------------------------------------------------------------------
def _menu_items():
    return [
        {"label": "首页", "icon": "icon_home", "key": "home"},
        {
            "label": "设置",
            "icon": "icon_setting",
            "key": "settings",
            "children": [
                {"label": "个人资料", "key": "profile"},
                {"label": "安全", "key": "security", "children": [{"label": "两步验证", "key": "twofa"}]},
            ],
        },
    ]


def test_app_menu_expand_and_expanded_signal(host):
    menu = CAppMenu(items=_menu_items())
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(menu)
    QTest.qWait(20)

    expanded = []
    menu.expandedChanged.connect(lambda key, value: expanded.append((key, value)))
    top = menu.items()
    assert [item.key() for item in top] == ["home", "settings"]

    group = top[1]
    assert group.depth() == 0
    assert group.children()[0].depth() == 1
    QTest.mouseClick(group, Qt.LeftButton, pos=group.rect().center())
    assert group.is_expanded()
    assert ("settings", True) in expanded

    menu.expand_all()
    nested = group.children()[1]
    assert nested.is_expanded()
    assert any(key == "security" and value for key, value in expanded)

    menu.collapse_all()
    assert not group.is_expanded()
    assert not nested.is_expanded()


def test_app_menu_single_active_and_click_signal(host):
    menu = CAppMenu(items=_menu_items())
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(menu)
    QTest.qWait(20)

    clicked = []
    menu.itemClicked.connect(lambda item: clicked.append(item.key()))

    assert menu.set_active("profile")
    assert menu.active_key() == "profile"
    assert menu.active_item().is_active()
    assert not menu.items()[0].is_active()

    menu.expand_all()
    QTest.qWait(20)
    profile = menu.find_item("profile")
    QTest.mouseClick(profile, Qt.LeftButton, pos=profile.rect().center())
    assert clicked == ["profile"]
    assert menu.active_key() == "profile"

    assert menu.set_active("twofa")
    assert menu.active_key() == "twofa"
    assert not profile.is_active()

    assert not menu.set_active("missing")
    assert menu.active_key() is None
