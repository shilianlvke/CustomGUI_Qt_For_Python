from types import SimpleNamespace

from GUI.windows.main_window.controller import MainWindowController, PageRouterController, ThemeController


class _StubMainFunctions:
    """类：_StubMainFunctions。

    职责:
    - 提供 _StubMainFunctions 相关能力。
    """
    @staticmethod
    def set_page(window, page):
        "函数：set_page。"
        window._selected_page = page

    @staticmethod
    def get_title_bar_btn(window, object_name):
        "函数：get_title_bar_btn。"
        raise AttributeError(object_name)


class _FakeButton:
    "类：_FakeButton。"
    def __init__(self, name):
        "函数：__init__。"
        self._name = name

    def objectName(self):
        "函数：objectName。"
        return self._name


def _make_window_for_router():
    "函数：_make_window_for_router。"
    selected = {"btn": None}
    title = {"text": None}

    def _find_child(_cls, page_name):
        "函数：_find_child。"
        return page_name

    window = SimpleNamespace(
        ui=SimpleNamespace(
            left_menu=SimpleNamespace(select_only_one=lambda btn_name: selected.update({"btn": btn_name})),
            load_pages=SimpleNamespace(pages=SimpleNamespace(findChild=_find_child)),
            title_bar=SimpleNamespace(set_title=lambda text: title.update({"text": text})),
        )
    )
    return window, selected, title


def test_page_router_switch_page_routes_target_widget():
    "测试用例：test_page_router_switch_page_routes_target_widget。"
    window, selected, title = _make_window_for_router()
    router = PageRouterController(
        window=window,
        main_functions=_StubMainFunctions,
        language=None,
        get_routes=lambda _language: {"btn_home": ("home_page", "Home")},
    )

    route = router.route_for("btn_home")
    assert route == ("home_page", "Home")

    router.switch_page("btn_home", route[0], route[1])

    assert selected["btn"] == "btn_home"
    assert title["text"] == "Home"
    assert window._selected_page == "home_page"


def test_theme_controller_cycles_expected_theme_sequence():
    "测试用例：test_theme_controller_cycles_expected_theme_sequence。"
    style_calls = []
    updates = []

    class _ColorPalette:
        "类：_ColorPalette。"
        @staticmethod
        def update(data):
            "函数：update。"
            updates.append(data)

    themes = {
        "eye": SimpleNamespace(data={"theme": "eye"}),
        "bright": SimpleNamespace(data={"theme": "bright"}),
        "default": SimpleNamespace(data={"theme": "default"}),
    }

    class _Styles:
        "类：_Styles。"
        def __init__(self):
            "函数：__init__。"
            self.style = "demo-style"

    window = SimpleNamespace(
        ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda style: style_calls.append(style)))
    )

    controller = ThemeController(window=window, color_palette=_ColorPalette, app_themes=themes, style_factory=_Styles)

    controller.cycle_theme()
    controller.cycle_theme()
    controller.cycle_theme()

    assert updates == [{"theme": "eye"}, {"theme": "bright"}, {"theme": "default"}]
    assert style_calls == ["demo-style", "demo-style", "demo-style"]


def test_main_window_controller_dispatches_plugin_command_when_unhandled():
    "测试用例：test_main_window_controller_dispatches_plugin_command_when_unhandled。"
    calls = []

    class _Registry:
        "类：_Registry。"
        def execute_command(self, command_id, window, btn):
            "函数：execute_command。"
            calls.append((command_id, window, btn.objectName()))

    window = SimpleNamespace(
        ui=SimpleNamespace(
            left_menu=SimpleNamespace(deselect_all_tab=lambda: None),
            title_bar=SimpleNamespace(),
        )
    )

    controller = MainWindowController(
        window=window,
        main_functions=_StubMainFunctions,
        plugin_registry_getter=lambda: _Registry(),
        event_recorder=lambda *args, **kwargs: None,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
    )
    controller.page_router = SimpleNamespace(route_for=lambda _name: None, switch_page=lambda *_args: None)
    controller.column_controller = SimpleNamespace(
        handle_info_button=lambda *_args: None,
        handle_more_button=lambda *_args: None,
        handle_top_settings_button=lambda *_args: None,
    )
    controller.theme_controller = SimpleNamespace(cycle_theme=lambda: None)

    btn = _FakeButton("cmd_custom")
    controller.handle_button(btn)

    assert calls
    assert calls[0][0] == "cmd_custom"

