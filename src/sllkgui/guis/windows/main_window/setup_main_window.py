from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from sllkgui.appcore import (
    LANGUAGE_OPTIONS,
    AppSettings,
    AppThemes,
    Language,
    Logger,
    get_theme_manager,
    load_user_settings,
)
from sllkgui.guicore import CGrips, set_acrylic_transparency, set_glass_strength

from .functions import MainFunctions
from .registry import (
    ensure_registered_page,
    get_default_page_object,
    get_menu_items,
    get_page_routes,
    load_registered_pages,
)


class SetupMainWindow:
    def __init__(self):
        self.bottom_right_grip = None
        self.bottom_left_grip = None
        self.top_right_grip = None
        self.top_left_grip = None
        self.bottom_grip = None
        self.top_grip = None
        self.right_grip = None
        self.left_grip = None
        self.ui = None

    def setup_btns(self):
        if self.ui.title_bar.sender() is not None:
            return self.ui.title_bar.sender()
        elif self.ui.left_menu.sender() is not None:
            return self.ui.left_menu.sender()
        elif self.ui.left_column.sender() is not None:
            return self.ui.left_column.sender()
        elif self.ui.top_column.sender() is not None:
            return self.ui.top_column.sender()
        elif self.ui.bottom_column.sender() is not None:
            return self.ui.bottom_column.sender()
        return None

    def setup_gui(self):
        Logger.debug("开始装配主窗口 UI")
        # 先恢复用户上次保存的主题 / 语言 / 窗口尺寸，再装载应用与页面，
        # 保证菜单文案、页面语言与窗口几何一次到位（避免启动后再重建）。
        user_state = SetupMainWindow.restore_ui_state(self)
        # 添加标题描述
        self.setWindowTitle(Language.custom_ui.sys_name)
        self.ui.title_bar.set_title(Language.custom_ui.sys_name)
        if AppSettings.custom_title_bar:
            # 去除标题栏
            self.setWindowFlag(Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            # 添加夹点
            self.left_grip = CGrips(self, "left", AppSettings.hide_grips)
            self.right_grip = CGrips(self, "right", AppSettings.hide_grips)
            self.top_grip = CGrips(self, "top", AppSettings.hide_grips)
            self.bottom_grip = CGrips(self, "bottom", AppSettings.hide_grips)
            self.top_left_grip = CGrips(self, "top_left", AppSettings.hide_grips)
            self.top_right_grip = CGrips(self, "top_right", AppSettings.hide_grips)
            self.bottom_left_grip = CGrips(self, "bottom_left", AppSettings.hide_grips)
            self.bottom_right_grip = CGrips(self, "bottom_right", AppSettings.hide_grips)
            SetupMainWindow.resize_grips(self)
        # 加载按钮
        SetupMainWindow.menu_add_btn(self)
        # 菜单模式依赖菜单按钮已就位，放在按钮创建之后再恢复
        SetupMainWindow.restore_menu_mode(self, user_state)
        # 抽屉模式决定四个抽屉的容器形态，须在任何抽屉打开之前应用
        SetupMainWindow.restore_drawer_mode(self, user_state)
        # PAGES (default page only; others are built on first navigation)
        load_registered_pages(self, eager=False)
        # 设置初始页面/设置左右列菜单（无任何应用时内容区留空）
        default_page = get_default_page_object()
        if default_page:
            ensure_registered_page(self, default_page)
        page = self.ui.load_pages.pages.findChild(QWidget, default_page) if default_page else None
        if page is not None:
            MainFunctions.set_page(self, page)
            try:
                routes = get_page_routes(Language)
                active = next((route for route in routes.values() if route[0] == default_page), None)
                if active:
                    self.ui.title_bar.set_title(active[1])
            except (AttributeError, KeyError, TypeError) as exc:
                Logger.debug(f"无法设置初始页面标题: {exc}")
        # MainFunctions.set_left_column_menu(
        #     self,
        #     menu=self.ui.left_column.menus.menu_1,
        #     title="Settings Left Column",
        #     icon_path=PathFactory.set_svg_icon("icon_setting"),
        # )
        # MainFunctions.set_right_column_menu(self, self.ui.right_column.menu_1)
        SetupMainWindow.clamp_to_screen(self)

    @staticmethod
    def restore_ui_state(window) -> dict:
        """恢复用户上次保存的主题 / 语言 / 窗口尺寸 / 材质参数。

        用户配置是 ``<data_root>/settings/user.yaml`` 增量覆盖层，优先级高于
        基座默认值与品牌层；缺失或非法的字段保持下层配置。窗口尺寸会在
        ``clamp_to_screen`` 中再夹到当前屏幕可用区域。
        """
        state = load_user_settings()

        # 材质参数必须在主题之前恢复：主题切换会重建全局样式，样式里的
        # 玻璃层透明度直接读取当前强度。
        appearance_applied = SetupMainWindow.restore_appearance(window, state)
        # 背景图与主题无关，先于样式重建恢复；无效路径由 CWindow 自动回落到纯色。
        SetupMainWindow.restore_background(window, state)

        theme_applied = False
        theme = state.get("theme_name")
        if isinstance(theme, str) and theme in AppThemes:
            get_theme_manager().apply(theme)
            theme_applied = True

        language = state.get("language")
        if isinstance(language, str) and language in LANGUAGE_OPTIONS and language != Language.current():
            Language.apply(language)

        size = state.get("startup_size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                width, height = int(size[0]), int(size[1])
            except (TypeError, ValueError):
                width = height = 0
            if width > 0 and height > 0:
                window.resize(width, height)

        # 主题变更会重建样式；只恢复了材质参数时也要立即重建一次，
        # 否则启动后要等到下一次主题切换才生效。
        if theme_applied or appearance_applied:
            apply_style = getattr(getattr(window.ui, "window", None), "apply_style", None)
            if callable(apply_style):
                apply_style()
        return state

    @staticmethod
    def restore_appearance(window, state: dict) -> bool:
        """恢复窗口透明度与亚克力质感强度，返回是否读到了合法配置。"""
        transparency = state.get("acrylic_transparency")
        strength = state.get("glass_strength")
        transparency = transparency if isinstance(transparency, int) and not isinstance(transparency, bool) else None
        strength = strength if isinstance(strength, int) and not isinstance(strength, bool) else None
        applied = transparency is not None or strength is not None
        if transparency is not None:
            set_acrylic_transparency(transparency)
        if strength is not None:
            set_glass_strength(strength)
        config = getattr(getattr(window, "ui", None), "theme_config", None)
        setter = getattr(config, "set_appearance", None)
        if callable(setter):
            setter(transparency=transparency, strength=strength)
        return applied

    @staticmethod
    def restore_background(window, state: dict) -> bool:
        """恢复用户选择的背景图与适应模式，返回是否成功应用到窗口。"""
        path = state.get("background_image")
        fit = state.get("background_fit")
        widget = getattr(getattr(window, "ui", None), "window", None)
        setter = getattr(widget, "set_background_image", None)
        if not callable(setter):
            return False
        return bool(
            setter(
                path if isinstance(path, str) else "",
                fit if isinstance(fit, str) else "fill",
            )
        )

    @staticmethod
    def restore_menu_mode(window, state: dict) -> None:
        """按用户配置恢复左菜单 Static / Overlay 模式并同步抽屉选中态。"""
        mode = state.get("menu_mode")
        if not isinstance(mode, str) or mode not in ("static", "overlay"):
            return
        try:
            MainFunctions.set_menu_mode(window, mode)
        except Exception as exc:  # noqa: BLE001 - 菜单恢复失败不应阻断启动
            Logger.warning(f"恢复菜单模式失败，回退 Static: {exc}")
            return
        config = getattr(getattr(window, "ui", None), "theme_config", None)
        setter = getattr(config, "set_menu_mode", None)
        if callable(setter):
            setter(mode)

    @staticmethod
    def restore_drawer_mode(window, state: dict) -> None:
        """按用户配置恢复四向抽屉的 Static / Overlay 模式并同步选中态。

        未配置时显式应用 ``static``：外观面板默认以浮层形态创建，必须在这里
        统一收进右列，才能与「固定」的语义一致。
        """
        mode = state.get("drawer_mode")
        if not isinstance(mode, str) or mode not in ("static", "overlay"):
            mode = "static"
        try:
            MainFunctions.set_drawer_mode(window, mode)
        except Exception as exc:  # noqa: BLE001 - 抽屉恢复失败不应阻断启动
            Logger.warning(f"恢复抽屉模式失败，回退 Static: {exc}")
            return
        config = getattr(getattr(window, "ui", None), "theme_config", None)
        setter = getattr(config, "set_drawer_mode", None)
        if callable(setter):
            setter(mode)

    @staticmethod
    def clamp_to_screen(window):
        """把启动尺寸夹到当前屏幕的可用逻辑尺寸内。

        高 DPI（如 150%）下 ``startup_size`` 是逻辑像素，但配置文件里的
        1280×840 可能大于逻辑屏幕 1280×800，窗口底部与右侧会被裁掉。
        这里只缩小、不放大，正常 DPI 下不改变任何窗口尺寸。
        """
        screen = window.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = min(window.width(), available.width())
        height = min(window.height(), available.height())
        if width != window.width() or height != window.height():
            window.resize(width, height)
            Logger.debug(f"启动尺寸已夹到屏幕可用区域: {width}x{height}")

    def resize_grips(self):
        grips = AppSettings.grips
        corner_size = int(grips.corner_size)
        corner_offset = int(grips.corner_offset)
        corner_inset = int(grips.corner_inset)
        edge_size = int(grips.edge_size)
        self.left_grip.setGeometry(corner_offset, edge_size, edge_size, self.height())
        self.right_grip.setGeometry(
            self.width() - corner_size, edge_size, edge_size, self.height()
        )
        self.top_grip.setGeometry(
            corner_offset, corner_offset, self.width() - edge_size, edge_size
        )
        self.bottom_grip.setGeometry(
            corner_offset, self.height() - corner_size, self.width() - edge_size, edge_size
        )
        # self.top_left_grip.setGeometry(5, 5, 15, 15)
        self.top_right_grip.setGeometry(
            self.width() - corner_inset, corner_offset, corner_size, corner_size
        )
        self.bottom_left_grip.setGeometry(
            corner_offset, self.height() - corner_inset, corner_size, corner_size
        )
        self.bottom_right_grip.setGeometry(
            self.width() - corner_inset,
            self.height() - corner_inset,
            corner_size,
            corner_size,
        )

    def menu_add_btn(self):
        left_menu_items = get_menu_items("LeftMenu")
        title_menu_items = get_menu_items("TitleMenu")
        self.ui.left_menu.add_menus(left_menu_items)
        self.ui.title_bar.add_menus(title_menu_items)
        # 按钮绑定
        self.ui.left_menu.clicked.connect(self.btn_clicked)
        self.ui.left_menu.released.connect(self.btn_released)
        self.ui.left_column.clicked.connect(self.btn_clicked)
        self.ui.left_column.released.connect(self.btn_released)
        self.ui.top_column.clicked.connect(self.btn_clicked)
        self.ui.top_column.released.connect(self.btn_released)
        self.ui.bottom_column.clicked.connect(self.btn_clicked)
        self.ui.bottom_column.released.connect(self.btn_released)
        self.ui.title_bar.clicked.connect(self.btn_clicked)
        self.ui.title_bar.released.connect(self.btn_released)
