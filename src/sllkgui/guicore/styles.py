# 这里决定整个window的总体样式
from PySide6.QtGui import QColor

from sllkgui.appcore import AppSettings, ColorPalette, Logger, PathFactory, get_design_tokens

from .acrylic import MIN_WINDOW_GLASS_ALPHA, acrylic_active, glass_alpha
from .background import background_image_active
from .styles_components import _ComponentStyles, _mix

# ----------------------------------------------------------------------
# 亚克力玻璃层的不透明度
# ----------------------------------------------------------------------
# 具体取值见 settings/window.yaml 的 ``glass`` 分组（0-1），
# 叠加顺序为：桌面 -> 亚克力色调（acrylic.opacity）-> 窗口 -> 侧栏/面板
# -> 区域卡片 -> 卡片。约束：太大看不到模糊，太小会牺牲文字可读性。
# 主界面（CWindow）本身就是背景层：由它铺这层玻璃，标题栏、侧栏、内容卡片
# 都是它的子控件，不再额外引入任何"背景窗口/背景控件"。这样标题栏的鼠标
# 命中区域、拖动与双击最大化等原生交互都留在原来的控件树上。


def _rgba(value: str, alpha: float) -> str:
    """把颜色转成带透明度的 ``rgba()`` 写法（Qt QSS 不支持 ``#RRGGBBAA``）。"""
    color = QColor(value)
    if not color.isValid():
        return value
    channel = max(0, min(255, round(color.alpha() * max(0.0, min(1.0, alpha)))))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {channel})"


def _composite(front: str, alpha: float, back: str) -> str:
    """把半透明前景压到不透明背景上，返回合成的实色（过场遮罩打底用）。"""
    top, bottom = QColor(front), QColor(back)
    alpha = max(0.0, min(1.0, alpha))
    return QColor(
        round(top.red() * alpha + bottom.red() * (1 - alpha)),
        round(top.green() * alpha + bottom.green() * (1 - alpha)),
        round(top.blue() * alpha + bottom.blue() * (1 - alpha)),
    ).name()


def region_card_tint() -> str:
    """区域背景卡片的玻璃色调（未叠加透明度）。"""
    colors = get_design_tokens().colors
    return _mix(colors.surface_app, colors.surface_panel, 0.5)


def region_card_background() -> str:
    """区域背景卡片的**等效不透明底色**（兼容入口）。

    主窗口的栏目过场已改为「透明擦除」：遮罩不铺底色，擦除后的空白直接露出
    卡片自身的玻璃层（见 ``CPageTransition``），因此不再需要这个实色近似。
    本函数保留给不传 ``stage`` 的独立堆叠控件、自定义动画与外部调用，结果
    仍随主题更新。
    """
    tint = region_card_tint()
    if not acrylic_active():
        return tint
    colors = get_design_tokens().colors
    glass_cfg = AppSettings.glass
    window = _composite(colors.surface_app, glass_alpha(glass_cfg.window, minimum=MIN_WINDOW_GLASS_ALPHA), colors.surface_app)
    return _composite(tint, glass_alpha(glass_cfg.region), window)


