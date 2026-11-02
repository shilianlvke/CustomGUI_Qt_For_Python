"""四向抽屉（栏目）契约：结构同构、命名一致、开合动画统一。

左列（``CLeftColumn``）与右列（``Ui_RightColumn``）是基座既有栏目，用法不变；
顶列 / 底列（``CTopColumn`` / ``CBottomColumn``）与之同构，开合动画只是把主轴
从宽度换成了高度。
"""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QWidget

from customgui.appcore import AppSettings
from customgui.appcore.app.main_window_use_cases import MainWindowButtonUseCase
from customgui.guicore import CBottomColumn, CLeftColumn, CTopColumn, Styles
from customgui.guis.windows.main_window.controller import ColumnController
from customgui.guis.windows.main_window.functions import MainFunctions


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeWindow:
    """只带 ui 的窗口替身：四个栏目框用真实 QFrame，属性动画才有意义。"""

    def __init__(self):
        self.ui = SimpleNamespace(
            left_column_frame=QFrame(),
            right_column_frame=QFrame(),
            top_column_frame=QFrame(),
            bottom_column_frame=QFrame(),
        )


def _wait_animation():
    QTest.qWait(AppSettings.time_animation + 80)


# ----------------------------------------------------------------------
# 结构与命名（与 CLeftColumn 同构）
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "factory, prefix, close_name",
    [
        (CTopColumn, "CTopColumn", "btn_close_top_column"),
        (CBottomColumn, "CBottomColumn", "btn_close_bottom_column"),
    ],
)
def test_top_bottom_columns_mirror_left_column(qapp, factory, prefix, close_name):
    host = QWidget()
    host.show()
    QTest.qWait(30)

    column = factory(host, "software.info", 18, "", "", AppSettings.family)
    assert column.title_frame.minimumHeight() == 47  # 与左列相同的标题条高度
    assert column.title_bg_frame.objectName() == f"{prefix}Title_Frame"
    assert column.title_label.objectName() == f"{prefix}Title_Label"
    assert column.icon_frame.objectName() == f"{prefix}Icon_Frame"
    assert column.btn_frame.objectName() == f"{prefix}Btn_Frame"
    assert column.content_frame.objectName() == f"{prefix}Content_Frame"
    assert column.btn_close.objectName() == close_name
    # menus 堆栈与左列同构（menus.menus 为内容堆栈）
    assert column.menus.menus is not None
    assert column.menus.menu_1 is not None

    # 标题与语言键
    assert column.title_label.text() == "software.info"
    column.set_title("plain.title")
    assert column.title_label.text() == "plain.title"

    # 左列回归：同样的对象名约定仍然成立
    left = CLeftColumn(host, "software.info", 18, "", "", AppSettings.family)
    assert left.title_frame.minimumHeight() == 47
    assert left.title_bg_frame.objectName() == "CLeftColumnTitle_Frame"
    assert left.btn_close.objectName() == "btn_close_left_column"


def test_styles_cover_all_four_columns():
    style = Styles().style
    for prefix in ("CLeftColumn", "CTopColumn", "CBottomColumn"):
        assert f"#{prefix}Title_Frame" in style
        assert f"#{prefix}Title_Label" in style
        assert f"#{prefix}Content_Frame" in style


def test_region_card_rule_is_shared():
    """内容区与四向抽屉共用同一张区域背景卡片规则（同 objectName 同规则）。"""
    style = Styles().style
    assert "#CRegion_Card_Frame" in style
    # 规则只出现一次：五个区域容器复用同一条规则，样式天然一致
    assert style.count("#CRegion_Card_Frame {") == 1


