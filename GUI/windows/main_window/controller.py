"""模块说明。"""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from AppCore import (
    AppThemes,
    ColorPalette,
    Language,
    Logger,
    MainWindowButtonUseCase,
    PathFactory,
    get_plugin_registry,
    record_event,
)
from guicore import Styles

from .functions import MainFunctions
from .user_define_pages import get_page_routes


class PageRouterController:
    """页面路由控制器。

    职责:
    - 解析按钮对应页面路由。
    - 执行页面切换与标题更新。
    """

    def __init__(
        self,
        window: object,
        main_functions: object = MainFunctions,
        language: object = Language,
        get_routes: Callable[[object], dict[str, tuple[str, str]]] = get_page_routes,
    ) -> None:
        """初始化页面路由控制器。

        参数:
        - window: 主窗口对象。
        - main_functions: 页面操作函数集合。
        - language: 当前语言资源对象。
        - get_routes: 路由获取函数。

        返回:
        - None
        """
        self._window = window
        self._main_functions = main_functions
        self._language = language
        self._get_routes = get_routes

    def route_for(self, btn_name: str) -> tuple[str, str] | None:
        """获取按钮对应路由。

        参数:
        - btn_name: 按钮对象名。

        返回:
        - tuple[str, str] | None: 页面对象名与标题元组，未命中时为 None。
        """
        return self._get_routes(self._language).get(btn_name)

    def switch_page(self, btn_name: str, page_name: str, title: str) -> None:
        """切换页面并更新标题。

        参数:
        - btn_name: 按钮对象名。
        - page_name: 页面对象名。
        - title: 标题文本。

        返回:
        - None
        """
        self._window.ui.left_menu.select_only_one(btn_name)
        self._main_functions.set_page(self._window, self._window.ui.load_pages.pages.findChild(QWidget, page_name))
        self._window.ui.title_bar.set_title(title)


class ThemeController:
    """主题切换控制器。

    职责:
    - 按固定顺序轮换主题。
    - 更新颜色调色板并刷新样式表。
    """

    _THEME_SEQUENCE = ("eye", "bright", "default")

    def __init__(
        self,
        window: object,
        color_palette: object = ColorPalette,
        app_themes: object = AppThemes,
        style_factory: object = Styles,
    ) -> None:
        """初始化主题控制器。

        参数:
        - window: 主窗口对象。
        - color_palette: 颜色调色板对象。
        - app_themes: 主题数据映射。
        - style_factory: 样式工厂。

        返回:
        - None
        """
        self._window = window
        self._color_palette = color_palette
        self._app_themes = app_themes
        self._style_factory = style_factory
        self._theme_index = -1

    def cycle_theme(self) -> None:
        """轮换到下一个主题并应用样式。

        返回:
        - None
        """
        self._theme_index = (self._theme_index + 1) % len(self._THEME_SEQUENCE)
        theme_name = self._THEME_SEQUENCE[self._theme_index]
        self._color_palette.update(self._app_themes[theme_name].data)
        now = self._style_factory()
        self._window.ui.window.setStyleSheet(now.style)


class ColumnController:
    """侧栏区域控制器。

    职责:
    - 处理左侧信息区与更多区切换。
    - 处理顶部设置按钮触发的右侧栏显示逻辑。
    """

    def __init__(self, window: object, main_functions: object = MainFunctions, language: object = Language) -> None:
        """初始化侧栏控制器。

        参数:
        - window: 主窗口对象。
        - main_functions: 窗口功能函数集合。
        - language: 当前语言资源对象。

        返回:
        - None
        """
        self._window = window
        self._main_functions = main_functions
        self._language = language

    def handle_info_button(self, btn_name: str) -> None:
        """处理信息按钮点击逻辑。

        参数:
        - btn_name: 按钮对象名。

        返回:
        - None
        """
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

    def handle_more_button(self, btn_name: str) -> None:
        """处理更多按钮点击逻辑。

        参数:
        - btn_name: 按钮对象名。

        返回:
        - None
        """
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

    def handle_top_settings_button(self, btn: object) -> None:
        """处理顶部设置按钮逻辑。

        参数:
        - btn: 顶部设置按钮对象。

        返回:
        - None
        """
        if not self._main_functions.right_column_is_visible(self._window):
            btn.set_active(True)
            self._main_functions.toggle_right_column(self._window)
        else:
            btn.set_active(False)
            self._main_functions.toggle_right_column(self._window)
        top_settings = self._main_functions.get_left_menu_btn(self._window, "btn_settings")
        top_settings.set_active_tab(False)


class MainWindowController:
    """主窗口总控制器。

    职责:
    - 接收按钮点击事件并记录日志与遥测。
    - 根据用例决策分发到页面、动作或插件命令。
    """

    @dataclass(frozen=True)
    class Runtime:
        """主窗口控制器运行时依赖。"""

        plugin_registry_getter: Callable[[], object] = get_plugin_registry
        event_recorder: Callable[..., object] = record_event
        logger: object = Logger

    def __init__(
        self,
        window: object,
        main_functions: object = MainFunctions,
        runtime: Runtime | None = None,
        button_use_case: object | None = None,
    ) -> None:
        """初始化主窗口控制器。

        参数:
        - window: 主窗口对象。
        - main_functions: 主窗口功能函数集合。
        - runtime: 运行时依赖集合（插件注册、遥测、日志）。
        - button_use_case: 按钮决策用例实例。

        返回:
        - None
        """
        runtime = runtime or MainWindowController.Runtime()
        self._window = window
        self._main_functions = main_functions
        self._plugin_registry_getter = runtime.plugin_registry_getter
        self._record_event = runtime.event_recorder
        self._logger = runtime.logger
        self._button_use_case = button_use_case or MainWindowButtonUseCase()
        self.page_router = PageRouterController(window=window, main_functions=main_functions)
        self.theme_controller = ThemeController(window=window)
        self.column_controller = ColumnController(window=window, main_functions=main_functions)

    def handle_button(self, btn: object) -> None:
        """处理主窗口按钮点击事件。

        参数:
        - btn: 当前触发事件的按钮对象。

        返回:
        - None
        """
        btn_name = btn.objectName()
        self._logger.debug("%s is clicked", btn_name)
        self._record_event("ui.button_click", category="ui", payload={"button_id": btn_name})

        if self._button_use_case.should_reset_left_tab(btn_name):
            self._window.ui.left_menu.deselect_all_tab()
        try:
            top_settings = self._main_functions.get_title_bar_btn(self._window, "btn_top_settings")
            top_settings.set_active(False)
        except AttributeError:
            pass

        route = self.page_router.route_for(btn_name)
        Logger.debug(route)
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
