from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout

from customgui.appcore import AppSettings, get_design_tokens

from ...acrylic import acrylic_active, apply_acrylic, remove_acrylic
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
        #: 当前顶层窗口是否已挂上亚克力材质
        self._acrylic_applied = False
        #: 首次显示淡入只播放一次（最大化/还原不重复）
        self._fade_played = False
        self._fade_animation: QPropertyAnimation | None = None
        self.apply_style()
        self.set_shadow_enabled(AppSettings.custom_title_bar and AppSettings.window_shadow)

    # ------------------------------------------------------------------
    # 样式
    # ------------------------------------------------------------------
    def apply_style(self):
        """重建全局样式并应用（主题切换时调用；不含最大化这类临时覆盖）。

        整张样式表统一下发到**应用级**：窗口本身、嵌入控件与无父弹层
        （QMenu / QToolTip / Qt.Popup）共用同一份，切主题时整棵控件树只
        polish 一次。窗口级只保留最大化/自定义圆角这一小块覆盖规则；旧实现
        在窗口级与应用级各设一遍整表，同一棵树被反复 polish，主题切换明显卡顿。
        """
        base = Styles().style
        override = self._frame_override
        self._style_has_override = override is not None and override != _FLAT_FRAME
        override_sheet = ""
        if self._style_has_override:
            radius, size = override
            border_color = get_design_tokens().colors.surface_interactive_pressed
            override_sheet = f"""#CWindow_Frame {{
                border-radius: {radius}px;
                border: {size}px solid {border_color};
            }}"""

        app = QApplication.instance()
        if app is not None:
            if app.styleSheet() != base:
                app.setStyleSheet(base)
            if override_sheet:
                self.setStyleSheet(override_sheet)
            elif self.styleSheet():
                # 清掉旧版本留下的窗口级整表副本，避免它盖住新主题
                self.setStyleSheet("")
        elif override_sheet:
            self.setStyleSheet(base + override_sheet)
        else:
            self.setStyleSheet(base)
        # 主题切换后亚克力色调要跟着重算（该调用约 0.15ms 且幂等）
        self._sync_acrylic()

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
    # 亚克力材质与入场动效
    # ------------------------------------------------------------------
    def showEvent(self, event):
        """窗口首次显示：挂上系统级亚克力材质并播放淡入。"""
        super().showEvent(event)
        # 顶层 HWND 在 show 之后才稳定，延后一轮事件循环再挂材质
        # 带 context 的重载：控件先一步销毁时回调不会打到已删除的 C++ 对象
        QTimer.singleShot(0, self, self._sync_acrylic)
        self._play_fade_in()

    def _sync_acrylic(self) -> None:
        """按当前主题与配置同步顶层窗口的亚克力材质。

        只在「顶层窗口已显示 + 启用了无边框半透明窗口」时执行；组件嵌入普通
        QWidget（示例、测试）时静默跳过，不影响既有用法。
        """
        target = self.window()
        if target is None or target is self:
            return
        if not acrylic_active():
            if self._acrylic_applied:
                remove_acrylic(target)
                self._acrylic_applied = False
            return
        if not target.isVisible() or not target.testAttribute(Qt.WA_TranslucentBackground):
            return
        self._acrylic_applied = apply_acrylic(target)

    def _play_fade_in(self) -> None:
        """首次显示时对顶层窗口做一次短淡入（亚克力灯光晕的"凝聚"感）。

        只在原生亚克力可用时播放；``acrylic.fade_in`` 为 0 或非 Windows
        环境直接跳过，保证离屏测试与截图拿到的是不透明终态。
        """
        if self._fade_played or not acrylic_active():
            return
        self._fade_played = True
        duration = int(AppSettings.acrylic.fade_in)
        target = self.window()
        if duration <= 0 or target is None or target is self:
            return
        animation = QPropertyAnimation(target, b"windowOpacity", self)
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._fade_animation = animation

    # ------------------------------------------------------------------
    # 阴影
    # ------------------------------------------------------------------
    def set_shadow_enabled(self, enabled: bool) -> None:
        """开关窗口外阴影。

        最大化时关掉：窗口铺满屏幕后阴影本来就看不见，而
        ``QGraphicsDropShadowEffect`` 会让整窗改走离屏合成，拖慢还原后的首帧。

        亚克力模式同样必须关闭：效果会把整棵内容树（图标、文字、卡片）先渲染
        到离屏位图再画它们的投影，而玻璃窗口本身是半透明的，这层"内容阴影"
        会从窗口内部透出来，表现为图标/文字周围一圈灰绿色残影。窗口外轮廓
        交给系统材质与 2px 边框表达。
        """
        enabled = bool(enabled) and bool(AppSettings.window_shadow) and not acrylic_active()
        if enabled:
            if self.graphicsEffect() is not None:
                return
            effect = QGraphicsDropShadowEffect(self)
            shadow = AppSettings.shadow
            effect.setBlurRadius(int(shadow.blur_radius))
            effect.setXOffset(int(shadow.offset_x))
            effect.setYOffset(int(shadow.offset_y))
            effect.setColor(QColor(0, 0, 0, int(shadow.alpha)))
            self.setGraphicsEffect(effect)
            self.shadow = effect
            return
        if self.graphicsEffect() is None:
            return
        self.setGraphicsEffect(None)  # Qt 接管所有权并销毁旧效果
        self.shadow = None
