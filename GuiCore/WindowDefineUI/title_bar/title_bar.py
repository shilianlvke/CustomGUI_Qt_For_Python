"""窗口标题栏组件模块。"""

from AppCore import AppSettings, ColorPalette, Language, PathFactory
from guicore.CustomUI.div import CVDiv
from qt_core import (
    QCursor,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSize,
    QSvgWidget,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from .title_button import CTitleButton

_is_maximized = False
_old_size = QSize()


class CTitleBar(QWidget):
    """窗口标题栏组件。

    职责:
    - 构建标题栏图标、标题与控制按钮。
    - 提供窗口拖拽、最大化/还原与菜单按钮事件分发。
    """

    # SIGNALS
    clicked = Signal(object)
    released = Signal(object)

    def __init__(self, parent: QWidget, app_parent: object) -> None:  # noqa: PLR0915
        """初始化标题栏。

        参数:
        - parent: 标题栏所属窗口。
        - app_parent: 应用父对象。

        返回:
        - None
        """
        super().__init__()
        self._parent = parent
        self._app_parent = app_parent
        self.settings = AppSettings

        # 参数
        self._logo_image = AppSettings.logo_title
        self._dark_one = ColorPalette.custom_dark_one
        self._bg_color = ColorPalette.custom_dark_three
        self._div_color = ColorPalette.custom_bg_three
        self._btn_bg_color = ColorPalette.custom_dark_three
        self._btn_bg_color_hover = ColorPalette.custom_bg_three
        self._btn_bg_color_pressed = ColorPalette.custom_bg_one
        self._context_color = ColorPalette.custom_context_color
        self._icon_color = ColorPalette.custom_icon_color
        self._icon_color_hover = ColorPalette.custom_icon_hover
        self._icon_color_pressed = ColorPalette.custom_icon_pressed
        self._icon_color_active = ColorPalette.custom_icon_active
        self._font_family = AppSettings.family
        self._title_size = AppSettings.title_size
        self._text_foreground = ColorPalette.custom_text_foreground
        self._is_custom_title_bar = AppSettings.custom_title_bar
        self.minimize_btn = Language.UI.ui_Minimize
        self.maximize_btn = Language.UI.ui_Maximize
        self.close_btn = Language.UI.ui_Close
        self.setup_ui()

        # 设置logo宽度
        self.top_logo.setMinimumWidth(AppSettings.icon_size)
        self.top_logo.setMaximumWidth(AppSettings.icon_size)

        # 移动窗口/最大化/恢复
        def move_window(event: object) -> None:
            # 如果最大化改变为正常
            if parent.isMaximized():
                self.maximize_restore()
                curso_x = parent.pos().x()
                curso_y = event.globalPos().y() - QCursor.pos().y()
                parent.move(curso_x, curso_y)
            # 移动窗口
            if event.buttons() == Qt.LeftButton:
                parent.move(parent.pos() + event.globalPos() - parent.dragPos)
                parent.dragPos = event.globalPos()
                event.accept()

        # 移动应用程序小部件
        if self._is_custom_title_bar:
            self.top_logo.mouseMoveEvent = move_window
            self.div_1.mouseMoveEvent = move_window
            self.title_label.mouseMoveEvent = move_window
            self.div_2.mouseMoveEvent = move_window
            self.div_3.mouseMoveEvent = move_window

        # 最大化/恢复
        if self._is_custom_title_bar:
            self.top_logo.mouseDoubleClickEvent = self.maximize_restore
            self.div_1.mouseDoubleClickEvent = self.maximize_restore
            self.title_label.mouseDoubleClickEvent = self.maximize_restore
            self.div_2.mouseDoubleClickEvent = self.maximize_restore

        # 将小部件添加到标题栏
        # ///////////////////////////////////////////////////////////////
        self.bg_layout.addWidget(self.top_logo)
        self.bg_layout.addWidget(self.div_1)
        self.bg_layout.addWidget(self.title_label)
        self.bg_layout.addWidget(self.div_2)

        # 添加按钮按钮
        # ///////////////////////////////////////////////////////////////
        # Functions
        self.minimize_button.released.connect(parent.showMinimized)
        self.maximize_restore_button.released.connect(self.maximize_restore)
        self.close_button.released.connect(parent.close)

        # 额外BTN布局
        self.bg_layout.addLayout(self.custom_buttons_layout)

        # 添加按钮
        if self._is_custom_title_bar:
            self.bg_layout.addWidget(self.minimize_button)
            self.bg_layout.addWidget(self.maximize_restore_button)
            self.bg_layout.addWidget(self.close_button)

    # 在标题栏中添加按钮
    # 添加btns并发出信号
    # ///////////////////////////////////////////////////////////////
    def add_menus(self, parameters: list[dict[str, object]] | None) -> None:
        """批量添加标题栏菜单按钮。

        参数:
        - parameters: 按钮配置列表。

        返回:
        - None
        """
        if parameters is not None and len(parameters) > 0:
            for parameter in parameters:
                _btn_icon = PathFactory.set_svg_icon(parameter["btn_icon"])
                _btn_id = parameter["btn_id"]
                _btn_tooltip = parameter["btn_tooltip"]
                _is_active = parameter["is_active"]

                self.menu = CTitleButton(
                    self._parent,
                    self._app_parent,
                    btn_id=_btn_id,
                    tooltip_text=_btn_tooltip,
                    bg_color=self._bg_color,
                    icon_color=self._icon_color,
                    icon_path=_btn_icon,
                    is_active=_is_active,
                )
                self.menu.clicked.connect(self.btn_clicked)
                self.menu.released.connect(self.btn_released)

                # ADD TO LAYOUT
                self.custom_buttons_layout.addWidget(self.menu)

            # ADD DIV
            if self._is_custom_title_bar:
                self.custom_buttons_layout.addWidget(self.div_3)

    # 标题栏菜单发出信号
    def btn_clicked(self) -> None:
        """处理标题栏按钮点击并发射信号。"""
        self.clicked.emit(self.menu)

    def btn_released(self) -> None:
        """处理标题栏按钮释放并发射信号。"""
        self.released.emit(self.menu)

    # 设置标题栏文本
    # ///////////////////////////////////////////////////////////////
    def set_title(self, title: str) -> None:
        """设置标题栏文本。

        参数:
        - title: 标题文本。

        返回:
        - None
        """
        self.title_label.setText(title)

    # 最大化/恢复
    # 最大化并恢复父窗口
    # ///////////////////////////////////////////////////////////////
    def maximize_restore(self, e: object | None = None) -> None:
        """切换窗口最大化与还原状态。

        参数:
        - e: 可选事件对象。

        返回:
        - None
        """
        _ = e
        state = globals()

        # 更改UI并调整夹点大小
        def change_ui() -> None:
            if hasattr(self._parent, "ui"):
                if state["_is_maximized"]:
                    self._parent.ui.central_widget_layout.setContentsMargins(0, 0, 0, 0)
                    self._parent.ui.window.set_stylesheet(border_radius=0, border_size=0)
                    self.maximize_restore_button.set_icon(PathFactory.set_svg_icon("icon_restore"))
                else:
                    self._parent.ui.central_widget_layout.setContentsMargins(10, 10, 10, 10)
                    self._parent.ui.window.set_stylesheet(border_radius=10, border_size=2)
                    self.maximize_restore_button.set_icon(PathFactory.set_svg_icon("icon_maximize"))

        # 检查事件
        if self._parent.isMaximized():
            state["_is_maximized"] = False
            self._parent.showNormal()
            change_ui()
        else:
            state["_is_maximized"] = True
            state["_old_size"] = QSize(self._parent.width(), self._parent.height())
            self._parent.showMaximized()
            change_ui()

    # SETUP APP
    # ///////////////////////////////////////////////////////////////
    def setup_ui(self) -> None:
        """构建标题栏界面结构。

        返回:
        - None
        """
        # ADD MENU LAYOUT
        self.title_bar_layout = QVBoxLayout(self)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)

        # ADD BG
        self.bg = QFrame()
        self.bg.setObjectName("CTitleBar_Bg_Frame")

        # ADD BG LAYOUT
        self.bg_layout = QHBoxLayout(self.bg)
        self.bg_layout.setContentsMargins(10, 0, 5, 0)
        self.bg_layout.setSpacing(0)

        # DIVS
        self.div_1 = CVDiv()
        self.div_2 = CVDiv()
        self.div_3 = CVDiv()

        # LEFT FRAME WITH MOVE APP
        self.top_logo = QLabel()
        self.top_logo_layout = QVBoxLayout(self.top_logo)
        self.top_logo_layout.setContentsMargins(0, 0, 0, 0)
        self.logo_svg = QSvgWidget()
        self.logo_svg.load(PathFactory.set_svg_image(self._logo_image))
        self.top_logo_layout.addWidget(self.logo_svg, Qt.AlignCenter, Qt.AlignCenter)

        # TITLE LABEL
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignVCenter)
        self.title_label.setStyleSheet(f'font: {self._title_size}pt "{self._font_family}"')

        # CUSTOM BUTTONS LAYOUT
        self.custom_buttons_layout = QHBoxLayout()
        self.custom_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_buttons_layout.setSpacing(0)

        # MINIMIZE BUTTON
        self.minimize_button = CTitleButton(
            self._parent,
            self._app_parent,
            tooltip_text=self.minimize_btn,
            bg_color=self._btn_bg_color,
            icon_color=self._icon_color,
            radius=6,
            icon_path=PathFactory.set_svg_icon("icon_minimize"),
        )

        # MAXIMIZE / RESTORE BUTTON
        self.maximize_restore_button = CTitleButton(
            self._parent,
            self._app_parent,
            tooltip_text=self.maximize_btn,
            bg_color=self._btn_bg_color,
            icon_color=self._icon_color,
            radius=6,
            icon_path=PathFactory.set_svg_icon("icon_maximize"),
        )

        # CLOSE BUTTON
        self.close_button = CTitleButton(
            self._parent,
            self._app_parent,
            tooltip_text=self.close_btn,
            bg_color=self._btn_bg_color,
            icon_color=self._icon_color,
            radius=6,
            icon_path=PathFactory.set_svg_icon("icon_close"),
        )

        # ADD TO LAYOUT
        self.title_bar_layout.addWidget(self.bg)