def test_main_window_region_frames_share_card_name(qapp):
    """五个区域容器（内容 + 四向抽屉）都挂 CRegion_Card_Frame。"""
    from PySide6.QtWidgets import QMainWindow

    from customgui.appcore import AppLanguages, AppSettings, AppThemes, ColorPalette, Language, get_app_context
    from customgui.guis.windows.main_window.ui_main import UiMainWindow

    # 装配真实主窗口 UI 需要语言包（左列菜单读取 Language.UI）
    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)

    window = QMainWindow()
    ui = UiMainWindow()
    ui.setup_ui(window)
    try:
        for name in (
            "content_area_left_frame",
            "left_column_frame",
            "right_column_frame",
            "top_column_frame",
            "bottom_column_frame",
        ):
            frame = getattr(ui, name)
            assert frame.objectName() == "CRegion_Card_Frame", name
    finally:
        window.deleteLater()


# ----------------------------------------------------------------------
# 开合动画（顶/底与左/右同一套规则，主轴换成高度）
# ----------------------------------------------------------------------
def test_toggle_top_column_animates_height(qapp):
    window = _FakeWindow()
    top = window.ui.top_column_frame
    bottom = window.ui.bottom_column_frame
    top.resize(400, 0)
    bottom.resize(400, 0)

    MainFunctions.toggle_top_column(window)
    _wait_animation()
    assert top.minimumHeight() == AppSettings.top_column_size.maximum
    assert top.maximumHeight() == AppSettings.top_column_size.maximum  # min/max 成对，避免布局病态
    assert bottom.minimumHeight() == AppSettings.bottom_column_size.minimum
    assert bottom.maximumHeight() == AppSettings.bottom_column_size.minimum

    # 关闭：模拟布局把实际高度撑开后再切一次
    top.resize(400, AppSettings.top_column_size.maximum)
    MainFunctions.toggle_top_column(window)
    _wait_animation()
    assert top.minimumHeight() == AppSettings.top_column_size.minimum
    assert top.maximumHeight() == AppSettings.top_column_size.minimum


def test_opening_bottom_column_closes_top(qapp):
    window = _FakeWindow()
    top = window.ui.top_column_frame
    bottom = window.ui.bottom_column_frame
    top.resize(400, AppSettings.top_column_size.maximum)
    bottom.resize(400, 0)

    MainFunctions.toggle_bottom_column(window)
    _wait_animation()
    assert bottom.minimumHeight() == AppSettings.bottom_column_size.maximum
    assert top.minimumHeight() == AppSettings.top_column_size.minimum


def test_toggle_left_column_regression(qapp):
    """左列既有开合行为不变：动画仍是宽度主轴。"""
    window = _FakeWindow()
    left = window.ui.left_column_frame
    right = window.ui.right_column_frame
    left.resize(0, 500)
    right.resize(0, 500)

    MainFunctions.toggle_left_column(window)
    _wait_animation()
    assert left.minimumWidth() == AppSettings.left_column_size.maximum
    assert right.minimumWidth() == AppSettings.right_column_size.minimum


def test_column_visibility_helpers(qapp):
    window = _FakeWindow()
    window.ui.top_column_frame.resize(400, 0)
    window.ui.bottom_column_frame.resize(400, 200)
    assert MainFunctions.top_column_is_visible(window) is False
    assert MainFunctions.bottom_column_is_visible(window) is True


# ----------------------------------------------------------------------
# 关闭按钮路由（与 btn_close_left_column 同一条链路）
# ----------------------------------------------------------------------
def test_close_button_names_map_to_actions():
    for name in ("btn_close_top_column", "btn_close_bottom_column"):
        decision = MainWindowButtonUseCase.decide(name, route=None)
        assert decision.kind == "action"
        assert decision.payload == name


def test_column_controller_toggles_on_close_button():
    calls = []
    controller = ColumnController(
        window=object(),
        main_functions=SimpleNamespace(
            toggle_top_column=lambda w: calls.append("top"),
            toggle_bottom_column=lambda w: calls.append("bottom"),
        ),
    )

    controller.handle_top_column_close("btn_close_top_column")
    controller.handle_bottom_column_close("btn_close_bottom_column")
    assert calls == ["top", "bottom"]
