from GUI import Ui_RightColumn
from GUI import Ui_MainPages
from GuiCore import CLeftMenu, CLeftColumn, CWindow, CTitleBar, CCredits
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from AppCore import PathFactory, ColorPalette, Language, AppSettings


class UiMainWindow(object):

    def __init__(self):
        self.parent = None
        self.credits = None
        self.credits_layout = None
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
        self.title_bar_frame = None
        self.right_app_layout = None
        self.right_app_frame = None
        self.left_column = None
        self.left_column_layout = None
        self.left_column_frame = None
        self.left_menu = None
        self.left_menu_layout = None
        self.left_menu_frame = None
        self.window = None
        self.central_widget_layout = None
        self.central_widget = None

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
        # 左侧抽屉
        self.left_column_frame = QFrame()
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
        self.content_area_layout.setSpacing(0)
        # 左侧内容
        self.content_area_left_frame = QFrame()
        # 将主页导入到内容区域
        self.load_pages = Ui_MainPages()
        self.load_pages.setupUi(self.content_area_left_frame)
        # 右侧工具栏
        self.right_column_frame = QFrame()
        self.right_column_frame.setMinimumWidth(AppSettings.right_column_size.minimum)
        self.right_column_frame.setMaximumWidth(AppSettings.right_column_size.minimum)
        # 导入右列
        self.content_area_right_layout = QVBoxLayout(self.right_column_frame)
        self.content_area_right_layout.setContentsMargins(5, 5, 5, 5)
        self.content_area_right_layout.setSpacing(0)
        # 右背景
        self.content_area_right_bg_frame = QFrame()
        # self.content_area_right_bg_frame.setObjectName("content_area_right_bg_frame")
        # self.content_area_right_bg_frame.setStyleSheet(f"""
        # #content_area_right_bg_frame {{
        #     border-radius: 8px;
        #     background-color: {ColorPalette.custom_bg_two};
        # }}
        # """)
        # ADD BG
        self.content_area_right_layout.addWidget(self.content_area_right_bg_frame)
        # ADD RIGHT PAGES TO RIGHT COLUMN
        self.right_column = Ui_RightColumn()
        self.right_column.setupUi(self.content_area_right_bg_frame)
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
        # 将小部件添加到右侧布局
        self.right_app_layout.addWidget(self.title_bar_frame)
        self.right_app_layout.addWidget(self.content_area_frame)
        self.right_app_layout.addWidget(self.credits_frame)

    def add_widget_to_window(self):
        # 将控件添加到“PyWindow”
        self.window.layout.addWidget(self.left_menu_frame)
        self.window.layout.addWidget(self.left_column_frame)
        self.window.layout.addWidget(self.right_app_frame)

    def config_enable(self):
        # 添加中心小部件并设置内容边距
        self.parent.setCentralWidget(self.central_widget)
        if AppSettings.custom_title_bar:
            self.central_widget_layout.setContentsMargins(10, 10, 10, 10)
        else:
            self.window.set_stylesheet(border_radius=0, border_size=0)
            self.central_widget_layout.setContentsMargins(0, 0, 0, 0)
