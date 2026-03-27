from types import SimpleNamespace

from GUI.windows.main_window.controller import ColumnController, MainWindowController, PageRouterController


class _FakeButton:
    """类：_FakeButton。

    职责:
    - 提供 _FakeButton 相关能力。
    """
    def __init__(self, name):
        "函数：__init__。"
        self._name = name

    def objectName(self):
        "函数：objectName。"
        return self._name


class _ToggleButton:
    "类：_ToggleButton。"
    def __init__(self):
        "函数：__init__。"
        self.active_calls = []

    def set_active(self, flag):
        "函数：set_active。"
        self.active_calls.append(flag)


class _MainFunctionStub:
    "类：_MainFunctionStub。"
    def __init__(self):
        "函数：__init__。"
        self.left_visible = False
        self.right_visible = False
        self.left_toggle_count = 0
        self.right_toggle_count = 0
        self.left_menu_payloads = []
        self.top_button = _ToggleButton()
        self.left_settings_button = _ToggleButton()

    def set_page(self, window, page):
        "函数：set_page。"
        window._selected_page = page

    def get_title_bar_btn(self, _window, object_name):
        "函数：get_title_bar_btn。"
        if object_name == "btn_top_settings":
            return self.top_button
        raise AttributeError(object_name)

    def left_column_is_visible(self, _window):
        "函数：left_column_is_visible。"
        return self.left_visible

    def toggle_left_column(self, _window):
        "函数：toggle_left_column。"
        self.left_visible = not self.left_visible
        self.left_toggle_count += 1

    def set_left_column_menu(self, _window, menu, title, icon_path):
        "函数：set_left_column_menu。"
        self.left_menu_payloads.append((menu, title, icon_path))

    def right_column_is_visible(self, _window):
        "函数：right_column_is_visible。"
        return self.right_visible

    def toggle_right_column(self, _window):
        "函数：toggle_right_column。"
        self.right_visible = not self.right_visible
        self.right_toggle_count += 1

    def get_left_menu_btn(self, _window, object_name):
        "函数：get_left_menu_btn。"
        if object_name == "btn_settings":
            return self.left_settings_button
        raise AttributeError(object_name)


class _LeftMenuStub:
    "类：_LeftMenuStub。"
    def __init__(self):
        "函数：__init__。"
        self.selected_page_btn = None
        self.selected_tab_btn = None
        self.deselect_count = 0

    def select_only_one(self, btn_name):
        "函数：select_only_one。"
        self.selected_page_btn = btn_name

    def select_only_one_tab(self, btn_name):
        "函数：select_only_one_tab。"
        self.selected_tab_btn = btn_name

    def deselect_all_tab(self):
        "函数：deselect_all_tab。"
        self.deselect_count += 1


def _build_window():
    "函数：_build_window。"
    left_menu = _LeftMenuStub()
    title_state = {"text": None}

    def _find_child(_cls, page_name):
        "函数：_find_child。"
        return page_name

    window = SimpleNamespace(
        ui=SimpleNamespace(
            left_menu=left_menu,
            title_bar=SimpleNamespace(set_title=lambda text: title_state.update({"text": text})),
            load_pages=SimpleNamespace(pages=SimpleNamespace(findChild=_find_child)),
            left_column=SimpleNamespace(menus=SimpleNamespace(menu_1="menu_1", menu_2="menu_2")),
            window=SimpleNamespace(setStyleSheet=lambda _style: None),
        )
    )
    return window, left_menu, title_state


def test_button_to_page_route_chain():
    "测试用例：test_button_to_page_route_chain。"
    window, left_menu, title_state = _build_window()
    main_functions = _MainFunctionStub()
    plugin_calls = []

    class _Registry:
        "类：_Registry。"
        def execute_command(self, command_id, _window, _btn):
            "函数：execute_command。"
            plugin_calls.append(command_id)

    controller = MainWindowController(
        window=window,
        main_functions=main_functions,
        plugin_registry_getter=lambda: _Registry(),
        event_recorder=lambda *args, **kwargs: None,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
    )
    controller.page_router = PageRouterController(
        window=window,
        main_functions=main_functions,
        language=None,
        get_routes=lambda _language: {"btn_home": ("home_page", "Home")},
    )

    controller.handle_button(_FakeButton("btn_home"))

    assert window._selected_page == "home_page"
    assert left_menu.selected_page_btn == "btn_home"
    assert title_state["text"] == "Home"
    assert plugin_calls == []


def test_button_to_column_action_chain():
    "测试用例：test_button_to_column_action_chain。"
    window, left_menu, _title_state = _build_window()
    main_functions = _MainFunctionStub()

    controller = MainWindowController(
        window=window,
        main_functions=main_functions,
        plugin_registry_getter=lambda: SimpleNamespace(execute_command=lambda *_args: None),
        event_recorder=lambda *args, **kwargs: None,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
    )
    controller.page_router = PageRouterController(
        window=window,
        main_functions=main_functions,
        language=None,
        get_routes=lambda _language: {},
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

    assert left_menu.selected_tab_btn == "btn_info"
    assert main_functions.left_toggle_count == 1
    assert main_functions.left_menu_payloads
    menu, _title, _icon = main_functions.left_menu_payloads[-1]
    assert menu == "menu_2"


def test_unhandled_button_falls_back_to_plugin_command_chain():
    "测试用例：test_unhandled_button_falls_back_to_plugin_command_chain。"
    window, _left_menu, _title_state = _build_window()
    main_functions = _MainFunctionStub()
    plugin_calls = []

    class _Registry:
        "类：_Registry。"
        def execute_command(self, command_id, _window, _btn):
            "函数：execute_command。"
            plugin_calls.append(command_id)

    controller = MainWindowController(
        window=window,
        main_functions=main_functions,
        plugin_registry_getter=lambda: _Registry(),
        event_recorder=lambda *args, **kwargs: None,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
    )
    controller.page_router = PageRouterController(
        window=window,
        main_functions=main_functions,
        language=None,
        get_routes=lambda _language: {},
    )

    controller.handle_button(_FakeButton("cmd_custom"))

    assert plugin_calls == ["cmd_custom"]

