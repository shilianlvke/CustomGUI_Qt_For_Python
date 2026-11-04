from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QPushButton, QWidget

from customgui.appcore import (
    Language,
    Logger,
    MainWindowButtonUseCase,
    PathFactory,
    get_plugin_registry,
    get_theme_manager,
    record_event,
)
from customgui.appcore.ui_state import save_ui_state
from customgui.guicore import Styles

from .functions import MainFunctions
from .registry import ensure_registered_page, get_page_routes


class _WindowStateTracker(QObject):
    """窗口关闭时保存正常尺寸（最大化/最小化/全屏状态不写入）。"""

    def __init__(self, window):
        super().__init__(window)
        self._window = window

    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if obj is self._window and event.type() == QEvent.Type.Close:
            self._save_size()
        return False

    def _save_size(self) -> None:
        window = self._window
        try:
            if window.isMaximized() or window.isMinimized() or window.isFullScreen():
                return
            size = window.size()
        except RuntimeError:
            return
        if size.width() > 0 and size.height() > 0:
            save_ui_state(window_size=[size.width(), size.height()])


class PageRouterController:
    def __init__(
        self,
        window,
        main_functions=MainFunctions,
        language=Language,
        get_routes=get_page_routes,
        logger=Logger,
        event_recorder=record_event,
    ):
        self._window = window
        self._main_functions = main_functions
        self._language = language
        self._get_routes = get_routes
        self._logger = logger
        self._record_event = event_recorder

    def route_for(self, btn_name: str):
        return self._get_routes(self._language).get(btn_name)

    def switch_page(self, btn_name: str, page_name: str, title: str):
        left_menu = self._window.ui.left_menu
        # 先记录原栏目按钮，再过场里由时间线驱动两枚按钮的高亮接力
        active_getter = getattr(left_menu, "active_button_id", None)
        previous_btn = active_getter() if callable(active_getter) else None
        left_menu.select_only_one(btn_name)
        ensure_registered_page(self._window, page_name)
        self._main_functions.set_page(
            self._window,
            self._window.ui.load_pages.pages.findChild(QWidget, page_name),
            menu=left_menu,
            button_id=btn_name,
            previous_button_id=previous_btn,
        )
        self._window.ui.title_bar.set_title(title)
        self._logger.debug(f"切换页面: {btn_name} -> {page_name} ({title})")
        self._record_event(
            "ui.page_switch",
            category="ui",
            payload={"button_id": btn_name, "page": page_name, "title": title},
        )


