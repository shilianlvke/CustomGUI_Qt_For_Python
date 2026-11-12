from types import SimpleNamespace

from sllkgui.guis.windows.main_window.controller import PageRouterController, ThemeController


class _StubMainFunctions:
    @staticmethod
    def set_page(window, page, **_kwargs):
        window._selected_page = page

    @staticmethod
    def get_title_bar_btn(window, object_name):
        raise AttributeError(object_name)


class _FakeButton:
    def __init__(self, name):
        self._name = name

    def objectName(self):
        return self._name


def _make_window_for_router():
    selected = {"btn": None}
    title = {"text": None}

    def _find_child(_cls, page_name):
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
    style_calls = []

    class _Styles:
        def __init__(self):
            self.style = "demo-style"

    window = SimpleNamespace(
        ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda style: style_calls.append(style)))
    )

    from sllkgui.appcore import ThemeManager

    manager = ThemeManager()  # 独立实例，不污染全局单例
    controller = ThemeController(window=window, theme_manager=manager, style_factory=_Styles)

    controller.cycle_theme()
    controller.cycle_theme()
    controller.cycle_theme()

    assert style_calls == ["demo-style", "demo-style", "demo-style"]
    assert manager.current() == "default"  # default -> eye -> bright -> default
