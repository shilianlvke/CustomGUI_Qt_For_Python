from qt_core import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    Qt,
    Signal,
    QWidget,
)
from .left_button import PyLeftButton
from .icon import PyIcon
from AppCore import ColorPalette, Language, get_theme_manager


class CLeftColumn(QWidget):
    # SIGNALS
    clicked = Signal(object)
    released = Signal(object)

    def __init__(
        self,
        # parent,
        app_parent,
        text_title,
        text_title_size,
        icon_path,
        icon_close_path,
        font_family,
        radius=8,
    ):
        super().__init__()

        # 参数（颜色实时读取 ColorPalette，主题切换自动生效）
        self._app_parent = app_parent
        self._title_key = text_title
        self._text_title_size = text_title_size
        self._icon_path = icon_path
        self._icon_close_path = icon_close_path
        self._radius = radius
        self._family = font_family
        self.setup_ui()

        # 在BG框架中添加左列（惰性导入，避免 GuiCore <-> Guis 循环导入）
        from Guis import Ui_LeftColumn

        self.menus = Ui_LeftColumn()
        self.menus.setupUi(self.content_frame)

        # CONNECT SIGNALS
        self.btn_close.clicked.connect(self.btn_clicked)
        self.btn_close.released.connect(self.btn_released)

        # 订阅主题/语言变更（弱引用，随组件生命周期）
        get_theme_manager().subscribe(self.update_style)
        Language.subscribe(self.apply_language)

    # 标题左列发出信号
    def btn_clicked(self):
        self.clicked.emit(self.btn_close)

    def btn_released(self):
        self.released.emit(self.btn_close)

    def set_title(self, title):
        """设置标题（支持 ``language.*`` 资源键，语言切换自动重新解析）。"""
        self._title_key = title
        self.title_label.setText(Language.resolve_key(title))

    def apply_language(self):
        """语言切换回调：刷新标题与关闭按钮提示。"""
        self.title_label.setText(Language.resolve_key(self._title_key))
        self.btn_close.set_tooltip(Language.resolve_key("language.UI.ui_Close"))

    def update_style(self):
        """主题切换回调：重建内联样式并重新着色图标。"""
        self.title_bg_frame.setStyleSheet(
            f"""
            #title_bg_frame {{
                background-color: {ColorPalette.custom_bg_three};
                border-radius: {self._radius}px;
            }}
            """
        )
        self.title_label.setStyleSheet(
            f"""
            #title_label {{
                font-size: {self._text_title_size}pt;
                color: {ColorPalette.custom_text_foreground};
                padding-bottom: 2px;
                background: none;
                font: 700 9pt "{self._family}";
            }}
            """
        )
        self.icon.set_icon(self._icon_path, ColorPalette.custom_icon_color)
        self.repaint()

    def setup_ui(self):
        # 基础布局
        self.base_layout = QVBoxLayout(self)
        self.base_layout.setContentsMargins(0, 0, 0, 0)
        self.base_layout.setSpacing(0)

        # 标题框架
        self.title_frame = QFrame()
        self.title_frame.setMaximumHeight(47)
        self.title_frame.setMinimumHeight(47)

        # 标题基础布局
        self.title_base_layout = QVBoxLayout(self.title_frame)
        self.title_base_layout.setContentsMargins(5, 3, 5, 3)

        # 标题背景框架
        self.title_bg_frame = QFrame()
        self.title_bg_frame.setObjectName("title_bg_frame")

        # 布局标题BG
        self.title_bg_layout = QHBoxLayout(self.title_bg_frame)
        self.title_bg_layout.setContentsMargins(5, 5, 5, 5)
        self.title_bg_layout.setSpacing(3)

        # 图标
        self.icon_frame = QFrame()
        self.icon_frame.setFixedSize(30, 30)
        self.icon_frame.setStyleSheet("background: none;")
        self.icon_layout = QVBoxLayout(self.icon_frame)
        self.icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_layout.setSpacing(5)

        self.icon = PyIcon(self._icon_path, ColorPalette.custom_icon_color)
        self.icon_layout.addWidget(self.icon, Qt.AlignCenter, Qt.AlignCenter)

        # 标签
        self.title_label = QLabel()
        self.title_label.setObjectName("title_label")

        # 按钮框架
        self.btn_frame = QFrame()
        self.btn_frame.setFixedSize(30, 30)
        self.btn_frame.setStyleSheet("background: none;")
        # 关闭按钮
        self.btn_close = PyLeftButton(
            # self._parent,
            self._app_parent,
            tooltip_text=Language.resolve_key("language.UI.ui_Close"),
            icon_path=self._icon_close_path,
            radius=6,
        )
        self.btn_close.setParent(self.btn_frame)
        self.btn_close.setObjectName("btn_close_left_column")

        # 添加图标、标题、按钮到标题背景布局
        self.title_bg_layout.addWidget(self.icon_frame)
        self.title_bg_layout.addWidget(self.title_label)
        self.title_bg_layout.addWidget(self.btn_frame)

        # 添加标题背景到基础布局
        self.title_base_layout.addWidget(self.title_bg_frame)

        # 文本框架
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("background: none")

        # 添加标题框架、内容框架到基础布局
        self.base_layout.addWidget(self.title_frame)
        self.base_layout.addWidget(self.content_frame)

        # 应用初始样式与标题
        self.set_title(self._title_key)
        self.update_style()
