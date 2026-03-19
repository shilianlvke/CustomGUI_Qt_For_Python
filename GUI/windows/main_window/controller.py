from PySide6.QtWidgets import QWidget

from AppCore import (
    AppThemes,
    MainWindowButtonUseCase,
    ColorPalette,
    Language,
    Logger,
    PathFactory,
    get_plugin_registry,
    record_event,
)
from GuiCore import Styles

from .functions import MainFunctions
from .user_define_pages import get_page_routes


class PageRouterController:
    def __init__(self, window, main_functions=MainFunctions, language=Language, get_routes=get_page_routes):
        self._window = window
        self._main_functions = main_functions
        self._language = language
        self._get_routes = get_routes

    def route_for(self, btn_name: str):
        return self._get_routes(self._language).get(btn_name)

    def switch_page(self, btn_name: str, page_name: str, title: str):
        self._window.ui.left_menu.select_only_one(btn_name)
        self._main_functions.set_page(self._window, self._window.ui.load_pages.pages.findChild(QWidget, page_name))
        self._window.ui.title_bar.set_title(title)


class ThemeController:
    _THEME_SEQUENCE = ("eye", "bright", "default")

    def __init__(self, window, color_palette=ColorPalette, app_themes=AppThemes, style_factory=Styles):
        self._window = window
        self._color_palette = color_palette
        self._app_themes = app_themes
        self._style_factory = style_factory
        self._theme_index = -1

    def cycle_theme(self):
        self._theme_index = (self._theme_index + 1) % len(self._THEME_SEQUENCE)
        theme_name = self._THEME_SEQUENCE[self._theme_index]
        self._color_palette.update(self._app_themes[theme_name].data)
        now = self._style_factory()
        self._window.ui.window.setStyleSheet(now.style)


class ColumnController:
    def __init__(self, window, main_functions=MainFunctions, language=Language):
        self._window = window
        self._main_functions = main_functions
        self._language = language

    def handle_info_button(self, btn_name: str):
        if not self._main_functions.left_column_is_visible(self._window):
            self._window.ui.left_menu.select_only_one_tab(btn_name)
            self._main_functions.toggle_left_column(self._window)
            self._window.ui.left_menu.select_only_one_tab(btn_name)
        else:
            if btn_name == "btn_close_left_column":
                self._window.ui.left_menu.deselect_all_tab()
                self._main_functions.toggle_left_column(self._window)
            self._window.ui.left_menu.select_only_one_tab(btn_name)
        if btn_name != "btn_close_left_column":
            self._main_functions.set_left_column_menu(
                self._window,
                menu=self._window.ui.left_column.menus.menu_2,
                title=self._language.UI.ui_Settings,
                icon_path=PathFactory.set_svg_icon("icon_setting"),
            )

    def handle_more_button(self, btn_name: str):
        if not self._main_functions.left_column_is_visible(self._window):
            self._main_functions.toggle_left_column(self._window)
            self._window.ui.left_menu.select_only_one_tab(btn_name)
        else:
            if btn_name == "btn_close_left_column":
                self._window.ui.left_menu.deselect_all_tab()
                self._main_functions.toggle_left_column(self._window)
            self._window.ui.left_menu.select_only_one_tab(btn_name)
        if btn_name != "btn_close_left_column":
            self._main_functions.set_left_column_menu(
                self._window,
                menu=self._window.ui.left_column.menus.menu_1,
                title=self._language.custom_ui.left_column_io_test_title,
                icon_path=PathFactory.set_svg_icon("icon_more"),
            )

    def handle_top_settings_button(self, btn):
        if not self._main_functions.right_column_is_visible(self._window):
            btn.set_active(True)
            self._main_functions.toggle_right_column(self._window)
        else:
            btn.set_active(False)
            self._main_functions.toggle_right_column(self._window)
        top_settings = self._main_functions.get_left_menu_btn(self._window, "btn_settings")
        top_settings.set_active_tab(False)


class MainWindowController:
    def __init__(
        self,
        window,
        main_functions=MainFunctions,
        plugin_registry_getter=get_plugin_registry,
        event_recorder=record_event,
        logger=Logger,
        button_use_case=None,
    ):
        self._window = window
        self._main_functions = main_functions
        self._plugin_registry_getter = plugin_registry_getter
        self._record_event = event_recorder
        self._logger = logger
        self._button_use_case = button_use_case or MainWindowButtonUseCase()
        self.page_router = PageRouterController(window=window, main_functions=main_functions)
        self.theme_controller = ThemeController(window=window)
        self.column_controller = ColumnController(window=window, main_functions=main_functions)

    def handle_button(self, btn):
        btn_name = btn.objectName()
        self._logger.debug(f"{btn_name} is clicked")
        self._record_event("ui.button_click", category="ui", payload={"button_id": btn_name})

        if self._button_use_case.should_reset_left_tab(btn_name):
            self._window.ui.left_menu.deselect_all_tab()
        try:
            top_settings = self._main_functions.get_title_bar_btn(self._window, "btn_top_settings")
            top_settings.set_active(False)
        except AttributeError:
            pass

        route = self.page_router.route_for(btn_name)
        decision = self._button_use_case.decide(btn_name, route)

        if decision.kind == "page_route":
            page_name, title = decision.payload
            self.page_router.switch_page(btn_name, page_name, title)
            return

        if decision.kind == "plugin_command":
            self._plugin_registry_getter().execute_command(btn_name, self._window, btn)
            return

        if decision.kind != "action":
            return

        action_name = decision.payload

        action_routes = {
            "btn_info": lambda: self.column_controller.handle_info_button(btn_name),
            "btn_more": lambda: self.column_controller.handle_more_button(btn_name),
            "btn_close_left_column": lambda: self.column_controller.handle_more_button(btn_name),
            "btn_top_settings": lambda: self.column_controller.handle_top_settings_button(btn),
            "btn_language": lambda: None,
            "btn_themes": self.theme_controller.cycle_theme,
        }

        action = action_routes.get(action_name)
        if action:
            action()
