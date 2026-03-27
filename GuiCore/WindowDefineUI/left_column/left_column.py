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
from GUI import Ui_LeftColumn
from AppCore import ColorPalette


class CLeftColumn(QWidget):
    """左侧信息栏容器组件。

    职责:
    - 构建左侧标题区与内容区。
    - 发出关闭按钮点击与释放信号。
    """

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
        """初始化左侧栏组件。

        参数:
        - app_parent: 应用父对象。
        - text_title: 标题文本。
        - text_title_size: 标题字号。
        - icon_path: 标题图标路径。
        - icon_close_path: 关闭按钮图标路径。
        - font_family: 字体名称。
        - radius: 圆角半径。

        返回:
        - None
        """

        super().__init__()

        # 参数
        # self._parent = parent
        self._app_parent = app_parent
        self.ColorPalette = ColorPalette
        self._text_title = text_title
        self._text_title_size = text_title_size
        self._text_title_color = ColorPalette.custom_text_foreground
        self._icon_path = icon_path
        self._dark_one = ColorPalette.custom_dark_one
        self._bg_color = ColorPalette.custom_bg_three
        self._btn_color = ColorPalette.custom_bg_three
        self._btn_color_hover = ColorPalette.custom_bg_two
        self._btn_color_pressed = ColorPalette.custom_bg_one
        self._icon_color = ColorPalette.custom_icon_color
        self._icon_color_hover = ColorPalette.custom_icon_hover
        self._icon_color_pressed = ColorPalette.custom_icon_pressed
        self._context_color = ColorPalette.custom_context_color
        self._icon_close_path = icon_close_path
        self._radius = radius
        self._family = font_family
        self.setup_ui()

        # 在BG框架中添加左列
        self.menus = Ui_LeftColumn()
        self.menus.setupUi(self.content_frame)

        # CONNECT SIGNALS
        self.btn_close.clicked.connect(self.btn_clicked)
        self.btn_close.released.connect(self.btn_released)

    # 标题左列发出信号
    def btn_clicked(self):
        """处理关闭按钮点击并发射信号。"""

        self.clicked.emit(self.btn_close)

    def btn_released(self):
        """处理关闭按钮释放并发射信号。"""

        self.released.emit(self.btn_close)

    def setup_ui(self):
        """构建左侧栏界面结构。

        返回:
        - None
        """

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
        self.title_bg_frame.setStyleSheet(f"""
        #title_bg_frame {{
            background-color: {self._bg_color};
            border-radius: {self._radius}px;
        }}
        """)

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

        self.icon = PyIcon(self._icon_path, self._icon_color)
        self.icon_layout.addWidget(self.icon, Qt.AlignCenter, Qt.AlignCenter)

        # 标签
        self.title_label = QLabel(self._text_title)
        self.title_label.setObjectName("title_label")
        self.title_label.setStyleSheet(f"""
        #title_label {{
            font-size: {self._text_title_size}pt;
            color: {self._text_title_color};
            padding-bottom: 2px;
            background: none;
            font: 700 9pt "{self._family}";
        }}
        """)

        # 按钮框架
        self.btn_frame = QFrame()
        self.btn_frame.setFixedSize(30, 30)
        self.btn_frame.setStyleSheet("background: none;")
        # 关闭按钮
        self.btn_close = PyLeftButton(
            # self._parent,
            self._app_parent,
            tooltip_text="关闭",
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
