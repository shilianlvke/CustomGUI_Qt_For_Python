from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QFrame, QGraphicsDropShadowEffect

from AppCore import AppSettings, get_design_tokens

from ...styles import Styles


class CWindow(QFrame):
    """应用主窗口框架。

    - 样式来自全局 Styles（主题切换时经 ``apply_style`` 整体重建）；
    - ``set_stylesheet(border_radius, border_size)`` 提供框架圆角/边框
      覆盖（如最大化时去掉圆角），覆盖状态在主题切换后保持不变。
    """

    def __init__(self, horizontal: bool = True):
        super().__init__()
        self.setObjectName("CWindow_Frame")
        if horizontal:
            self.layout = QHBoxLayout(self)
        else:
            self.layout = QVBoxLayout(self)
        margin = AppSettings.window_margin
        self.layout.setContentsMargins(margin, margin, margin, margin)
        self.layout.setSpacing(AppSettings.window_space)
        if AppSettings.custom_title_bar:
            if AppSettings.window_shadow:
                self.shadow = QGraphicsDropShadowEffect()
                self.shadow.setBlurRadius(20)
                self.shadow.setXOffset(0)
                self.shadow.setYOffset(0)
                self.shadow.setColor(QColor(0, 0, 0, 160))
                self.setGraphicsEffect(self.shadow)

        # 框架样式覆盖状态：(border_radius, border_size)，None 表示无覆盖
        self._frame_override = None
        self.apply_style()

    def apply_style(self):
        """重建全局样式并应用（叠加框架覆盖，若有）。"""
        style = Styles().style
        if self._frame_override is not None:
            radius, size = self._frame_override
            border_color = get_design_tokens().colors.surface_interactive_pressed
            style += f"""
            #CWindow_Frame {{
                border-radius: {radius}px;
                border: {size}px solid {border_color};
            }}
            """
        self.setStyleSheet(style)
        # 同步下发到应用级：弹出类组件（QMenu、提示气泡）是独立顶层窗口，
        # 不经过本控件，只能通过应用级样式表着色。
        # 内容不变时跳过：setStyleSheet 会触发整棵控件树重新 polish，
        # 而 apply_style 在最大化/还原等场景会被反复调用。
        app = QApplication.instance()
        if app is not None and app.styleSheet() != style:
            app.setStyleSheet(style)

    def set_stylesheet(self, border_radius=None, border_size=None):
        """覆盖框架圆角/边框；两个参数均为 None 时清除覆盖（恢复主题默认）。"""
        if border_radius is None and border_size is None:
            self._frame_override = None
        else:
            radius = border_radius if border_radius is not None else AppSettings.window_border_radius
            size = border_size if border_size is not None else AppSettings.window_border_size
            self._frame_override = (radius, size)
        self.apply_style()