class ThemeController:
    """主题切换控制器：委托 ThemeManager，样式重建由订阅驱动。"""

    def __init__(
        self,
        window,
        theme_manager=None,
        style_factory=Styles,
        logger=Logger,
        event_recorder=record_event,
    ):
        self._window = window
        self._theme_manager = theme_manager or get_theme_manager()
        self._style_factory = style_factory
        self._logger = logger
        self._record_event = event_recorder
        # 主题变更 -> 重建全局样式并应用（弱引用订阅）
        self._theme_manager.subscribe(self._apply_styles)

    def cycle_theme(self):
        # Launcher applications may expose their own theme cycle (for example
        # dark/light/system). Prefer it over the base theme sequence.
        custom = getattr(self._window, "cycle_app_theme", None)
        if callable(custom):
            try:
                custom()
                return
            except Exception as exc:
                self._logger.warning(f"自定义主题切换失败，回退到基座主题循环: {exc}")
        self._theme_manager.cycle()

    def toggle_theme_drawer(self) -> bool:
        """打开/收起右侧主题配置抽屉。

        - 抽屉收起：切换到 ``theme_menu`` 并展开；
        - 抽屉已展开且当前就是主题页：收起（Toggle）；
        - 抽屉已展开但停在别的右侧页：只切到主题页，不收起。
        """
        ui = getattr(self._window, "ui", None)
        menu = getattr(ui, "theme_menu", None)
        if menu is None or not hasattr(ui, "right_column"):
            self._logger.warning("当前窗口没有主题配置抽屉页")
            return False
        visible = MainFunctions.right_column_is_visible(self._window)
        if visible and ui.right_column.menus.currentWidget() is menu:
            MainFunctions.toggle_right_column(self._window)
            self._sync_theme_button()
            return True
        ui.right_column.menus.setCurrentWidget(menu)
        if not visible:
            MainFunctions.toggle_right_column(self._window)
        self._sync_theme_button()
        return True

    def _sync_theme_button(self) -> None:
        """让标题栏“主题配置”按钮始终反映主题抽屉的展开状态。"""
        ui = getattr(self._window, "ui", None)
        if ui is None:
            return
        button = ui.title_bar.findChild(QPushButton, "btn_themes")
        if button is None or not hasattr(button, "set_active"):
            return
        menu = getattr(ui, "theme_menu", None)
        active = bool(
            menu is not None
            and MainFunctions.right_column_is_visible(self._window)
            and ui.right_column.menus.currentWidget() is menu
        )
        button.set_active(active)

    def _apply_styles(self):
        window_widget = self._window.ui.window
        # 优先委托 CWindow.apply_style（内部重建样式，并保留最大化等框架样式覆盖）
        apply_style = getattr(window_widget, "apply_style", None)
        if callable(apply_style):
            apply_style()
        else:
            # 旧组件/测试桩：回落到直接设置样式（样式仅在此处构造一次）
            now = self._style_factory()
            window_widget.setStyleSheet(now.style)
        save_ui_state(theme=self._theme_manager.current())


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

    def handle_top_column_close(self, btn_name: str):
        """顶列自带的关闭按钮：与左列的 btn_close_* 一样走统一开合。"""
        self._main_functions.toggle_top_column(self._window)

    def handle_bottom_column_close(self, btn_name: str):
        """底列自带的关闭按钮。"""
        self._main_functions.toggle_bottom_column(self._window)


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
        config = getattr(getattr(window, "ui", None), "theme_config", None)
        close_requested = getattr(config, "closeRequested", None)
        if close_requested is not None:
            close_requested.connect(self.theme_controller.toggle_theme_drawer)
        menu_mode_changed = getattr(config, "menuModeChanged", None)
        if menu_mode_changed is not None:
            menu_mode_changed.connect(self._apply_menu_mode)
        # 关闭窗口时把正常尺寸写入 ui_state.json，下次启动恢复
        # （测试桩可能只提供 SimpleNamespace，不是 QObject，跳过即可）
        if isinstance(window, QObject):
            self._window_state_tracker = _WindowStateTracker(window)
            window.installEventFilter(self._window_state_tracker)

    def _apply_menu_mode(self, mode: str) -> None:
        """主题配置里的 Static / Overlay 菜单模式，交给宿主改变左菜单布局。"""
        setter = getattr(self._main_functions, "set_menu_mode", None)
        if callable(setter):
            setter(self._window, mode)

    def handle_button(self, btn):
        btn_name = btn.objectName()
        self._logger.debug(f"{btn_name} is clicked")
        self._record_event("ui.button_click", category="ui", payload={"button_id": btn_name})

        if self._button_use_case.should_reset_left_tab(btn_name):
            self._window.ui.left_menu.deselect_all_tab()

        route = self.page_router.route_for(btn_name)
        self._logger.debug(f"路由解析: {btn_name} -> {route}")
        decision = self._button_use_case.decide(btn_name, route)

        if decision.kind == "page_route":
            page_name, title = decision.payload
            self.page_router.switch_page(btn_name, page_name, title)
            return

        if decision.kind == "plugin_command":
            self._plugin_registry_getter().execute_command(btn_name, self._window, btn)
            return

        if decision.kind != "action":
            self._logger.warning(f"未知按钮决策类型: {decision.kind} (button={btn_name})")
            return

        action_name = decision.payload

        action_routes = {
            "btn_info": lambda: self.column_controller.handle_info_button(btn_name),
            "btn_more": lambda: self.column_controller.handle_more_button(btn_name),
            "btn_close_left_column": lambda: self.column_controller.handle_more_button(btn_name),
            "btn_close_top_column": lambda: self.column_controller.handle_top_column_close(btn_name),
            "btn_close_bottom_column": lambda: self.column_controller.handle_bottom_column_close(btn_name),
            "btn_top_settings": lambda: self.column_controller.handle_top_settings_button(btn),
            "btn_language": self._handle_language_switch,
            "btn_themes": self._handle_theme_button,
            "btn_search": lambda: self._handle_search_button(btn),
        }

        action = action_routes.get(action_name)
        if action:
            action()
        else:
            self._logger.warning(f"按钮动作未实现: {action_name} (button={btn_name})")

    def _handle_language_switch(self):
        """语言切换：整体切换基座 + 全部应用语言并刷新 UI。"""
        from customgui.guis.language_service import switch_language

        switch_language(self._window)

    def _handle_search_button(self, anchor):
        """标题栏搜索：弹出按页面标题过滤的快速跳转面板。"""
        from .search_palette import CSearchPalette

        palette = getattr(self, "_search_palette", None)
        if palette is None:
            palette = CSearchPalette(self._window)
            palette.selected.connect(self._open_search_result)
            self._search_palette = palette
        palette.show_for(anchor)

    def _open_search_result(self, btn_name: str) -> None:
        route = self.page_router.route_for(btn_name)
        if route is None:
            return
        page_name, title = route
        self.page_router.switch_page(btn_name, page_name, title)

    def _handle_theme_button(self):
        """标题栏“主题配置”按钮：打开/收起右侧主题抽屉。

        兼容只注入了旧 ``cycle_theme`` 的测试桩/自定义控制器；真实控制器
        始终具备 ``toggle_theme_drawer``。
        """
        toggle = getattr(self.theme_controller, "toggle_theme_drawer", None)
        if callable(toggle):
            toggle()
        else:
            self.theme_controller.cycle_theme()