class Styles(_ComponentStyles):
    """全局样式表：所有组件的**颜色 / 状态 / 字体**都集中在这里。

    约定（与 ``CPushButton`` 一致）：

    1. 组件在 ``__init__`` 里只声明 ``setObjectName("<组件名>_<Qt类名>")``；
    2. 组件的全部颜色/状态/字体样式在本文件内按该 objectName 定义；
    3. 组件**不订阅主题**——主题切换时由 ``CWindow.apply_style()`` 整体重建
       本样式表并下发（窗口级 + 应用级），组件自动跟随；
    4. **几何量不进本文件**：圆角、边框宽度、内边距、固定宽高、偏移等与主题
       无关的尺寸，一律由组件本地用一条只含几何属性的 ``setStyleSheet`` 提供
       （见 ``CStatusButton._apply_geometry``）；这些尺寸的取值**全部来自设计
       令牌**（``sllkgui.appcore.sysx.modules.token_module``），组件暴露的几何参数默认取
       ``None`` 并回落到对应令牌，显式传参即可覆盖。

    亚克力材质：``acrylic_active()`` 为真时，各层底色改用半透明 ``rgba()``，
    透出系统级模糊背景；不可用时保持原有的不透明主题色，避免「半透明但
    没有模糊」的脏画面。悬浮/按下等状态色同样按透明度分档，保证玻璃上仍然
    有清晰的层次。

    外观由两部分拼成：**基础框架 QSS**（见 :meth:`_build_base_sheet`）与
    各组件族的片段（见 :mod:`sllkgui.guicore.styles_components`），后者按
    固定顺序追加，输出文本与拆分前逐字一致。
    """

    def __init__(self):
        self.tokens = get_design_tokens()
        Logger.debug(f"生成全局样式（设计令牌）: {self.tokens}")
        # 资源以绝对路径注入 QSS，避免相对路径依赖工作目录（跨平台路径统一为正斜杠）
        self._icon_arrow_right = PathFactory.set_svg_icon("icon_arrow_right").replace("\\", "/")
        self._icon_arrow_down = PathFactory.set_svg_icon("icon_arrow_down").replace("\\", "/")

        colors = self.tokens.colors
        # 背景图激活时即使没有系统亚克力，也要把各层表面转为半透明，
        # 否则侧栏/面板/卡片会整块盖住 CWindow 绘制的背景图。
        image_mode = background_image_active() and not acrylic_active()
        glass = acrylic_active() or background_image_active()
        # 背景图模式给表面一个可读性下限：既能看到图，又不至于文字发飘。
        min_surface = 0.58 if image_mode else 0.0
        min_sidebar = 0.50 if image_mode else 0.0
        self.glass = glass
        glass_cfg = AppSettings.glass

        # 各层表面：玻璃模式下使用半透明写法，否则保持不透明主题色。
        # 表面层按运行期「亚克力质感强度」降低不透明度，让系统模糊材质透出更多；
        # 浮层/工具提示保持原配置不缩放，避免菜单文字与页面互相穿透。
        # 主窗口底色保留最小 Alpha：分层窗口 Alpha=0 的像素会鼠标穿透。
        self._window_bg = (
            _rgba(colors.surface_app, glass_alpha(glass_cfg.window, minimum=MIN_WINDOW_GLASS_ALPHA))
            if glass
            else colors.surface_app
        )
        self._sidebar_bg = (
            _rgba(colors.surface_sidebar, glass_alpha(glass_cfg.sidebar, minimum=min_sidebar))
            if glass
            else colors.surface_sidebar
        )
        self._panel_bg = (
            _rgba(colors.surface_panel, glass_alpha(glass_cfg.panel, minimum=min_surface))
            if glass
            else colors.surface_panel
        )
        self._card_bg = (
            _rgba(colors.surface_card, glass_alpha(glass_cfg.card, minimum=min_surface))
            if glass
            else colors.surface_card
        )
        self._region_bg = (
            _rgba(region_card_tint(), glass_alpha(glass_cfg.region, minimum=min_surface))
            if glass
            else region_card_tint()
        )
        self._control_bg = (
            _rgba(colors.surface_sidebar, glass_alpha(glass_cfg.control, minimum=min_surface))
            if glass
            else colors.surface_sidebar
        )
        self._menu_bg = (
            _rgba(colors.surface_interactive, glass_alpha(glass_cfg.menu, minimum=0.85)) if glass else colors.surface_interactive
        )
        # Overlay 左菜单浮在内容之上，需要接近不透明的面板底色；沿用侧栏的
        # 0 透明度会让菜单和页面文字互相穿透。
        self._overlay_panel_bg = (
            _rgba(colors.surface_panel, glass_alpha(glass_cfg.overlay_panel, minimum=0.90))
            if glass
            else colors.surface_panel
        )
        self._overlay_panel_border = _rgba(colors.text_primary, 0.14) if glass else colors.surface_interactive_pressed
        self._tooltip_bg = (
            _rgba(colors.surface_sidebar, glass_alpha(glass_cfg.tooltip, minimum=0.85)) if glass else colors.surface_sidebar
        )

        # 描边与状态层：玻璃模式用正文色的低透明度，深浅主题都会得到
        # 「深色上是白色高光、浅色上是灰色阴影」的 Fluent 分层效果
        self._hairline = _rgba(colors.text_primary, 0.10) if glass else colors.surface_app
        self._stroke = _rgba(colors.text_primary, 0.14) if glass else colors.border_transparent
        self._stroke_strong = _rgba(colors.text_primary, 0.24) if glass else colors.surface_interactive_pressed
        self._fill_rest = _rgba(colors.text_primary, 0.045) if glass else colors.surface_interactive
        self._fill_hover = _rgba(colors.text_primary, 0.09) if glass else colors.surface_interactive_hover
        self._fill_pressed = _rgba(colors.text_primary, 0.14) if glass else colors.surface_interactive_pressed
        self._accent_soft = _rgba(colors.border_context, 0.18) if glass else colors.surface_interactive_hover
        self._accent_border = _rgba(colors.border_context, 0.70) if glass else colors.border_context
        self._gridline = _rgba(colors.text_primary, 0.07) if glass else colors.surface_interactive_pressed
        # 滚动条把手：玻璃模式与实色模式都用正文色 + 透明度，保证在卡片底色上
        # 始终可辨；之前实色模式取 surface_interactive_pressed，与卡片底色几乎同值。
        self._scroll_handle = _rgba(colors.text_primary, 0.42 if glass else 0.34)
        self._scroll_handle_hover = _rgba(colors.text_primary, 0.62 if glass else 0.52)
        self._scroll_handle_pressed = _rgba(colors.text_primary, 0.78 if glass else 0.66)

        # 每种模式下的具体描边
        self._window_border = self._stroke if glass else colors.surface_interactive_pressed
        self._card_border = self._stroke if glass else colors.border_transparent
        #: 语义色：Fluent 的 error / success 直接取主题语义色
        self._danger = QColor(ColorPalette.custom_red).name()
        self._success = QColor(ColorPalette.custom_green).name()
        #: Fluent 控件描边：输入框/按钮比卡片描边更深，保证浅色主题下可辨认
        self._control_stroke = (
            _rgba(colors.text_primary, 0.42) if glass else _mix(colors.surface_app, colors.text_primary, 0.42)
        )
        self._control_stroke_secondary = (
            _rgba(colors.text_primary, 0.26) if glass else _mix(colors.surface_app, colors.text_primary, 0.26)
        )

        self.style = self._build_base_sheet()
        self.update_btn_style()
        self.update_status_button_style()
        self.update_lineedit_style()
        self.update_combobox_style()
        self.update_menu_style()
        self.update_show_card_style()
        self.update_tooltip_style()
        self.update_title_bar_style()
        self.update_columns_style()
        self.update_region_card_style()
        self.update_grips_style()
        self.update_table_style()
        self.update_scrollbar_style()

    def _build_base_sheet(self) -> str:
        """窗口框架、侧栏/面板/卡片等基础容器与 ``QFrame`` 兜底的 QSS。"""
        return f"""
            #CWindow_Frame {{
                background-color: {self._window_bg};
                border-radius: {self.tokens.radius.window}px;
                border: {self.tokens.border.width}px solid {self._window_border};
            }}
            /* 设置背景图后由 CWindow.paintEvent 负责绘制，样式表底色必须透明 */
            #CWindow_Frame[hasBackgroundImage="true"] {{
                background-color: transparent;
            }}
            /* 最大化/贴边：由 CWindow 改这条动态属性即可，无需重建整张样式表 */
            #CWindow_Frame[frameStyle="flat"] {{
                border-radius: 0px;
                border: 0px solid transparent;
            }}
            #CLeftMenu_Bg_Frame {{
                background-color: {self._sidebar_bg};
            }}
            /* Overlay 模式：左菜单浮在内容区上，改用接近不透明的面板底色 */
            #CLeftMenu_Bg_Frame[overlay="true"] {{
                background-color: {self._overlay_panel_bg};
                border: 1px solid {self._overlay_panel_border};
            }}
            #CTitleBar_Bg_Frame {{
                background-color: {self._panel_bg};
                border-radius: {self.tokens.radius.window}px;
            }}
            #CCredits_Bg_Frame {{
                background-color: {self._panel_bg};
                border-radius: {self.tokens.radius.window}px;
            }}
            #CCredits_Bg_Frame QLabel {{
                font: {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
                color: {self.tokens.colors.text_primary};
                padding-left: {self.tokens.spacing.padding_md}px;
                padding-right: {self.tokens.spacing.padding_md}px;
            }}
            #CCard_Frame {{
                border: {self.tokens.border.width}px solid {self._card_border};
                border-radius: {self.tokens.radius.window}px;
                background-color: {self._card_bg};
            }}
            #CHDiv_Frame {{
                background-color: {self._hairline};
            }}
            #CVDiv_Frame {{
                background-color: {self._hairline};
            }}
            QFrame {{
                color: {self.tokens.colors.text_primary};
                font: {self.tokens.typography.family};
            }}
        """
