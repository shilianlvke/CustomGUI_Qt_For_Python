"""主窗口控制器组装层。

MainWindowController 聚合 PageRouterController（栏目路由与页面切换）、
SettingsController（主题/背景/外观设置与预览）与 ColumnController（左右/底
列按钮处理），并接管主窗口按钮分发与关闭时尺寸持久化。位于 GUI 窗口层，
把 UI 事件委派给 appcore 用例与页面注册表，保持控件与业务逻辑解耦。
"""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QPushButton, QWidget

from sllkgui.appcore import (
    KEY_BACKGROUND_BLUR,
    KEY_THEME,
    Language,
    Logger,
    MainWindowButtonUseCase,
    PathFactory,
    SettingsSession,
    ensure_core_pages,
    get_theme_manager,
    load_user_settings,
    record_event,
    save_user_settings,
)
from sllkgui.guicore import (
    CSettingsWindow,
    Styles,
    acrylic_active,
    acrylic_transparency,
    apply_acrylic,
    glass_strength,
    set_acrylic_transparency,
    set_glass_strength,
)

from .functions import MainFunctions
from .registry import ensure_registered_page, get_page_routes, notify_page_failure


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
            maximized = window.isMaximized() or window.isMinimized() or window.isFullScreen()
            size = None if maximized else window.size()
        except RuntimeError:
            return
        updates = {}
        if size is not None and size.width() > 0 and size.height() > 0:
            # 不把小于 minimum_size 的尺寸写回 user.yaml
            minimum = window.minimumSize()
            updates["startup_size"] = [
                max(size.width(), minimum.width()),
                max(size.height(), minimum.height()),
            ]
        state = load_user_settings()
        if state.get("remember_window_size", True) is False:
            # 用户关闭了「记住窗口尺寸」：不写 startup_size，下次用配置文件里的值
            updates.pop("startup_size", None)
        # 外观参数以运行期状态为准：设置窗口保存时已经写入 acrylic 模块
        updates["acrylic_transparency"] = acrylic_transparency()
        updates["glass_strength"] = glass_strength()
        if updates:
            save_user_settings(**updates)


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
        return self._get_routes(self._language, self._window).get(btn_name)

    def switch_page(self, btn_name: str, page_name: str, title: str):
        left_menu = self._window.ui.left_menu
        # 先记录原栏目按钮，再过场里由时间线驱动两枚按钮的高亮接力
        active_getter = getattr(left_menu, "active_button_id", None)
        previous_btn = active_getter() if callable(active_getter) else None
        left_menu.select_only_one(btn_name)
        ensure_registered_page(self._window, page_name, on_error=notify_page_failure)
        self._main_functions.set_page(
            self._window,
            self._window.ui.load_pages.pages.findChild(QWidget, page_name),
            menu=left_menu,
            button_id=btn_name,
            previous_button_id=previous_btn,
        )
        self._window.ui.title_bar.set_title(title)
        # GalleryWindow 需要同步“当前页”状态（原生页/插件 Surface 进入与离开）；
        # 控制器不直接依赖 gallery，用可选钩子保持 guis -> gallery 的单向边界。
        sync_context = getattr(self._window, "_on_page_router_switch", None)
        if callable(sync_context):
            try:
                sync_context(page_name)
            except Exception as exc:  # noqa: BLE001 - 状态同步失败不阻断切页
                self._logger.warning(f"同步页面上下文失败: {exc}")
        self._logger.debug(f"切换页面: {btn_name} -> {page_name} ({title})")
        self._record_event(
            "ui.page_switch",
            category="ui",
            payload={"button_id": btn_name, "page": page_name, "title": title},
        )
        from .pet_bridge import on_page_switched

        on_page_switched(btn_name)


