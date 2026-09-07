"""主窗口装配流程模块。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from AppCore import MenuPlugin, get_plugin_registry, get_token_manager
from guicore import CGrips

from .functions import MainFunctions
from .user_define_pages import get_default_page_object, get_menu_items, load_registered_pages

BUILTIN_TITLE_MENU_PLUGINS = [
    MenuPlugin(
        plugin_id="builtin.menu.title.search",
        target="TitleMenu",
        item={
            "btn_icon": "icon_search",
            "btn_id": "btn_search",
            "btn_tooltip": "搜索",
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.title.language",
        target="TitleMenu",
        item={
            "btn_icon": "icon_chinese",
            "btn_id": "btn_language",
            "btn_tooltip": "切换语言",
            "is_active": False,
        },
    ),
    MenuPlugin(
        plugin_id="builtin.menu.title.theme",
        target="TitleMenu",
        item={
            "btn_icon": "icon_moon",
            "btn_id": "btn_themes",
            "btn_tooltip": "切换主题",
            "is_active": False,
        },
    ),
]


def register_builtin_title_menus() -> None:
    """注册内置标题栏菜单插件。

    返回:
    - None
    """
    registry = get_plugin_registry()
    for plugin in BUILTIN_TITLE_MENU_PLUGINS:
        if not registry.has_menu(plugin.plugin_id):
            registry.register_menu(plugin)


class SetupMainWindow:
    """主窗口装配器。

    职责:
    - 完成窗口基础装配、菜单注入与页面初始化。
    - 提供窗口尺寸夹点与按钮来源解析等辅助能力。

    说明:
    - 方法均为静态方法，显式接收 ``window`` 参数，避免类方法式调用造成的歧义。
    """

    @staticmethod
    def setup_btns(window: object) -> object | None:
        """获取当前触发信号的按钮对象。

        参数:
        - window: 主窗口对象。

        返回:
        - QObject | None: 发送信号的按钮对象。
        """
        if window.ui.title_bar.sender() is not None:
            return window.ui.title_bar.sender()
        if window.ui.left_menu.sender() is not None:
            return window.ui.left_menu.sender()
        if window.ui.left_column.sender() is not None:
            return window.ui.left_column.sender()
        return None

    @staticmethod
    def setup_gui(window: object) -> None:
        """执行主窗口 UI 装配流程。

        参数:
        - window: 主窗口对象。

        返回:
        - None
        """
        # 添加标题描述
        window.setWindowTitle(get_token_manager().language.custom_ui.sys_name)
        window.ui.title_bar.set_title(get_token_manager().language.custom_ui.sys_name)
        if get_token_manager().settings.custom_title_bar:
            # 去除标题栏
            window.setWindowFlag(Qt.FramelessWindowHint)
            window.setAttribute(Qt.WA_TranslucentBackground)
            # 添加夹点
            hide_grips = get_token_manager().settings.hide_grips
            window.left_grip = CGrips(window, "left", disable_color=hide_grips)
            window.right_grip = CGrips(window, "right", disable_color=hide_grips)
            window.top_grip = CGrips(window, "top", disable_color=hide_grips)
            window.bottom_grip = CGrips(window, "bottom", disable_color=hide_grips)
            window.top_left_grip = CGrips(window, "top_left", disable_color=hide_grips)
            window.top_right_grip = CGrips(window, "top_right", disable_color=hide_grips)
            window.bottom_left_grip = CGrips(window, "bottom_left", disable_color=hide_grips)
            window.bottom_right_grip = CGrips(window, "bottom_right", disable_color=hide_grips)
            SetupMainWindow.resize_grips(window)
        # 加载按钮
        SetupMainWindow.menu_add_btn(window)
        # PAGES
        load_registered_pages(window)
        # 设置初始页面/设置左右列菜单
        default_page = get_default_page_object()
        MainFunctions.set_page(window, window.ui.load_pages.pages.findChild(QWidget, default_page))

    @staticmethod
    def resize_grips(window: object) -> None:
        """根据窗口尺寸更新边缘夹点位置。

        参数:
        - window: 主窗口对象。

        返回:
        - None
        """
        window.left_grip.setGeometry(5, 10, 10, window.height())
        window.right_grip.setGeometry(window.width() - 15, 10, 10, window.height())
        window.top_grip.setGeometry(5, 5, window.width() - 10, 10)
        window.bottom_grip.setGeometry(5, window.height() - 15, window.width() - 10, 10)
        window.top_right_grip.setGeometry(window.width() - 20, 5, 15, 15)
        window.bottom_left_grip.setGeometry(5, window.height() - 20, 15, 15)
        window.bottom_right_grip.setGeometry(window.width() - 20, window.height() - 20, 15, 15)

    @staticmethod
    def menu_add_btn(window: object) -> None:
        """注入菜单并绑定按钮事件。

        参数:
        - window: 主窗口对象。

        返回:
        - None
        """
        register_builtin_title_menus()
        left_menu_items = get_menu_items("LeftMenu")
        title_menu_items = get_menu_items("TitleMenu")
        window.ui.left_menu.add_menus(left_menu_items)
        window.ui.title_bar.add_menus(title_menu_items)
        # 按钮绑定
        window.ui.left_menu.clicked.connect(window.btn_clicked)
        window.ui.left_menu.released.connect(window.btn_released)
        window.ui.left_column.clicked.connect(window.btn_clicked)
        window.ui.left_column.released.connect(window.btn_released)
        window.ui.title_bar.clicked.connect(window.btn_clicked)
        window.ui.title_bar.released.connect(window.btn_released)
