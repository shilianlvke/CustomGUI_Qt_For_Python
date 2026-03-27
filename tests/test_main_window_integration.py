"""模块说明。"""

from types import SimpleNamespace

import pytest

from gui.windows.main_window.controller import ColumnController, MainWindowController, PageRouterController


class _FakeButton:
    """类：_FakeButton。

    职责:
    - 提供 _FakeButton 相关能力。
    """

    def __init__(self, name: str) -> None:
        """函数：__init__。"""
        self._name = name

    def objectName(self) -> str:  # noqa: N802
        """函数：objectName。"""
        return self._name


class _ToggleButton:
    """类：_ToggleButton。"""

    def __init__(self) -> None:
        """函数：__init__。"""
        self.active_calls = []

    def set_active(self, flag: object) -> None:
        """函数：set_active。"""
        self.active_calls.append(flag)


class _MainFunctionStub:
    """类：_MainFunctionStub。"""

    def __init__(self) -> None:
        """函数：__init__。"""
        self.left_visible = False
        self.right_visible = False
        self.left_toggle_count = 0
        self.right_toggle_count = 0
        self.left_menu_payloads = []
        self.top_button = _ToggleButton()
        self.left_settings_button = _ToggleButton()

    def set_page(self, window: SimpleNamespace, page: object) -> None:
        """函数：set_page。"""
        window.selected_page = page

    def get_title_bar_btn(self, _window: object, object_name: str) -> object:
        """函数：get_title_bar_btn。"""
        if object_name == "btn_top_settings":
            return self.top_button
        raise AttributeError(object_name)

    def left_column_is_visible(self, _window: object) -> bool:
        """函数：left_column_is_visible。"""
        return self.left_visible

    def toggle_left_column(self, _window: object) -> None:
        """函数：toggle_left_column。"""
        self.left_visible = not self.left_visible
        self.left_toggle_count += 1

    def set_left_column_menu(self, _window: object, menu: object, title: str, icon_path: str) -> None:
        """函数：set_left_column_menu。"""
        self.left_menu_payloads.append((menu, title, icon_path))

    def right_column_is_visible(self, _window: object) -> bool:
        """函数：right_column_is_visible。"""
        return self.right_visible

    def toggle_right_column(self, _window: object) -> None:
        """函数：toggle_right_column。"""
        self.right_visible = not self.right_visible
        self.right_toggle_count += 1

    def get_left_menu_btn(self, _window: object, object_name: str) -> object:
        """函数：get_left_menu_btn。"""
        if object_name == "btn_settings":
            return self.left_settings_button
        raise AttributeError(object_name)


class _LeftMenuStub:
    """类：_LeftMenuStub。"""

    def __init__(self) -> None:
        """函数：__init__。"""
        self.selected_page_btn = None
        self.selected_tab_btn = None
        self.deselect_count = 0

    def select_only_one(self, btn_name: str) -> None:
        """函数：select_only_one。"""
        self.selected_page_btn = btn_name

    def select_only_one_tab(self, btn_name: str) -> None:
        """函数：select_only_one_tab。"""
        self.selected_tab_btn = btn_name

    def deselect_all_tab(self) -> None:
        """函数：deselect_all_tab。"""
        self.deselect_count += 1


def _build_window() -> tuple[SimpleNamespace, _LeftMenuStub, dict[str, str | None]]:
    """函数：_build_window。"""
    left_menu = _LeftMenuStub()
    title_state = {"text": None}

    def _find_child(_cls: object, page_name: str) -> str:
        """函数：_find_child。"""
        return page_name

    window = SimpleNamespace(
        ui=SimpleNamespace(
            left_menu=left_menu,
            title_bar=SimpleNamespace(set_title=lambda text: title_state.update({"text": text})),
            load_pages=SimpleNamespace(pages=SimpleNamespace(findChild=_find_child)),
            left_column=SimpleNamespace(menus=SimpleNamespace(menu_1="menu_1", menu_2="menu_2")),
            window=SimpleNamespace(setStyleSheet=lambda _style: None),
        ),
    )
    return window, left_menu, title_state


