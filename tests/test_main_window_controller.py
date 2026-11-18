from types import SimpleNamespace

from sllkgui.guis.windows.main_window.controller import (
    MainWindowController,
    PageRouterController,
    SettingsController,
)


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


def test_settings_controller_cycles_expected_theme_sequence():
    style_calls = []

    class _Styles:
        def __init__(self):
            self.style = "demo-style"

    window = SimpleNamespace(
        ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda style: style_calls.append(style)))
    )

    from sllkgui.appcore import ThemeManager

    manager = ThemeManager()  # 独立实例，不污染全局单例
    controller = SettingsController(window=window, theme_manager=manager, style_factory=_Styles)

    controller.cycle_theme()
    controller.cycle_theme()
    controller.cycle_theme()

    assert style_calls == ["demo-style", "demo-style", "demo-style"]
    assert manager.current() == "default"  # default -> eye -> bright -> default


def test_open_settings_page_delegates_to_settings_controller():
    controller = object.__new__(MainWindowController)
    calls: list[tuple[str, str]] = []
    controller.settings_controller = SimpleNamespace(
        open_settings_page=lambda plugin_id, page_id="": calls.append((plugin_id, page_id)) or True
    )

    assert controller.open_settings_page("com.example.plugin", "com.example.plugin")
    assert calls == [("com.example.plugin", "com.example.plugin")]


def test_settings_controller_builds_plugin_page_item_id():
    controller = object.__new__(SettingsController)
    controller._settings_window = None
    opened: list[str] = []

    class _FakeSettingsWindow:
        def show_page(self, item_id):
            opened.append(item_id)
            return True

    def fake_open_settings_window():
        controller._settings_window = _FakeSettingsWindow()
        return True

    controller.open_settings_window = fake_open_settings_window

    assert controller.open_settings_page("com.example.plugin", "com.example.plugin")
    assert opened == ["plugin::com.example.plugin::com.example.plugin"]


def test_save_language_keeps_settings_window_open(monkeypatch):
    from sllkgui.appcore import ThemeManager
    from sllkgui.guis import language_service

    class _FakeSettingsWindow:
        def __init__(self):
            self.refreshed = 0
            self.closed = False

        def refresh_language(self):
            self.refreshed += 1

        def isVisible(self):
            return not self.closed

        def close(self):
            self.closed = True

    window = SimpleNamespace(
        ui=SimpleNamespace(
            window=SimpleNamespace(setStyleSheet=lambda _style: None),
            title_bar=SimpleNamespace(findChild=lambda *_args: None),
        )
    )
    controller = SettingsController(window=window, theme_manager=ThemeManager())
    fake = _FakeSettingsWindow()
    controller._settings_window = fake
    monkeypatch.setattr(language_service, "apply_language", lambda language, window=None: language)

    controller._apply_saved_settings({"core.interface.language": "en_us"})

    assert controller._settings_window is fake
    assert fake.refreshed == 1
    assert fake.isVisible()
