from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, PathFactory
from customgui.guicore import (
    CAppConfigurator,
    CBottomColumn,
    CCredits,
    CLeftColumn,
    CLeftMenu,
    CTitleBar,
    CTopColumn,
    CWindow,
    acrylic_active,
)
from customgui.guicore.window import Ui_RightColumn
from customgui.guis import Ui_MainPages


class UiMainWindow:
    def __init__(self):
        self.credits_layout = None
        self.credits = None
        self.credits_frame = None
        self.right_column = None
        self.content_area_right_bg_frame = None
        self.content_area_right_layout = None
        self.right_column_frame = None
        self.load_pages = None
        self.content_area_left_frame = None
        self.content_area_layout = None
        self.content_area_frame = None
        self.title_bar = None
        self.title_bar_layout = None
        self.right_app_layout = None
        self.right_app_frame = None
        self.title_bar_frame = None
        self.left_column = None
        self.left_column_layout = None
        self.left_column_frame = None
        self.top_column = None
        self.top_column_layout = None
        self.top_column_frame = None
        self.bottom_column = None
        self.bottom_column_layout = None
        self.bottom_column_frame = None
        self.left_menu = None
        self.left_menu_layout = None
        self.window = None
        self.central_widget_layout = None
        self.parent = None
        self.central_widget = None
        self.left_menu_frame = None

    def setup_ui(self, parent):
        self.parent = parent
        # 界面主体
        self.set_up_main_widget()
        # 界面左侧
        self.set_up_left_widget()
        # 界面右侧
        self.set_up_right_widget()
        # 添加至window
        self.add_widget_to_window()
        # window 配置
        self.config_enable()

    def set_up_main_widget(self):
        # 设置主体
        self.central_widget = QWidget()
        self.central_widget_layout = QVBoxLayout(self.central_widget)
        # 主Frame
        self.window = CWindow()
        # 将PyWindow添加到中心小部件
        self.central_widget_layout.addWidget(self.window)

    def set_up_left_widget(self):
        # 左侧菜单
        margin = AppSettings.left_menu_content_margins
        size = AppSettings.lef_menu_size.minimum
        self.left_menu_frame = QFrame()
        self.left_menu_frame.setMaximumSize(size + (margin * 2), 17280)
        self.left_menu_frame.setMinimumSize(size + (margin * 2), 0)
        self.left_menu_layout = QHBoxLayout(self.left_menu_frame)
        self.left_menu_layout.setContentsMargins(margin, margin, margin, margin)
        self.left_menu = CLeftMenu(parent=self.left_menu_frame, app_parent=self.central_widget)
        self.left_menu_layout.addWidget(self.left_menu)
        # 左侧抽屉（栏目卡片样式见 Styles.update_region_card_style）
        self.left_column_frame = QFrame()
        self.left_column_frame.setObjectName("CRegion_Card_Frame")
        self.left_column_frame.setMaximumWidth(AppSettings.left_column_size.minimum)
        self.left_column_frame.setMinimumWidth(AppSettings.left_column_size.minimum)
        self.left_column_layout = QVBoxLayout(self.left_column_frame)
        self.left_column_layout.setContentsMargins(0, 0, 0, 0)
        self.left_column = CLeftColumn(
            # parent,
            app_parent=self.central_widget,
            text_title="",
            text_title_size=AppSettings.title_size,
            icon_path=PathFactory.set_svg_icon("icon_setting"),
            icon_close_path=PathFactory.set_svg_icon("icon_close"),
            font_family=AppSettings.family,
        )
        self.left_column_layout.addWidget(self.left_column)

    def set_up_right_widget(self):
        self.right_app_frame = QFrame()
        self.right_app_layout = QVBoxLayout(self.right_app_frame)
        margin = AppSettings.right_menu_content_margins
        self.right_app_layout.setContentsMargins(margin, margin, margin, margin)
        self.right_app_layout.setSpacing(AppSettings.right_content_space)
        # 添加标题栏框架、布局
        self.title_bar_frame = QFrame()
        self.title_bar_frame.setFixedHeight(AppSettings.right_title_bar_height)
        self.title_bar_layout = QVBoxLayout(self.title_bar_frame)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar = CTitleBar(self.parent, self.central_widget)
        self.title_bar_layout.addWidget(self.title_bar)
        # 添加内容框架、布局
        self.content_area_frame = QFrame()
        self.content_area_layout = QHBoxLayout(self.content_area_frame)
        self.content_area_layout.setContentsMargins(0, 0, 0, 0)
        # 两块区域卡片之间留出间距，各自成为一块独立的板面
        self.content_area_layout.setSpacing(AppSettings.right_content_space)
        # 左侧内容：主内容区背景卡片，插件页面都渲染在这张卡片之上
        self.content_area_left_frame = QFrame()
        self.content_area_left_frame.setObjectName("CRegion_Card_Frame")
        # 将主页导入到内容区域
        self.load_pages = Ui_MainPages()
        self.load_pages.setupUi(self.content_area_left_frame)
        # 页面与背景卡片齐平（uic 生成的布局默认 0 边距，这里显式钉住）：
        # 只要留一点内缩，卡片边缘就会露出一圈底色窄环，页面像被"装裱"在卡片里
        self.load_pages.Main_layout.setContentsMargins(0, 0, 0, 0)
        # 右侧工具栏
        self.right_column_frame = QFrame()
        self.right_column_frame.setObjectName("CRegion_Card_Frame")
        self.right_column_frame.setMinimumWidth(AppSettings.right_column_size.minimum)
        self.right_column_frame.setMaximumWidth(AppSettings.right_column_size.minimum)
        # 导入右列
        self.content_area_right_layout = QVBoxLayout(self.right_column_frame)
        # 右列内容同样与卡片齐平（内缩量交给右列自身的页面处理）
        self.content_area_right_layout.setContentsMargins(0, 0, 0, 0)
        self.content_area_right_layout.setSpacing(0)
        # 右背景
        self.content_area_right_bg_frame = QFrame()
        # ADD BG
        self.content_area_right_layout.addWidget(self.content_area_right_bg_frame)
        # ADD RIGHT PAGES TO RIGHT COLUMN
        self.right_column = Ui_RightColumn()
        self.right_column.setupUi(self.content_area_right_bg_frame)
        # 右侧抽屉的“主题配置”页：复用 CAppConfigurator 的配置内容，但以嵌入
        # 模式运行（无固定宽度、无滑入动画、无自身背景），开合交给右侧栏。
        self.theme_menu = QWidget()
        self.theme_menu.setObjectName("themeMenu")
        self.theme_menu_layout = QVBoxLayout(self.theme_menu)
        self.theme_menu_layout.setContentsMargins(0, 0, 0, 0)
        self.theme_menu_layout.setSpacing(0)
        self.theme_config = CAppConfigurator(self.theme_menu, embedded=True)
        self.theme_menu_layout.addWidget(self.theme_config)
        self.right_column.menus.addWidget(self.theme_menu)
        # ADD TO LAYOUTS
        self.content_area_layout.addWidget(self.content_area_left_frame)
        self.content_area_layout.addWidget(self.right_column_frame)
        # CREDITS / BOTTOM APP FRAME
        # ///////////////////////////////////////////////////////////////
        self.credits_frame = QFrame()
        self.credits_frame.setFixedHeight(AppSettings.right_credits_height)
        # CREATE LAYOUT
        self.credits_layout = QVBoxLayout(self.credits_frame)
        self.credits_layout.setContentsMargins(0, 0, 0, 0)
        # ADD CUSTOM WIDGET CREDITS
        self.credits = CCredits()
        #  ADD TO LAYOUT
        self.credits_layout.addWidget(self.credits)
        # 顶部抽屉：标题栏下方、内容区上方（结构同左列，见 CTopColumn）
        # 闭合同步钳住 min/max（开合动画成对改两个属性），避免 min>max 的布局病态
        self.top_column_frame = QFrame()
        self.top_column_frame.setObjectName("CRegion_Card_Frame")
        self.top_column_frame.setMaximumHeight(AppSettings.top_column_size.minimum)
        self.top_column_frame.setMinimumHeight(AppSettings.top_column_size.minimum)
        self.top_column_layout = QVBoxLayout(self.top_column_frame)
        self.top_column_layout.setContentsMargins(0, 0, 0, 0)
        self.top_column = CTopColumn(
            app_parent=self.central_widget,
            text_title="",
            text_title_size=AppSettings.title_size,
            icon_path=PathFactory.set_svg_icon("icon_setting"),
            icon_close_path=PathFactory.set_svg_icon("icon_close"),
            font_family=AppSettings.family,
        )
        self.top_column_layout.addWidget(self.top_column)
        # 底部抽屉：内容区下方、版权栏上方（结构同左列，见 CBottomColumn）
        self.bottom_column_frame = QFrame()
        self.bottom_column_frame.setObjectName("CRegion_Card_Frame")
        self.bottom_column_frame.setMaximumHeight(AppSettings.bottom_column_size.minimum)
        self.bottom_column_frame.setMinimumHeight(AppSettings.bottom_column_size.minimum)
        self.bottom_column_layout = QVBoxLayout(self.bottom_column_frame)
        self.bottom_column_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_column = CBottomColumn(
            app_parent=self.central_widget,
            text_title="",
            text_title_size=AppSettings.title_size,
            icon_path=PathFactory.set_svg_icon("icon_setting"),
            icon_close_path=PathFactory.set_svg_icon("icon_close"),
            font_family=AppSettings.family,
        )
        self.bottom_column_layout.addWidget(self.bottom_column)
        # 将小部件添加到右侧布局
        self.right_app_layout.addWidget(self.title_bar_frame)
        self.right_app_layout.addWidget(self.top_column_frame)
        self.right_app_layout.addWidget(self.content_area_frame)
        self.right_app_layout.addWidget(self.bottom_column_frame)
        self.right_app_layout.addWidget(self.credits_frame)

    def add_widget_to_window(self):
        self.window.layout.addWidget(self.left_menu_frame)
        self.window.layout.addWidget(self.left_column_frame)
        self.window.layout.addWidget(self.right_app_frame)

    def config_enable(self):
        # 添加中心小部件并设置内容边距
        self.parent.setCentralWidget(self.central_widget)
        if AppSettings.custom_title_bar:
            # 10px 外圈原本是给 QGraphicsDropShadowEffect 留的投影空间。
            # 亚克力模式下阴影关闭，这 10px 只剩一条透出壁纸的"外包装"，
            # 看起来像在主界面外面又套了一层。此时让 CWindow 直接铺满窗口：
            # 主界面就是背景，原生材质与主界面边界完全重合。
            margin = 0 if acrylic_active() else 10
            self.central_widget_layout.setContentsMargins(margin, margin, margin, margin)
        else:
            self.window.set_stylesheet(border_radius=0, border_size=0)
            self.central_widget_layout.setContentsMargins(0, 0, 0, 0)
