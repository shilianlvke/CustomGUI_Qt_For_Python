"""主窗口装配流程模块。"""

from PySide6.QtCore import QMargins, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget

from AppCore import AppSettings, ColorPalette, Language, Logger, MenuPlugin, PathFactory, get_plugin_registry
from GuiCore import CCard, CComboBox, CGrips, CMenu, CMenuButton, CPushButton, CShowCard, CStatusButton

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
    """

    def setup_btns(self) -> object | None:
        """获取当前触发信号的按钮对象。

        返回:
        - QObject | None: 发送信号的按钮对象。
        """
        if self.ui.title_bar.sender() is not None:
            return self.ui.title_bar.sender()
        if self.ui.left_menu.sender() is not None:
            return self.ui.left_menu.sender()
        if self.ui.left_column.sender() is not None:
            return self.ui.left_column.sender()
        return None

    def setup_gui(self) -> None:
        """执行主窗口 UI 装配流程。

        返回:
        - None
        """
        # 添加标题描述
        self.setWindowTitle(Language.custom_ui.sys_name)
        self.ui.title_bar.set_title(Language.custom_ui.sys_name)
        if AppSettings.custom_title_bar:
            # 去除标题栏
            self.setWindowFlag(Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            # 添加夹点
            self.left_grip = CGrips(self, "left", disable_color=AppSettings.hide_grips)
            self.right_grip = CGrips(self, "right", disable_color=AppSettings.hide_grips)
            self.top_grip = CGrips(self, "top", disable_color=AppSettings.hide_grips)
            self.bottom_grip = CGrips(self, "bottom", disable_color=AppSettings.hide_grips)
            self.top_left_grip = CGrips(self, "top_left", disable_color=AppSettings.hide_grips)
            self.top_right_grip = CGrips(self, "top_right", disable_color=AppSettings.hide_grips)
            self.bottom_left_grip = CGrips(self, "bottom_left", disable_color=AppSettings.hide_grips)
            self.bottom_right_grip = CGrips(self, "bottom_right", disable_color=AppSettings.hide_grips)
            SetupMainWindow.resize_grips(self)
        # 加载按钮
        SetupMainWindow.menu_add_btn(self)
        # PAGES
        load_registered_pages(self)
        # 设置初始页面/设置左右列菜单
        default_page = get_default_page_object()
        MainFunctions.set_page(self, self.ui.load_pages.pages.findChild(QWidget, default_page))

    def load_page1(self) -> None:
        """预留页面加载入口。"""

    def load_page2(self) -> None:  # noqa: PLR0915
        """构建组件展示页示例内容。

        返回:
        - None
        """
        page_layout = QVBoxLayout(self.ui.load_pages.widget_show)
        page_layout.setContentsMargins(QMargins(0, 0, 0, 0))

        back_card = CCard()
        back_layout = QVBoxLayout(back_card)
        back_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        page_layout.addWidget(back_card)

        card = CCard()
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        scroller_area = QScrollArea()
        scroller_area.setWidget(card)
        scroller_area.setWidgetResizable(True)
        scroller_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroller_area.setStyleSheet(f"background-color:{ColorPalette.custom_dark_three};")
        back_layout.addWidget(scroller_area)

        stander_btn = CPushButton(text="标准按钮")
        stander_btn.clicked.connect(lambda: Logger.info("点击了标准按钮"))
        icon_btn = CPushButton(size=QSize(64, 64), icon=PathFactory.set_jpg_image("托盘"))
        icon_btn.clicked.connect(lambda: Logger.info("点击了图片按钮"))
        trans_btn = CPushButton(text="透明按钮", is_transparent=True)
        trans_btn.clicked.connect(lambda: Logger.info("点击了透明按钮"))
        text_icon_btn = CPushButton(
            size=QSize(128, 32),
            icon=QIcon(PathFactory.set_svg_icon("icon_heart")),
            text="QIcon-文字按钮",
        )
        text_icon_btn.clicked.connect(lambda: Logger.info("点击了文字按钮"))
        two_btn = CStatusButton(
            size=QSize(64, 32),
            radius=16,
            icon_negative=QIcon(PathFactory.set_svg_icon("icon_arrow_left")),
            icon_positive=QIcon(PathFactory.set_svg_icon("icon_arrow_right")),
            text_negative="左",
            text_positive="右",
        )
        two_btn.clicked.connect(lambda: Logger.info(f"点击了双态按钮当前状态{two_btn.status}"))
        three_btn = CStatusButton(
            size=QSize(64, 32),
            radius=16,
            icon_negative=QIcon(PathFactory.set_svg_icon("icon_arrow_down")),
            icon_normal=QIcon(PathFactory.set_svg_icon("icon_arrow_left")),
            icon_positive=QIcon(PathFactory.set_svg_icon("icon_arrow_right")),
            text_negative="中",
            text_normal="左",
            text_positive="右",
            is_normal=True,
        )
        three_btn.clicked.connect(lambda: Logger.info(f"点击了三态按钮当前状态{three_btn.status}"))
        menu_btn = CMenuButton(
            colorpalette=ColorPalette,
            text="邮件",
            icon=QIcon(PathFactory.set_svg_icon("icon_mail")),
        )
        menu_btn.clicked.connect(lambda: Logger.info("点击了菜单按钮"))
        menu = CMenu(self, colorpalette=ColorPalette)
        f1 = menu.addAction(QIcon(PathFactory.set_svg_icon("icon_save")), "保存")
        f2 = menu.addAction(QIcon(PathFactory.set_svg_icon("icon_mail_send")), "发送")
        f1.triggered.connect(lambda: Logger.info("点击了菜单按钮保存"))
        f2.triggered.connect(lambda: Logger.info("点击了菜单按钮发送"))
        menu_btn.setMenu(menu)
        combo_box_0 = CComboBox(size=QSize(120, 30), items=["提莫", "亚索", "阿狸"], placeholder_text="选择你的英雄")
        combo_box_0.currentIndexChanged.connect(lambda: Logger.info(f"改变了下拉框值{combo_box_0.currentIndex()}"))
        card_1 = CShowCard(None, Language.custom_ui.sys_github, "标准按钮", stander_btn)
        card_2 = CShowCard(None, Language.custom_ui.sys_github, "图标按钮", icon_btn)
        card_3 = CShowCard(None, Language.custom_ui.sys_github, "透明按钮", trans_btn)
        card_4 = CShowCard(None, Language.custom_ui.sys_github, "QIcon-文字按钮", text_icon_btn)
        card_5 = CShowCard(None, Language.custom_ui.sys_github, "双态按钮", two_btn)
        card_6 = CShowCard(None, Language.custom_ui.sys_github, "三态按钮", three_btn)
        card_7 = CShowCard(None, Language.custom_ui.sys_github, "菜单按钮", menu_btn)
        card_8 = CShowCard(None, Language.custom_ui.sys_github, "下拉框", combo_box_0)
        card_layout.addWidget(card_1, 0, 0)
        card_layout.addWidget(card_2, 0, 1)
        card_layout.addWidget(card_3, 0, 2)
        card_layout.addWidget(card_4, 0, 3)
        card_layout.addWidget(card_5)
        card_layout.addWidget(card_6)
        card_layout.addWidget(card_7)
        card_layout.addWidget(card_8)

    def resize_grips(self) -> None:
        """根据窗口尺寸更新边缘夹点位置。

        返回:
        - None
        """
        self.left_grip.setGeometry(5, 10, 10, self.height())
        self.right_grip.setGeometry(self.width() - 15, 10, 10, self.height())
        self.top_grip.setGeometry(5, 5, self.width() - 10, 10)
        self.bottom_grip.setGeometry(5, self.height() - 15, self.width() - 10, 10)
        self.top_right_grip.setGeometry(self.width() - 20, 5, 15, 15)
        self.bottom_left_grip.setGeometry(5, self.height() - 20, 15, 15)
        self.bottom_right_grip.setGeometry(self.width() - 20, self.height() - 20, 15, 15)

    def menu_add_btn(self) -> None:
        """注入菜单并绑定按钮事件。

        返回:
        - None
        """
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