def test_button_to_page_route_chain() -> None:
    """测试用例：test_button_to_page_route_chain。"""
    window, left_menu, title_state = _build_window()
    main_functions = _MainFunctionStub()
    plugin_calls = []

    def _record_event(*_args: object, **_kwargs: object) -> None:
        return

    def _debug_log(*_args: object, **_kwargs: object) -> None:
        return

    def _routes(_language: object) -> dict[str, tuple[str, str]]:
        return {"btn_home": ("home_page", "Home")}

    def _plugin_registry_getter() -> "_Registry":
        return _Registry()

    class _Registry:
        """类：_Registry。"""

        def execute_command(self, command_id: str, _window: object, _btn: object) -> None:
            """函数：execute_command。"""
            plugin_calls.append(command_id)

    controller = MainWindowController(
        window=window,
        main_functions=main_functions,
        runtime=MainWindowController.Runtime(
            plugin_registry_getter=_plugin_registry_getter,
            event_recorder=_record_event,
            logger=SimpleNamespace(debug=_debug_log),
        ),
    )
    controller.page_router = PageRouterController(
        window=window,
        main_functions=main_functions,
        language=None,
        get_routes=_routes,
    )

    controller.handle_button(_FakeButton("btn_home"))

    if window.selected_page != "home_page":
        pytest.fail("Assertion failed")
    if left_menu.selected_page_btn != "btn_home":
        pytest.fail("Assertion failed")
    if title_state["text"] != "Home":
        pytest.fail("Assertion failed")
    if plugin_calls != []:
        pytest.fail("Assertion failed")


def test_button_to_column_action_chain() -> None:
    """测试用例：test_button_to_column_action_chain。"""
    window, left_menu, _title_state = _build_window()
    main_functions = _MainFunctionStub()

    def _execute_command(*_args: object) -> None:
        return

    def _record_event(*_args: object, **_kwargs: object) -> None:
        return

    def _debug_log(*_args: object, **_kwargs: object) -> None:
        return

    def _routes(_language: object) -> dict[str, tuple[str, str]]:
        return {}

    def _plugin_registry_getter() -> SimpleNamespace:
        return SimpleNamespace(execute_command=_execute_command)

    controller = MainWindowController(
        window=window,
        main_functions=main_functions,
        runtime=MainWindowController.Runtime(
            plugin_registry_getter=_plugin_registry_getter,
            event_recorder=_record_event,
            logger=SimpleNamespace(debug=_debug_log),
        ),
    )
    controller.page_router = PageRouterController(
        window=window,
        main_functions=main_functions,
        language=None,
        get_routes=_routes,
    )
    controller.column_controller = ColumnController(
        window=window,
        main_functions=main_functions,
        language=SimpleNamespace(
            UI=SimpleNamespace(ui_Settings="Settings"),
            custom_ui=SimpleNamespace(left_column_io_test_title="IO"),
        ),
    )

    controller.handle_button(_FakeButton("btn_info"))

    if left_menu.selected_tab_btn != "btn_info":
        pytest.fail("Assertion failed")
    if main_functions.left_toggle_count != 1:
        pytest.fail("Assertion failed")
    if not (main_functions.left_menu_payloads):
        pytest.fail("Assertion failed")
    menu, _title, _icon = main_functions.left_menu_payloads[-1]
    if menu != "menu_2":
        pytest.fail("Assertion failed")


def test_unhandled_button_falls_back_to_plugin_command_chain() -> None:
    """测试用例：test_unhandled_button_falls_back_to_plugin_command_chain。"""
    window, _left_menu, _title_state = _build_window()
    main_functions = _MainFunctionStub()
    plugin_calls = []

    def _record_event(*_args: object, **_kwargs: object) -> None:
        return

    def _debug_log(*_args: object, **_kwargs: object) -> None:
        return

    def _routes(_language: object) -> dict[str, tuple[str, str]]:
        return {}

    def _plugin_registry_getter() -> "_Registry":
        return _Registry()

    class _Registry:
        """类：_Registry。"""

        def execute_command(self, command_id: str, _window: object, _btn: object) -> None:
            """函数：execute_command。"""
            plugin_calls.append(command_id)

    controller = MainWindowController(
        window=window,
        main_functions=main_functions,
        runtime=MainWindowController.Runtime(
            plugin_registry_getter=_plugin_registry_getter,
            event_recorder=_record_event,
            logger=SimpleNamespace(debug=_debug_log),
        ),
    )
    controller.page_router = PageRouterController(
        window=window,
        main_functions=main_functions,
        language=None,
        get_routes=_routes,
    )

    controller.handle_button(_FakeButton("cmd_custom"))

    if plugin_calls != ["cmd_custom"]:
        pytest.fail("Assertion failed")
