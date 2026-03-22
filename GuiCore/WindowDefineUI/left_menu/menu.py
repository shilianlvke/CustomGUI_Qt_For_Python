from qt_core import (
    QEasingCurve,
    QFrame,
    QPropertyAnimation,
    QPushButton,
    QVBoxLayout,
    Qt,
    Signal,
    QWidget,
)
from .menu_button import CLeftMenuButton
from GuiCore.CustomUI.div import CHDiv

from AppCore import PathFactory, ColorPalette, AppSettings, Language


class CLeftMenu(QWidget):
    # 信号
    clicked = Signal(object)
    released = Signal(object)

    def __init__(
            self,
            parent=None,
            app_parent=None,
            radius=8,
            icon_path="icon_menu",
            icon_path_close="icon_menu_close"
    ):
        super().__init__()
        self.setObjectName("CLeftMenu_QWidget")
        self.parent = parent
        self.app_parent = app_parent
        self._dark_one = ColorPalette.custom_dark_one
        self._dark_three = ColorPalette.custom_dark_three
        self._dark_four = ColorPalette.custom_dark_four
        self._bg_one = ColorPalette.custom_bg_one
        self._icon_color = ColorPalette.custom_icon_color
        self._icon_color_hover = ColorPalette.custom_icon_hover
        self._icon_color_pressed = ColorPalette.custom_icon_pressed
        self._icon_color_active = ColorPalette.custom_icon_active
        self._context_color = ColorPalette.custom_context_color
        self._text_foreground = ColorPalette.custom_text_foreground
        self._text_active = ColorPalette.custom_text_active
        self._duration_time = AppSettings.time_animation
        self._radius = radius
        self._minimum_width = AppSettings.lef_menu_size.minimum
        self._maximum_width = AppSettings.lef_menu_size.maximum
        self._icon_path = PathFactory.set_svg_icon(icon_path)
        self._icon_path_close = PathFactory.set_svg_icon(icon_path_close)
        self._font_family = AppSettings.family
        # 获取父类
        self._parent = parent
        self._app_parent = app_parent

        # 绘制UI
        self.setup_ui()

        # 设置背景颜色
        # self.bg.setStyleSheet(f"background: {self._dark_one}; border-radius: {radius};")

        # 切换按钮和DIV菜单
        self.toggle_button = CLeftMenuButton(
            app_parent,
            text=Language.UI.ui_Hide,
            tooltip_text=Language.UI.ui_Show,
            icon_path=icon_path,
            minimum_width=self._minimum_width,
            maximum_width=self._maximum_width,
            font_family=self._font_family,
        )
        self.toggle_button.clicked.connect(self.toggle_animation)
        self.div_top = CHDiv()

        # 将展开按钮和分割线添加到顶部布局
        self.top_layout.addWidget(self.toggle_button)
        self.top_layout.addWidget(self.div_top)  # 分割线

        # 将分割线添加到底部布局
        self.div_bottom = CHDiv()
        self.div_bottom.hide()
        self.bottom_layout.addWidget(self.div_bottom)

    # 为左侧菜单添加按钮
    # 添加按钮并设置信号
    def add_menus(self, parameters):
        if parameters is not None:
            for parameter in parameters:
                _btn_icon = parameter["btn_icon"]
                _btn_id = parameter["btn_id"]
                _btn_text = parameter["btn_text"]
                _btn_tooltip = parameter["btn_tooltip"]
                _show_top = parameter["show_top"]
                _is_active = parameter["is_active"]

                self.menu = CLeftMenuButton(
                    self._app_parent,
                    text=_btn_text,
                    btn_id=_btn_id,
                    tooltip_text=_btn_tooltip,
                    icon_path=_btn_icon,
                    is_active=_is_active,
                    font_family=self._font_family,
                )
                self.menu.clicked.connect(self.btn_clicked)
                self.menu.released.connect(self.btn_released)

                # 添加到布局
                if _show_top:
                    self.top_layout.addWidget(self.menu)
                else:
                    self.div_bottom.show()
                    self.bottom_layout.addWidget(self.menu)

    # 左侧菜单发射信号
    def btn_clicked(self):
        self.clicked.emit(self.menu)

    def btn_released(self):
        self.released.emit(self.menu)

    # 展开/缩回左菜单
    def toggle_animation(self):
        # CREATE ANIMATION
        self.animation = QPropertyAnimation(self._parent, b"minimumWidth")
        self.animation.stop()
        if self.width() <= self._minimum_width:  # 50
            self.animation.setStartValue(self.width())
            self.animation.setEndValue(self._maximum_width)  # 240
            self.toggle_button.set_active_toggle(True)
            self.toggle_button.set_icon(self._icon_path_close)
        else:
            self.animation.setStartValue(self.width())
            self.animation.setEndValue(self._minimum_width)
            self.toggle_button.set_active_toggle(False)
            self.toggle_button.set_icon(self._icon_path)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(self._duration_time)
        self.animation.start()

    # 仅选择一个BTN
    def select_only_one(self, widget: str):
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == widget:
                btn.set_active(True)
            else:
                btn.set_active(False)

    # 仅选择一个选项卡BTN
    def select_only_one_tab(self, widget: str):
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == widget:
                btn.set_active_tab(True)
            else:
                btn.set_active_tab(False)

    # 取消选择所有BTN
    def deselect_all(self):
        for btn in self.findChildren(QPushButton):
            btn.set_active(False)

    # 取消选择所有标签
    def deselect_all_tab(self):
        for btn in self.findChildren(QPushButton):
            btn.set_active_tab(False)

    # SETUP APP
    # ///////////////////////////////////////////////////////////////
    def setup_ui(self):
        # 添加菜单布局
        self.left_menu_layout = QVBoxLayout(self)
        self.left_menu_layout.setContentsMargins(0, 0, 0, 0)

        # 添加背景框架
        self.bg = QFrame()
        self.bg.setObjectName("CLeftMenu_Bg_Frame")

        # 添加顶部框架
        self.top_frame = QFrame()
        self.top_frame.setObjectName("CLeftMenu_top_Frame")

        # 添加底部框架
        self.bottom_frame = QFrame()
        self.bottom_frame.setObjectName("CLeftMenu_bottom_Frame")

        # 添加背景布局
        self._layout = QVBoxLayout(self.bg)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # 添加顶部布局
        self.top_layout = QVBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(1)

        # 添加底部布局
        self.bottom_layout = QVBoxLayout(self.bottom_frame)
        self.bottom_layout.setContentsMargins(0, 0, 0, 8)
        self.bottom_layout.setSpacing(1)

        # 将顶部框架、底部框架添加到背景布局
        self._layout.addWidget(self.top_frame, 0, Qt.AlignTop)
        self._layout.addWidget(self.bottom_frame, 0, Qt.AlignBottom)

        # 添加背景到菜单布局
        self.left_menu_layout.addWidget(self.bg)
