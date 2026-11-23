"""四向抽屉的 Static / Overlay 模式回归（offscreen）。

``drawer_mode`` 是全局开关：static 时抽屉占布局、压缩内容区；overlay 时抽屉
脱离开布局、浮在内容区之上，内容区尺寸不变。四个方向（左 / 右 / 上 / 下）
共用同一份配置，``menu_mode`` 仍只控制左侧图标菜单。

右侧抽屉自 3.0 起不再内置设置面板：宿主可通过
``DrawerLayout.attach_right(panel)`` 注入任意面板，这里用一个桩面板验证
两种模式下的挂载行为。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMainWindow, QWidget

from sllkgui.appcore import (
    AppLanguages,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_app_context,
)
from sllkgui.guis.windows.main_window.controller import MainWindowController
from sllkgui.guis.windows.main_window.functions import MainFunctions
from sllkgui.guis.windows.main_window.ui_main import UiMainWindow

DEFAULT_PANEL_WIDTH = 360


class _StubRightPanel(QWidget):
    """替代已删除的设置抽屉：只实现 DrawerLayout 需要的最小协议。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._embedded = False
        self._open = False
        self.setFixedWidth(DEFAULT_PANEL_WIDTH)

    def set_embedded(self, value: bool) -> None:
        self._embedded = bool(value)

    def is_embedded(self) -> bool:
        return self._embedded

    def open(self) -> None:
        self._open = True
        self.show()

    def close(self) -> None:
        self._open = False
        self.hide()

    def is_open(self) -> bool:
        return self._open

    def hide(self) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._open = False
        super().hide()


@pytest.fixture
def window(qapp):
    """真实主窗口骨架（不加载插件：抽屉模式只依赖四个容器）。"""
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
    yield host
    host.close()
    host.deleteLater()


def _wait_animation():
    QTest.qWait(max(AppSettings.time_animation, AppSettings.overlay.drawer_duration) + 220)


def _content_size(window):
    frame = window.ui.content_area_frame
    return frame.width(), frame.height()


# ----------------------------------------------------------------------
# Static：四个抽屉都在布局里占位
# ----------------------------------------------------------------------
def test_static_mode_left_and_right_drawers_occupy_layout(window):
    MainFunctions.set_drawer_mode(window, "static")
    assert MainFunctions.drawer_mode(window) == "static"

    drawer = window._drawer_layout
    panel = _StubRightPanel(window.ui.content_area_frame)
    drawer.attach_right(panel)
    assert panel.is_embedded()
    assert window.ui.right_column_frame.minimumWidth() == AppSettings.right_column_size.minimum

    MainFunctions.toggle_left_column(window)
    _wait_animation()
    assert window.ui.left_column_frame.minimumWidth() == AppSettings.left_column_size.maximum
    assert MainFunctions.left_column_is_visible(window)


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


def test_overlay_mode_right_panel_floats_without_resizing_content(window):
    """右侧抽屉浮动时不压缩内容区；面板由宿主注入，基座不再内置设置页。"""
    MainFunctions.set_drawer_mode(window, "overlay")
    drawer = window._drawer_layout
    panel = _StubRightPanel(window.ui.content_area_frame)
    panel.show()
    drawer.attach_right(panel)

    width_before, height_before = _content_size(window)
    panel.open()
    _wait_animation()

    assert drawer.right_is_open()
    assert panel.isVisible()
    assert not panel.is_embedded()
    assert panel.width() == DEFAULT_PANEL_WIDTH
    assert window.ui.right_column_frame.width() == AppSettings.right_column_size.minimum
    assert _content_size(window) == (width_before, height_before)

    panel.close()
    _wait_animation()
    assert not drawer.right_is_open()
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
