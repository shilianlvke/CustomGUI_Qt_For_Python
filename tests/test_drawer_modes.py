"""四向抽屉的 Static / Overlay 模式回归（offscreen）。

``drawer_mode`` 是全局开关：static 时抽屉占布局、压缩内容区；overlay 时抽屉
脱离开布局、浮在内容区之上，内容区尺寸不变。四个方向（左 / 右 / 上 / 下）
共用同一份配置，``menu_mode`` 仍只控制左侧图标菜单。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow

from sllkgui.appcore import (
    AppLanguages,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_app_context,
)
from sllkgui.guicore.window.app_configurator import CAppConfigurator
from sllkgui.guis.windows.main_window.controller import MainWindowController, ThemeController
from sllkgui.guis.windows.main_window.functions import MainFunctions
from sllkgui.guis.windows.main_window.ui_main import UiMainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    """真实主窗口骨架（不加载 apps：抽屉模式只依赖四个容器）。"""
    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)

    host = QMainWindow()
    ui = UiMainWindow()
    ui.setup_ui(host)
    host.ui = ui
    host.controller = MainWindowController(host)
    # 外观面板默认惰性创建；抽屉模式用例需要它立即存在
    host.controller._ensure_theme_config()
    host.resize(1200, 760)
    host.show()
    QTest.qWait(80)
    yield host
    host.close()
    host.deleteLater()


def test_appearance_panel_is_created_on_first_open(qapp):
    """外观抽屉惰性创建：启动时为空，首次点击才构建并接入抽屉。"""
    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)

    host = QMainWindow()
    ui = UiMainWindow()
    ui.setup_ui(host)
    host.ui = ui
    host.controller = MainWindowController(host)
    host.resize(1200, 760)
    host.show()
    QTest.qWait(80)
    try:
        assert ui.theme_config is None
        host.controller.theme_controller.toggle_theme_drawer()
        _wait_animation()
        assert ui.theme_config is not None
        assert ui.theme_config.isVisible()
        assert ui.right_column_frame.minimumWidth() == AppSettings.right_column_size.maximum
    finally:
        host.close()
        host.deleteLater()


def _wait_animation():
    QTest.qWait(max(AppSettings.time_animation, AppSettings.overlay.drawer_duration) + 220)


def _content_size(window):
    frame = window.ui.content_area_frame
    return frame.width(), frame.height()


# ----------------------------------------------------------------------
# 外观抽屉里的抽屉模式控件
# ----------------------------------------------------------------------
def test_configurator_drawer_mode_signal(qapp):
    from PySide6.QtWidgets import QWidget

    host = QWidget()
    host.resize(900, 640)
    host.show()
    panel = CAppConfigurator(host)
    modes: list[str] = []
    panel.drawerModeChanged.connect(modes.append)
    try:
        assert panel.drawer_mode() == "static"
        panel.set_drawer_mode("overlay")
        assert panel.drawer_mode() == "overlay"
        assert modes == ["overlay"]
        panel.set_drawer_mode("overlay")
        assert modes == ["overlay"], "重复设置同一模式不应再次发信号"
        panel.set_drawer_mode("static")
        assert modes == ["overlay", "static"]
    finally:
        panel.deleteLater()
        host.deleteLater()


# ----------------------------------------------------------------------
# Static：四个抽屉都在布局里占位
# ----------------------------------------------------------------------
def test_static_mode_left_and_right_drawers_occupy_layout(window):
    MainFunctions.set_drawer_mode(window, "static")
    assert MainFunctions.drawer_mode(window) == "static"
    assert window.ui.theme_config.is_embedded()
    assert window.ui.theme_menu is window.ui.theme_config

    MainFunctions.toggle_left_column(window)
    _wait_animation()
    assert window.ui.left_column_frame.minimumWidth() == AppSettings.left_column_size.maximum
    assert MainFunctions.left_column_is_visible(window)

    controller = ThemeController(window)
    controller.toggle_theme_drawer()
    _wait_animation()
    assert window.ui.right_column_frame.minimumWidth() == AppSettings.right_column_size.maximum
    assert window.ui.theme_config.isVisible()
    assert controller._theme_drawer_active()

    controller.toggle_theme_drawer()
    _wait_animation()
    assert window.ui.right_column_frame.minimumWidth() == AppSettings.right_column_size.minimum
    assert not controller._theme_drawer_active()


def test_static_mode_top_and_bottom_drawers_occupy_layout(window):
    MainFunctions.set_drawer_mode(window, "static")
    MainFunctions.toggle_top_column(window)
    _wait_animation()
    assert window.ui.top_column_frame.minimumHeight() == AppSettings.top_column_size.maximum
    assert MainFunctions.top_column_is_visible(window)

    # 同一主轴只保留一个：打开底部会收起顶部
    MainFunctions.toggle_bottom_column(window)
    _wait_animation()
    assert window.ui.bottom_column_frame.minimumHeight() == AppSettings.bottom_column_size.maximum
    assert not MainFunctions.top_column_is_visible(window)
    assert MainFunctions.bottom_column_is_visible(window)


# ----------------------------------------------------------------------
# Overlay：四个抽屉浮在内容区之上，内容区尺寸不变
# ----------------------------------------------------------------------
def test_overlay_mode_left_and_top_bottom_float_without_resizing_content(window):
    MainFunctions.set_drawer_mode(window, "overlay")
    drawer = window._drawer_layout
    assert drawer.mode() == "overlay"
    assert not window.ui.theme_config.is_embedded()
    assert window.ui.theme_config.isHidden()
    for frame in (
        window.ui.left_column_frame,
        window.ui.top_column_frame,
        window.ui.bottom_column_frame,
    ):
        assert frame.parentWidget() is window.ui.window

    width_before, height_before = _content_size(window)
    MainFunctions.toggle_left_column(window)
    _wait_animation()
    assert drawer.is_open("left")
    assert window.ui.left_column_frame.width() == AppSettings.left_column_size.maximum
    assert window.ui.left_column_frame.x() == window.ui.content_area_frame.mapTo(window.ui.window, window.ui.content_area_frame.rect().topLeft()).x()
    assert _content_size(window) == (width_before, height_before)

    MainFunctions.toggle_top_column(window)
    _wait_animation()
    assert drawer.is_open("top")
    assert window.ui.top_column_frame.height() == AppSettings.top_column_size.maximum
    assert _content_size(window) == (width_before, height_before)

    MainFunctions.toggle_bottom_column(window)
    _wait_animation()
    assert drawer.is_open("bottom")
    assert not drawer.is_open("top")
    assert window.ui.bottom_column_frame.height() == AppSettings.bottom_column_size.maximum
    assert _content_size(window) == (width_before, height_before)


def test_overlay_mode_right_drawer_floats_without_resizing_content(window):
    MainFunctions.set_drawer_mode(window, "overlay")
    controller = ThemeController(window)
    width_before, height_before = _content_size(window)

    controller.toggle_theme_drawer()
    _wait_animation()
    panel = window.ui.theme_config
    assert panel.is_open()
    assert panel.isVisible()
    assert panel.width() == CAppConfigurator.DEFAULT_WIDTH
    assert window.ui.right_column_frame.width() == AppSettings.right_column_size.minimum
    assert _content_size(window) == (width_before, height_before)

    controller.toggle_theme_drawer()
    _wait_animation()
    assert not panel.is_open()
    assert not panel.isVisible()


# ----------------------------------------------------------------------
# 运行期切换：保留已展开的抽屉
# ----------------------------------------------------------------------
def test_switching_mode_preserves_open_left_drawer(window):
    MainFunctions.set_drawer_mode(window, "static")
    MainFunctions.toggle_left_column(window)
    _wait_animation()
    assert MainFunctions.left_column_is_visible(window)

    MainFunctions.set_drawer_mode(window, "overlay")
    drawer = window._drawer_layout
    assert drawer.mode() == "overlay"
    assert drawer.is_open("left")
    assert window.ui.left_column_frame.isVisible()
    assert window.ui.left_column_frame.width() == AppSettings.left_column_size.maximum
    assert window.ui.window.layout.indexOf(window.ui.left_column_frame) < 0

    MainFunctions.set_drawer_mode(window, "static")
    assert drawer.mode() == "static"
    assert MainFunctions.left_column_is_visible(window)
    assert window.ui.window.layout.indexOf(window.ui.left_column_frame) >= 0
    assert window.ui.left_column_frame.minimumWidth() == AppSettings.left_column_size.maximum


def test_static_mode_restores_overlay_panels_to_layouts(window):
    MainFunctions.set_drawer_mode(window, "overlay")
    drawer = window._drawer_layout
    MainFunctions.toggle_top_column(window)
    _wait_animation()
    assert drawer.is_open("top")

    MainFunctions.set_drawer_mode(window, "static")
    assert window.ui.right_app_layout.indexOf(window.ui.top_column_frame) >= 0
    assert window.ui.top_column_frame.minimumHeight() == AppSettings.top_column_size.maximum
    assert window.ui.top_column_frame.graphicsEffect() is None
