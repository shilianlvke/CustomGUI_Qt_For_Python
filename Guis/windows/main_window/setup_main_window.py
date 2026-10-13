from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from .functions import MainFunctions
from .registry import get_default_page_object, get_menu_items, load_registered_pages
from GuiCore import CGrips
from AppCore import AppSettings, Language, Logger, MenuPlugin, get_plugin_registry
from Guis.app_loader import load_apps

BUILTIN_TITLE_MENU_PLUGINS = [
    MenuPlugin(
        plugin_id="builtin.menu.title.search",
        target="TitleMenu",
        item={
            "btn_icon": "icon_search",
            "btn_id": "btn_search",
            "btn_tooltip": "language.UI.ui_Search",
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.title.language",
        target="TitleMenu",
        item={
            "btn_icon": "icon_chinese",
            "btn_id": "btn_language",
            "btn_tooltip": "language.UI.ui_SwitchLanguage",
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.title.theme",
        target="TitleMenu",
        item={
            "btn_icon": "icon_moon",
            "btn_id": "btn_themes",
            "btn_tooltip": "language.UI.ui_SwitchTheme",
            "is_active": False,
        },
    ),
]


def register_builtin_title_menus():
    registry = get_plugin_registry()
    for plugin in BUILTIN_TITLE_MENU_PLUGINS:
        if plugin.plugin_id not in registry._menus:
            registry.register_menu(plugin)


class SetupMainWindow:
    def setup_btns(self):
        if self.ui.title_bar.sender() is not None:
            return self.ui.title_bar.sender()
        elif self.ui.left_menu.sender() is not None:
            return self.ui.left_menu.sender()
        elif self.ui.left_column.sender() is not None:
            return self.ui.left_column.sender()
        return None

    def setup_gui(self):
        Logger.debug("开始装配主窗口 UI")
        # 装载 Apps 目录下的应用模组（菜单 + 页面 + 语言）
        load_apps()
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
        # PAGES
        load_registered_pages(self)
        # 设置初始页面/设置左右列菜单（无任何应用时内容区留空）
        default_page = get_default_page_object()
        page = self.ui.load_pages.pages.findChild(QWidget, default_page) if default_page else None
        if page is not None:
            MainFunctions.set_page(self, page)
        # MainFunctions.set_left_column_menu(
        #     self,
        #     menu=self.ui.left_column.menus.menu_1,
        #     title="Settings Left Column",
        #     icon_path=PathFactory.set_svg_icon("icon_setting"),
        # )
        # MainFunctions.set_right_column_menu(self, self.ui.right_column.menu_1)

    def resize_grips(self):
        self.left_grip.setGeometry(5, 10, 10, self.height())
        self.right_grip.setGeometry(self.width() - 15, 10, 10, self.height())
        self.top_grip.setGeometry(5, 5, self.width() - 10, 10)
        self.bottom_grip.setGeometry(5, self.height() - 15, self.width() - 10, 10)
        # self.top_left_grip.setGeometry(5, 5, 15, 15)
        self.top_right_grip.setGeometry(self.width() - 20, 5, 15, 15)
        self.bottom_left_grip.setGeometry(5, self.height() - 20, 15, 15)
        self.bottom_right_grip.setGeometry(self.width() - 20, self.height() - 20, 15, 15)

    def menu_add_btn(self):
        register_builtin_title_menus()
        left_menu_items = get_menu_items("LeftMenu")
        title_menu_items = get_menu_items("TitleMenu")
        self.ui.left_menu.add_menus(left_menu_items)
        self.ui.title_bar.add_menus(title_menu_items)
        # 按钮绑定
        self.ui.left_menu.clicked.connect(self.btn_clicked)
        self.ui.left_menu.released.connect(self.btn_released)
        self.ui.left_column.clicked.connect(self.btn_clicked)
        self.ui.left_column.released.connect(self.btn_released)
        self.ui.title_bar.clicked.connect(self.btn_clicked)
        self.ui.title_bar.released.connect(self.btn_released)
