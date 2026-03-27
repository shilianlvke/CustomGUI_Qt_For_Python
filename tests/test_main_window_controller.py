"""模块说明。"""

from types import SimpleNamespace

import pytest

from GUI.windows.main_window.controller import MainWindowController, PageRouterController, ThemeController


class _StubMainFunctions:
    """类：_StubMainFunctions。

    职责:
    - 提供 _StubMainFunctions 相关能力。
    """

    @staticmethod
    def set_page(window: SimpleNamespace, page: object) -> None:
        """函数：set_page。"""
        window.selected_page = page

    @staticmethod
    def get_title_bar_btn(_window: object, object_name: str) -> object:
        """函数：get_title_bar_btn。"""
        raise AttributeError(object_name)


class _FakeButton:
    """类：_FakeButton。"""

    def __init__(self, name: str) -> None:
        """函数：__init__。"""
        self._name = name

    def objectName(self) -> str:  # noqa: N802
        """函数：objectName。"""
        return self._name


def _make_window_for_router() -> tuple[SimpleNamespace, dict[str, str | None], dict[str, str | None]]:
    """函数：_make_window_for_router。"""
    selected = {"btn": None}
    title = {"text": None}

    def _find_child(_cls: object, page_name: str) -> str:
        """函数：_find_child。"""
        return page_name

    window = SimpleNamespace(
        ui=SimpleNamespace(
            left_menu=SimpleNamespace(select_only_one=lambda btn_name: selected.update({"btn": btn_name})),
            load_pages=SimpleNamespace(pages=SimpleNamespace(findChild=_find_child)),
            title_bar=SimpleNamespace(set_title=lambda text: title.update({"text": text})),
        ),
    )
    return window, selected, title


def test_page_router_switch_page_routes_target_widget() -> None:
    """测试用例：test_page_router_switch_page_routes_target_widget。"""
    window, selected, title = _make_window_for_router()

    def _routes(_language: object) -> dict[str, tuple[str, str]]:
        return {"btn_home": ("home_page", "Home")}

    router = PageRouterController(
        window=window,
        main_functions=_StubMainFunctions,
        language=None,
        get_routes=_routes,
    )

    route = router.route_for("btn_home")
    if route != ("home_page", "Home"):
        pytest.fail("Assertion failed")

    router.switch_page("btn_home", route[0], route[1])

    if selected["btn"] != "btn_home":
        pytest.fail("Assertion failed")
    if title["text"] != "Home":
        pytest.fail("Assertion failed")
    if window.selected_page != "home_page":
        pytest.fail("Assertion failed")


def test_theme_controller_cycles_expected_theme_sequence() -> None:
    """测试用例：test_theme_controller_cycles_expected_theme_sequence。"""
    style_calls = []
    updates = []

    class _ColorPalette:
        """类：_ColorPalette。"""

        @staticmethod
        def update(data: dict[str, str]) -> None:
            """函数：update。"""
            updates.append(data)

    themes = {
        "eye": SimpleNamespace(data={"theme": "eye"}),
        "bright": SimpleNamespace(data={"theme": "bright"}),
        "default": SimpleNamespace(data={"theme": "default"}),
    }

    class _Styles:
        """类：_Styles。"""

        def __init__(self) -> None:
            """函数：__init__。"""
            self.style = "demo-style"

    def _set_style(style: str) -> None:
        style_calls.append(style)

    window = SimpleNamespace(
        ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=_set_style)),
    )

    controller = ThemeController(window=window, color_palette=_ColorPalette, app_themes=themes, style_factory=_Styles)

    controller.cycle_theme()
    controller.cycle_theme()
    controller.cycle_theme()

    if updates != [{"theme": "eye"}, {"theme": "bright"}, {"theme": "default"}]:
        pytest.fail("Assertion failed")
    if style_calls != ["demo-style", "demo-style", "demo-style"]:
        pytest.fail("Assertion failed")


class _PluginDispatchRegistry:
    """类：_PluginDispatchRegistry。"""

    def __init__(self, calls: list[tuple[str, object, str]]) -> None:
        """函数：__init__。"""
        self._calls = calls

    def execute_command(self, command_id: str, window: object, btn: object) -> None:
        """函数：execute_command。"""
        self._calls.append((command_id, window, btn.objectName()))


def _build_controller_for_plugin_dispatch(calls: list[tuple[str, object, str]]) -> MainWindowController:
    """函数：_build_controller_for_plugin_dispatch。"""
    window = SimpleNamespace(
        ui=SimpleNamespace(
            left_menu=SimpleNamespace(deselect_all_tab=lambda: None),
            title_bar=SimpleNamespace(),
        ),
    )
    controller = MainWindowController(
        window=window,
        main_functions=_StubMainFunctions,
        plugin_registry_getter=lambda: _PluginDispatchRegistry(calls),
        event_recorder=lambda *_args, **_kwargs: None,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
    )
    controller.page_router = SimpleNamespace(route_for=lambda _name: None, switch_page=lambda *_args: None)
    controller.column_controller = SimpleNamespace(
        handle_info_button=lambda *_args: None,
        handle_more_button=lambda *_args: None,
        handle_top_settings_button=lambda *_args: None,
    )
    controller.theme_controller = SimpleNamespace(cycle_theme=lambda: None)
    return controller


def test_main_window_controller_dispatches_plugin_command_when_unhandled() -> None:
    """测试用例：test_main_window_controller_dispatches_plugin_command_when_unhandled。"""
    calls: list[tuple[str, object, str]] = []
    controller = _build_controller_for_plugin_dispatch(calls)

    btn = _FakeButton("cmd_custom")
    controller.handle_button(btn)
    assert calls
    assert calls[0][0] == "cmd_custom"