class SettingsController:
    """设置与主题控制器：主题切换委托 ThemeManager，样式重建由订阅驱动。"""

    def __init__(
        self,
        window,
        theme_manager=None,
        style_factory=Styles,
        logger=Logger,
        event_recorder=record_event,
        plugin_titles=None,
    ):
        self._window = window
        self._theme_manager = theme_manager or get_theme_manager()
        self._style_factory = style_factory
        self._logger = logger
        self._record_event = event_recorder
        #: 插件显示名提供者（设置窗口的插件页分组标题用）；guicore 不 import gallery
        self._plugin_titles = plugin_titles
        #: 独立设置窗口（打开时创建，关闭即销毁；下次打开重新读盘）
        self._settings_window: CSettingsWindow | None = None
        #: 实时预览主题时不落盘，保存由设置会话统一负责
        self._previewing_theme = False
        #: 主题持久化重入保护（session.save → settings change → 应用主题）
        self._persisting_theme = False
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
        from .pet_bridge import on_theme_cycled

        on_theme_cycled(str(self._theme_manager.current()))

    # ------------------------------------------------------------------
    # 独立设置窗口
    # ------------------------------------------------------------------
    def settings_window(self) -> CSettingsWindow | None:
        """当前打开的设置窗口（未打开时为 ``None``）。

        供 toast 锚点解析使用：设置页里的动作结果应出现在设置窗口，
        而不是落到被它遮住的主窗口。
        """
        return self._settings_window

    def open_settings_window(self) -> bool:
        """打开独立设置窗口；已打开时聚焦到现有实例。"""
        if self._settings_window is not None:
            self._settings_window.open_settings()
            return True
        window = CSettingsWindow(
            self._window,
            host=self._window,
            plugin_titles=self._plugin_titles,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.previewChanged.connect(self._preview_setting)
        window.settingsSaved.connect(self._apply_saved_settings)
        window.closed.connect(self._on_settings_window_closed)
        window.destroyed.connect(self._forget_settings_window)
        self._settings_window = window
        window.open_settings()
        self._sync_settings_button(True)
        self._record_event("ui.settings_window_open", category="ui", payload={})
        from .pet_bridge import on_settings_opened

        on_settings_opened()
        return True

    def open_settings_page(self, plugin_id: str, page_id: str = "") -> bool:
        """打开设置窗口并定位到插件的指定设置页。"""
        if not self.open_settings_window():
            return False
        window = self._settings_window
        if window is None:
            return False
        target = str(page_id or plugin_id).strip()
        if not target:
            return True
        window.show_page(f"plugin::{plugin_id}::{target}")
        return True

    def close_settings_window(self) -> None:
        window = self._settings_window
        if window is not None:
            window.close()

    def _on_settings_window_closed(self) -> None:
        self._settings_window = None
        self._sync_settings_button(False)
        self._record_event("ui.settings_window_close", category="ui", payload={})
        from .pet_bridge import on_settings_closed

        on_settings_closed()

    def _forget_settings_window(self, *_args) -> None:
        self._settings_window = None

    def _preview_setting(self, key: str, value) -> None:
        """设置窗口的实时预览：只改运行期观感，不写用户配置。"""
        if key == KEY_THEME:
            self._apply_theme_preview(str(value))
        elif key == "core.appearance.transparency":
            set_acrylic_transparency(int(value))
            self.refresh_acrylic()
            if self._settings_window is not None:
                apply_acrylic(self._settings_window)
        elif key == "core.appearance.glass_strength":
            set_glass_strength(int(value))
            self.refresh_styles()
        elif key in ("core.appearance.background_image", "core.appearance.background_fit"):
            self._apply_background_preview(key, value)
        elif key == KEY_BACKGROUND_BLUR:
            self._apply_background_blur(value)

    def _apply_theme_preview(self, name: str) -> None:
        self._previewing_theme = True
        try:
            self._theme_manager.apply(name)
        finally:
            self._previewing_theme = False

    def _apply_background_preview(self, key: str, value) -> None:
        window = self._settings_window
        if window is None:
            return
        session = window.session()
        path = (
            str(value) if key.endswith("background_image") else str(session.value("core.appearance.background_image"))
        )
        fit = str(value) if key.endswith("background_fit") else str(session.value("core.appearance.background_fit"))
        self._apply_background(path, fit)

    def _apply_background(self, path: str, fit: str) -> None:
        widget = getattr(getattr(self._window, "ui", None), "window", None)
        setter = getattr(widget, "set_background_image", None)
        if callable(setter):
            setter(path, fit)

    def _apply_background_blur(self, value) -> None:
        """背景模糊实时预览：只改运行期背景层，切换背景图时保留。"""
        widget = getattr(getattr(self._window, "ui", None), "window", None)
        setter = getattr(widget, "set_background_blur", None)
        if not callable(setter):
            return
        try:
            setter(int(value))
        except (TypeError, ValueError):
            self._logger.debug(f"忽略非法背景模糊值: {value!r}")

    def _apply_menu_mode(self, mode: str) -> None:
        """应用菜单模式；持久化由 ``SettingsSession.save()`` 统一负责。"""
        setter = getattr(MainFunctions, "set_menu_mode", None)
        if callable(setter):
            setter(self._window, mode)

    def _apply_drawer_mode(self, mode: str) -> None:
        """应用抽屉模式；持久化由 ``SettingsSession.save()`` 统一负责。"""
        setter = getattr(MainFunctions, "set_drawer_mode", None)
        if callable(setter):
            setter(self._window, mode)

    def _apply_saved_settings(self, changes: dict) -> None:
        """保存成功后应用非预览类设置（语言 / 布局 / 窗口记忆）。"""
        if KEY_THEME in changes:
            self._previewing_theme = True
            try:
                self._theme_manager.apply(str(changes[KEY_THEME]))
            finally:
                self._previewing_theme = False
            from .pet_bridge import on_theme_changed

            on_theme_changed(str(changes[KEY_THEME]))
        if "core.appearance.transparency" in changes:
            set_acrylic_transparency(int(changes["core.appearance.transparency"]))
            self.refresh_acrylic()
        if "core.appearance.glass_strength" in changes:
            set_glass_strength(int(changes["core.appearance.glass_strength"]))
            self.refresh_styles()
        if KEY_BACKGROUND_BLUR in changes:
            self._apply_background_blur(changes[KEY_BACKGROUND_BLUR])
        if "core.appearance.background_image" in changes or "core.appearance.background_fit" in changes:
            window = self._settings_window
            session = window.session() if window is not None else None
            path = str(
                changes.get(
                    "core.appearance.background_image",
                    session.value("core.appearance.background_image") if session is not None else "",
                )
            )
            fit = str(
                changes.get(
                    "core.appearance.background_fit",
                    session.value("core.appearance.background_fit") if session is not None else "fill",
                )
            )
            self._apply_background(path, fit)
        from .pet_bridge import on_layout_changed

        if "core.interface.menu_mode" in changes:
            self._apply_menu_mode(str(changes["core.interface.menu_mode"]))
            on_layout_changed(str(changes["core.interface.menu_mode"]))
        if "core.interface.drawer_mode" in changes:
            self._apply_drawer_mode(str(changes["core.interface.drawer_mode"]))
            on_layout_changed(str(changes["core.interface.drawer_mode"]))
        if "core.interface.language" in changes:
            from sllkgui.guis.language_service import apply_language

            try:
                apply_language(str(changes["core.interface.language"]), self._window)
            except Exception as exc:  # noqa: BLE001 - 语言应用失败不应关闭设置窗口
                self._logger.warning(f"应用语言失败: {exc}")
            else:
                from .pet_bridge import on_language_changed

                on_language_changed(str(changes["core.interface.language"]))
            # 语言切换会重建主窗口页面；设置窗口保持打开，并在原位刷新文案，
            # 避免用户保存后还要重新打开、重新定位到刚才的配置页。
            window = self._settings_window
            if window is not None:
                try:
                    window.refresh_language()
                except Exception as exc:  # noqa: BLE001 - 刷新失败保留旧文案，不关闭窗口
                    self._logger.warning(f"刷新设置窗口文案失败: {exc}")
            self._sync_settings_button(window is not None)
            return
        self._sync_settings_button(self._settings_window is not None)

    def is_settings_window_open(self) -> bool:
        """设置窗口是否处于打开状态（标题栏按钮高亮用）。"""
        window = self._settings_window
        return window is not None and window.isVisible()

    def _sync_settings_button(self, active: bool | None = None) -> None:
        """让标题栏设置按钮反映设置窗口的开合状态。"""
        ui = getattr(self._window, "ui", None)
        if ui is None:
            return
        button = ui.title_bar.findChild(QPushButton, "btn_settings")
        if button is None or not hasattr(button, "set_active"):
            return
        if active is None:
            active = self.is_settings_window_open()
        button.set_active(bool(active))

    def refresh_styles(self):
        """按当前主题与外观参数重建全局样式（滑块实时预览也走这里）。"""
        window_widget = self._window.ui.window
        # 优先委托 CWindow.apply_style（内部重建样式，并保留最大化等框架样式覆盖）
        apply_style = getattr(window_widget, "apply_style", None)
        if callable(apply_style):
            apply_style()
        else:
            # 旧组件/测试桩：回落到直接设置样式（样式仅在此处构造一次）
            now = self._style_factory()
            window_widget.setStyleSheet(now.style)

    def refresh_acrylic(self):
        """重新应用亚克力色调（透明度滑块实时生效，开销约 0.15ms）。"""
        window_widget = getattr(getattr(self._window, "ui", None), "window", None)
        sync = getattr(window_widget, "_sync_acrylic", None)
        if callable(sync):
            sync()
            return
        if acrylic_active():
            apply_acrylic(self._window)

    def _apply_styles(self):
        self.refresh_styles()
        # 设置窗口里的主题预览不落盘：用户点「保存」时才由会话统一写入。
        # 非预览路径（如插件切换主题）经 SettingsSession 写回，键名与校验
        # 复用 base.py 的单一声明；_persisting_theme 阻断 save→apply→save 回路。
        if self._previewing_theme or self._persisting_theme:
            return
        self._persisting_theme = True
        try:
            ensure_core_pages()
            session = SettingsSession()
            if session.set(KEY_THEME, str(self._theme_manager.current())):
                session.save()
        except Exception as exc:  # noqa: BLE001 - 持久化失败不影响已应用的主题
            self._logger.warning(f"主题持久化失败: {exc}")
        finally:
            self._persisting_theme = False

    def detach(self) -> None:
        """窗口关闭时退订主题变更，避免已销毁窗口继续响应全局主题切换。"""
        try:
            self._theme_manager.unsubscribe(self._apply_styles)
        except Exception as exc:  # noqa: BLE001 - 退订失败不应阻塞关闭
            self._logger.debug(f"主题订阅退订失败: {exc}")


class ColumnController:
    def __init__(self, window, main_functions=MainFunctions, language=Language):
        self._window = window
        self._main_functions = main_functions
        self._language = language

    def handle_more_button(self, btn_name: str):
        if not self._main_functions.left_column_is_visible(self._window):
            self._main_functions.toggle_left_column(self._window)
            self._window.ui.left_menu.select_only_one_tab(btn_name)
        else:
            if btn_name == "btn_close_left_column":
                self._window.ui.left_menu.deselect_all_tab("bottom")
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
        event_recorder=record_event,
        logger=Logger,
        button_use_case=None,
    ):
        self._window = window
        self._main_functions = main_functions
        self._record_event = event_recorder
        self._logger = logger
        self._button_use_case = button_use_case or MainWindowButtonUseCase()
        #: 搜索面板刚命中跳转：收起时不再补"回到常态"反馈（见 _on_search_palette_closed）
        self._search_navigated = False
        self.page_router = PageRouterController(window=window, main_functions=main_functions)
        self.settings_controller = SettingsController(window=window, plugin_titles=self._plugin_titles)
        self.column_controller = ColumnController(window=window, main_functions=main_functions)
        # 关闭窗口时把正常尺寸写入用户配置 user.yaml，下次启动恢复
        # （测试桩可能只提供 SimpleNamespace，不是 QObject，跳过即可）
        if isinstance(window, QObject):
            self._window_state_tracker = _WindowStateTracker(window)
            window.installEventFilter(self._window_state_tracker)

    def _plugin_titles(self) -> dict[str, str]:
        """插件显示名：设置窗口按它分组插件页；未接入 Gallery 时为空表。"""
        registry = getattr(self._window, "gallery_registry", None)
        if registry is None:
            return {}
        # 只列出真实安装的插件；桌面宠物是基座原生设置，不属于插件栏
        return {record.plugin_id: record.name for record in registry.plugins()}

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

        if decision.kind != "action":
            self._logger.warning(f"未知按钮决策类型: {decision.kind} (button={btn_name})")
            return

        action_name = decision.payload

        action_routes = {
            "btn_more": lambda: self.column_controller.handle_more_button(btn_name),
            "btn_close_left_column": lambda: self.column_controller.handle_more_button(btn_name),
            "btn_close_top_column": lambda: self.column_controller.handle_top_column_close(btn_name),
            "btn_close_bottom_column": lambda: self.column_controller.handle_bottom_column_close(btn_name),
            "btn_top_settings": lambda: self._handle_top_settings_button(btn),
            "btn_settings": self._handle_settings_button,
            "btn_search": lambda: self._handle_search_button(btn),
        }

        action = action_routes.get(action_name)
        if action:
            action()
        else:
            self._logger.warning(f"按钮动作未实现: {action_name} (button={btn_name})")

    def _handle_search_button(self, anchor):
        """标题栏搜索：弹出按页面标题过滤的快速跳转面板。"""
        from .search_palette import CSearchPalette

        palette = getattr(self, "_search_palette", None)
        if palette is None:
            palette = CSearchPalette(self._window)
            palette.selected.connect(self._open_search_result)
            # 收起（含点外部关闭）时结束搜索状态，避免宠物一直停在 searching
            palette.closed.connect(self._on_search_palette_closed)
            self._search_palette = palette
        palette.show_for(anchor)
        from .pet_bridge import on_search_opened

        on_search_opened()

    def _on_search_palette_closed(self) -> None:
        """搜索面板收起：宠物给一次收起反馈后回到常态。

        命中结果时不再额外发收起反馈：选中会先触发切页反应，
        再补一条"回到常态"会把刚给出的页面反馈立刻盖掉。
        """
        if self._search_navigated:
            self._search_navigated = False
            return
        from .pet_bridge import on_search_closed

        on_search_closed()

    def _open_search_result(self, btn_name: str) -> None:
        route = self.page_router.route_for(btn_name)
        if route is None:
            return
        self._search_navigated = True
        page_name, title = route
        self.page_router.switch_page(btn_name, page_name, title)

    def open_search_palette(self) -> bool:
        """内置快捷键入口：把搜索弹层贴到标题栏按钮上。

        没有搜索按钮的旧宿主/测试桩返回 ``False``，让调用方知道这条快捷键
        没有落点（注册阶段会直接跳过，而不是留一条空绑定）。
        """
        title_bar = getattr(getattr(self._window, "ui", None), "title_bar", None)
        anchor = title_bar.findChild(QPushButton, "btn_search") if title_bar is not None else None
        if anchor is None:
            return False
        self._handle_search_button(anchor)
        return True

    def _handle_settings_button(self):
        """标题栏设置按钮：打开独立设置窗口。"""
        self.settings_controller.open_settings_window()

    def open_settings_window(self) -> bool:
        """内置快捷键入口：打开独立设置窗口。"""
        return bool(self.settings_controller.open_settings_window())

    def open_settings_page(self, plugin_id: str, page_id: str = "") -> bool:
        """内置入口：打开独立设置窗口并定位到插件的指定设置页。"""
        opener = getattr(self.settings_controller, "open_settings_page", None)
        if not callable(opener):
            return False
        return bool(opener(plugin_id, page_id))

    def _handle_top_settings_button(self, btn):
        """顶栏设置按钮开合右列时，按抽屉的实际状态同步设置按钮。"""
        self.column_controller.handle_top_settings_button(btn)
        sync = getattr(self.settings_controller, "_sync_settings_button", None)
        if callable(sync):
            sync()
