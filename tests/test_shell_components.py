"""Sakai 壳层组件测试（offscreen）。

覆盖主题配置抽屉的开合与主题信号、顶栏的搜索 / 通知 / 用户菜单信号，
以及嵌套侧边菜单的展开与单选激活。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from customgui.appcore import get_theme_manager
from customgui.guicore.window.app_configurator import CAppConfigurator
from customgui.guicore.window.app_menu import CAppMenu
from customgui.guicore.window.app_topbar import CAppTopbar


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
    QTest.qWait(320)


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
