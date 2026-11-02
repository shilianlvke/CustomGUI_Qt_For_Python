from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout

from customgui.appcore import AppSettings, get_design_tokens

from ...styles import Styles

#: 无圆角、无边框的框架状态（最大化 / 贴边时使用），对应样式表里的属性选择器
_FLAT_FRAME = (0, 0)


class CWindow(QFrame):
    """应用主窗口框架。

    - 样式来自全局 Styles（主题切换时经 ``apply_style`` 整体重建）；
    - ``set_stylesheet(border_radius, border_size)`` 提供框架圆角/边框
      覆盖（如最大化时去掉圆角），覆盖状态在主题切换后保持不变。

    覆盖走 ``frameStyle="flat"`` **动态属性**而不是重建样式表：最大化/还原
    每次都会切换覆盖，重建样式表会让整棵控件树重新 polish（实测单次 400+
    次 StyleChange、同步阻塞 40~500ms），表现为点一下卡一下。
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

        # 框架样式覆盖状态：(border_radius, border_size)，None 表示无覆盖
        self._frame_override = None
        #: 当前样式表里是否写进了覆盖规则（非 flat 的自定义圆角才写入）
        self._style_has_override = False
        #: 阴影效果对象（关闭时置 None，Qt 会随 ``setGraphicsEffect(None)`` 销毁它）
        self.shadow: QGraphicsDropShadowEffect | None = None
        self.apply_style()
        self.set_shadow_enabled(AppSettings.custom_title_bar and AppSettings.window_shadow)

    # ------------------------------------------------------------------
    # 样式
    # ------------------------------------------------------------------
    def apply_style(self):
        """重建全局样式并应用（主题切换时调用；不含最大化这类临时覆盖）。"""
        style = Styles().style
        override = self._frame_override
        self._style_has_override = override is not None and override != _FLAT_FRAME
        if self._style_has_override:
            radius, size = override
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
        # 而 apply_style 在主题切换等场景会被调用。
        app = QApplication.instance()
        if app is not None and app.styleSheet() != style:
            app.setStyleSheet(style)

    def set_stylesheet(self, border_radius=None, border_size=None):
        """覆盖框架圆角/边框；两个参数均为 None 时清除覆盖（恢复主题默认）。

        ``(0, 0)`` 是最大化/贴边用的高频路径，只改动态属性并重绘框架本身；
        其它自定义尺寸（少见）才退回重建样式表。
        """
        if border_radius is None and border_size is None:
            self._frame_override = None
            self._apply_frame_style("default")
            if self._style_has_override:  # 之前写过自定义圆角，需要把那条规则抹掉
                self.apply_style()
            return

        radius = border_radius if border_radius is not None else AppSettings.window_border_radius
        size = border_size if border_size is not None else AppSettings.window_border_size
        self._frame_override = (radius, size)
        if (radius, size) == _FLAT_FRAME:
            self._apply_frame_style("flat")
            if self._style_has_override:  # 同上：自定义圆角规则要清掉
                self.apply_style()
            return
        self._apply_frame_style("default")
        self.apply_style()

    def _apply_frame_style(self, value: str) -> None:
        """切换 ``frameStyle`` 动态属性并只重刷本控件（不波及子树）。"""
        if self.property("frameStyle") == value:
            return
        self.setProperty("frameStyle", value)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    # ------------------------------------------------------------------
    # 阴影
    # ------------------------------------------------------------------
    def set_shadow_enabled(self, enabled: bool) -> None:
        """开关窗口外阴影。

        最大化时关掉：窗口铺满屏幕后阴影本来就看不见，而
        ``QGraphicsDropShadowEffect`` 会让整窗改走离屏合成，拖慢还原后的首帧。
        """
        enabled = bool(enabled) and bool(AppSettings.window_shadow)
        if enabled:
            if self.graphicsEffect() is not None:
                return
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(20)
            effect.setXOffset(0)
            effect.setYOffset(0)
            effect.setColor(QColor(0, 0, 0, 160))
            self.setGraphicsEffect(effect)
            self.shadow = effect
            return
        if self.graphicsEffect() is None:
            return
        self.setGraphicsEffect(None)  # Qt 接管所有权并销毁旧效果
        self.shadow = None
