from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sllkgui.appcore import ColorPalette, Language, get_design_tokens, get_theme_manager

from ..column_geometry import title_strip_style
from ..left_column.icon import PyIcon
from ..left_column.left_button import PyLeftButton
from .ui import Ui_BottomColumn


class CBottomColumn(QWidget):
    """底部抽屉：结构与 ``CLeftColumn`` 同构（47px 标题条 + 内容框架）。

    与左列的差别只有停靠方向：主窗口把它放在内容区下方、版权栏上方，
    开合由 ``MainFunctions.toggle_bottom_column`` 动画 ``minimumHeight`` 完成。
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
        radius=None,
    ):
        super().__init__()

        # 参数（颜色实时读取 ColorPalette，主题切换自动生效）
        self._app_parent = app_parent
        self._title_key = text_title
        self._text_title_size = text_title_size
        self._icon_path = icon_path
        self._icon_close_path = icon_close_path
        self._radius = get_design_tokens().radius.window if radius is None else radius
        self._family = font_family
        self.setup_ui()

        # 在 BG 框架中添加底列布局（同包 ui.py，由 bottom_column.ui 生成）
        self.menus = Ui_BottomColumn()
        self.menus.setupUi(self.content_frame)

        # CONNECT SIGNALS
        self.btn_close.clicked.connect(self.btn_clicked)
        self.btn_close.released.connect(self.btn_released)

        # 订阅主题/语言变更（弱引用，随组件生命周期）
        get_theme_manager().subscribe(self.update_style)
        Language.subscribe(self.apply_language)

    # 标题底列发出信号
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
        """主题切换回调：重新着色图标（颜色样式由全局样式表统一提供）。"""
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

        # 标题基础布局：贴死卡片边缘（留边距会在卡片与标题条之间露出一圈底色窄环）
        self.title_base_layout = QVBoxLayout(self.title_frame)
        self.title_base_layout.setContentsMargins(0, 0, 0, 0)

        # 标题背景框架（配色见 sllkgui.guicore/styles.py；圆角是实例参数，本地覆盖）
        # 标题条与卡片同宽同顶，只有上圆角需要与卡片圆角对齐，下沿是内部接缝必须为直角
        self.title_bg_frame = QFrame()
        self.title_bg_frame.setObjectName("CBottomColumnTitle_Frame")
        self.title_bg_frame.setStyleSheet(title_strip_style("CBottomColumnTitle_Frame", self._radius))

        # 布局标题BG
        self.title_bg_layout = QHBoxLayout(self.title_bg_frame)
        self.title_bg_layout.setContentsMargins(5, 5, 5, 5)
        self.title_bg_layout.setSpacing(3)

        # 图标
        self.icon_frame = QFrame()
        self.icon_frame.setObjectName("CBottomColumnIcon_Frame")
        self.icon_frame.setFixedSize(30, 30)
        self.icon_layout = QVBoxLayout(self.icon_frame)
        self.icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_layout.setSpacing(5)

        self.icon = PyIcon(self._icon_path, ColorPalette.custom_icon_color)
        self.icon_layout.addWidget(self.icon, Qt.AlignCenter, Qt.AlignCenter)

        # 标签（配色见 sllkgui.guicore/styles.py；内边距与字体是组件本地几何，此处覆盖）
        tokens = get_design_tokens()
        self.title_label = QLabel()
        self.title_label.setObjectName("CBottomColumnTitle_Label")
        self.title_label.setStyleSheet(
            f"#CBottomColumnTitle_Label {{"
            f" padding-bottom: {tokens.spacing.label_padding_bottom}px;"
            f' font: {tokens.typography.weight_label} {tokens.typography.size_label}pt "{self._family}"; }}'
        )

        # 按钮框架
        self.btn_frame = QFrame()
        self.btn_frame.setObjectName("CBottomColumnBtn_Frame")
        self.btn_frame.setFixedSize(30, 30)
        # 关闭按钮
        self.btn_close = PyLeftButton(
            # self._parent,
            self._app_parent,
            tooltip_text=Language.resolve_key("language.UI.ui_Close"),
            icon_path=self._icon_close_path,
            radius=6,
        )
        self.btn_close.setParent(self.btn_frame)
        self.btn_close.setObjectName("btn_close_bottom_column")

        # 添加图标、标题、按钮到标题背景布局
        self.title_bg_layout.addWidget(self.icon_frame)
        self.title_bg_layout.addWidget(self.title_label)
        self.title_bg_layout.addWidget(self.btn_frame)

        # 添加标题背景到基础布局
        self.title_base_layout.addWidget(self.title_bg_frame)

        # 文本框架
        self.content_frame = QFrame()
        self.content_frame.setObjectName("CBottomColumnContent_Frame")

        # 添加标题框架、内容框架到基础布局
        self.base_layout.addWidget(self.title_frame)
        self.base_layout.addWidget(self.content_frame)

        # 应用初始样式与标题
        self.set_title(self._title_key)
        self.update_style()
