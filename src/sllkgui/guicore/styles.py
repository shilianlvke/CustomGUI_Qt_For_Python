# 这里决定整个window的总体样式
from PySide6.QtGui import QColor

from sllkgui.appcore import AppSettings, Logger, PathFactory, get_design_tokens

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


def _gradient(top: str, bottom: str) -> str:
    """纵向渐变写法；两层色差很小，只用来给大面积色块一点空气感。"""
    return (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
        f" stop:0 {top}, stop:1 {bottom})"
    )


def _glass_gradient(top: str, bottom: str, alpha: float, minimum: float = 0.0) -> str:
    """亚克力模式下的纵向渐变：两端共用同一不透明度，只有色相渐变。"""
    scaled = glass_alpha(alpha, minimum=minimum)
    return _gradient(_rgba(top, scaled), _rgba(bottom, scaled))


def region_card_tint() -> str:
    """区域背景卡片的玻璃色调（未叠加透明度）。

    区域卡片是内容区与四向抽屉共用的"板面"，只比画布高半档：再亮就会和
    内部卡片抢层次，再暗就退化成画布本身。
    """
    colors = get_design_tokens().colors
    return _mix(colors.surface_canvas, colors.surface_card, 0.62)


def region_card_top() -> str:
    """区域背景卡片渐变的顶部（略亮，制造自上而下的光感）。"""
    colors = get_design_tokens().colors
    return _mix(region_card_tint(), colors.text_primary, 0.03)


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
    window = _composite(
        colors.surface_app,
        glass_alpha(glass_cfg.window, minimum=MIN_WINDOW_GLASS_ALPHA),
        colors.surface_app,
    )
    return _composite(tint, glass_alpha(glass_cfg.region), window)


def qss_color(color: QColor) -> str:
    """QColor → QSS 颜色：不透明输出 ``#RRGGBB``，半透明输出 ``rgba(...)``。"""
    if color.alpha() >= 255:
        return color.name()
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def _glass_color(value: str, alpha: float, minimum: float = 0.0) -> QColor:
    """按「亚克力质感强度」缩放不透明度的玻璃色（自绘组件与样式表共用）。"""
    color = QColor(value)
    color.setAlpha(max(0, min(255, round(255 * glass_alpha(alpha, minimum=minimum)))))
    return color


def glass_surfaces() -> bool:
    """各层表面是否需要半透明：亚克力材质或窗口背景图任一启用。"""
    return acrylic_active() or background_image_active()


def card_surface_color() -> QColor:
    """卡片层（设置卡片、分组卡）的玻璃色，与全局 ``#CCard_Frame`` 同值。"""
    colors = get_design_tokens().colors
    if not glass_surfaces():
        return QColor(colors.surface_card)
    # 背景图模式给一个可读性下限，避免正文压在复杂图案上发飘
    minimum = 0.0 if acrylic_active() else 0.58
    return _glass_color(colors.surface_card, AppSettings.glass.card, minimum)


def overlay_surface_color() -> QColor:
    """浮层表面（浮层菜单、浮层抽屉）的玻璃色。

    浮层取当前主题最亮的那档表面：深色主题用抬升层，浅色主题用卡片白。
    透明度保留 0.90 的下限，防止页面文字透上来干扰阅读。
    """
    colors = get_design_tokens().colors
    if not glass_surfaces():
        return QColor(colors.surface_overlay)
    return _glass_color(colors.surface_overlay, AppSettings.glass.overlay_panel, 0.90)


def overlay_border_color() -> QColor:
    """浮层表面的描边色：玻璃模式取正文色 20%，实色模式取发丝线。"""
    colors = get_design_tokens().colors
    if not glass_surfaces():
        return QColor(colors.border_soft)
    color = QColor(colors.text_primary)
    color.setAlpha(round(255 * 0.20))
    return color


def card_stroke_color() -> QColor:
    """卡片描边：玻璃模式取正文色 14%，实色模式取一档更明显的发丝线。

    实色模式必须给卡片描边：深浅主题里卡片底与画布只差半档，没有描边
    卡片就等于不可见；而描边过重会把卡片切成"九宫格"，因此只取 16%。
    """
    colors = get_design_tokens().colors
    if not glass_surfaces():
        return QColor(colors.border_soft)
    color = QColor(colors.text_primary)
    color.setAlpha(round(255 * 0.14))
    return color


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

    分层规则（本次重构的核心）：

    - 七档中性色按「画布 → 侧栏 → 面板 → 卡片 → 抬升层」排布，**面板与卡片
      不再同色**，标题栏、抽屉、内容卡片各自有独立的一档；
    - 大面积色块（窗口、区域卡片）用极轻的纵向渐变，避免整屏纯色显得扁平；
    - 描边统一走发丝线：深浅主题都用「画布 + 正文色 10~16%」的混合色，
      既不抢内容，也不会在浅色主题里彻底消失；
    - 强调色只出现在「状态」上（选中指示条、选中底、焦点环、主色文字），
      不再大面积铺开。

    亚克力材质：``acrylic_active()`` 为真时，各层底色改用半透明 ``rgba()``，
    透出系统级模糊背景；不可用时保持原有的不透明主题色，避免「半透明但
    没有模糊」的脏画面。悬浮/按下等状态色同样按透明度分档，保证玻璃上仍然
    有清晰的层次。

    外观由两部分拼成：**基础框架 QSS**（见 :meth:`_build_base_sheet`）与
    各组件族的片段（见 :mod:`sllkgui.guicore.styles_components`），后者按
    固定顺序追加。
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
        window_top = _mix(colors.surface_canvas, colors.text_primary, 0.025)
        window_bottom = _mix(colors.surface_canvas, colors.surface_sunken, 0.55)
        self._window_bg = (
            _glass_gradient(window_top, window_bottom, glass_cfg.window, minimum=MIN_WINDOW_GLASS_ALPHA)
            if glass
            else _gradient(window_top, window_bottom)
        )
        sidebar_top = _mix(colors.surface_sidebar, colors.text_primary, 0.02)
        self._sidebar_bg = (
            _glass_gradient(sidebar_top, colors.surface_sidebar, glass_cfg.sidebar, minimum=min_sidebar)
            if glass
            else _gradient(sidebar_top, colors.surface_sidebar)
        )
        self._panel_bg = (
            _rgba(colors.surface_panel, glass_alpha(glass_cfg.panel, minimum=min_surface))
            if glass
            else colors.surface_panel
        )
        self._card_bg = qss_color(card_surface_color())
        self._region_tint = region_card_tint()
        self._region_bg = (
            _glass_gradient(
                region_card_top(),
                self._region_tint,
                glass_cfg.region,
                minimum=min_surface,
            )
            if glass
            else _gradient(region_card_top(), self._region_tint)
        )
        # 控件底色比卡片高一档：输入框、中性按钮在深浅主题里都能"浮"在卡片上
        self._control_bg = (
            _rgba(colors.surface_raised, glass_alpha(glass_cfg.control, minimum=min_surface))
            if glass
            else colors.surface_raised
        )
        self._menu_bg = (
            _rgba(colors.surface_overlay, glass_alpha(glass_cfg.menu, minimum=0.85))
            if glass
            else colors.surface_overlay
        )
        # Overlay 左菜单浮在内容之上，需要接近不透明的面板底色；沿用侧栏的
        # 0 透明度会让菜单和页面文字互相穿透。浮层抽屉共用同一套取值。
        self._overlay_panel_bg = qss_color(overlay_surface_color())
        self._overlay_panel_border = qss_color(overlay_border_color())
        self._tooltip_bg = (
            _rgba(colors.surface_overlay, glass_alpha(glass_cfg.tooltip, minimum=0.85))
            if glass
            else colors.surface_overlay
        )

        # 描边与状态层：玻璃模式用正文色的低透明度，深浅主题都会得到
        # 「深色上是白色高光、浅色上是灰色阴影」的 Fluent 分层效果
        self._hairline = _rgba(colors.text_primary, 0.10) if glass else colors.border_hairline
        self._stroke = _rgba(colors.text_primary, 0.16) if glass else colors.border_soft
        self._stroke_strong = _rgba(colors.text_primary, 0.28) if glass else colors.border_strong
        self._fill_rest = _rgba(colors.text_primary, 0.05) if glass else colors.surface_raised
        self._fill_hover = _rgba(colors.text_primary, 0.09) if glass else colors.surface_interactive_hover
        self._fill_pressed = _rgba(colors.text_primary, 0.14) if glass else colors.surface_interactive_pressed
        self._accent_soft = _rgba(colors.accent, 0.18) if glass else colors.accent_soft
        self._accent_wash = _rgba(colors.accent, 0.10) if glass else colors.accent_wash
        self._accent_border = _rgba(colors.accent, 0.85) if glass else colors.accent
        self._gridline = _rgba(colors.text_primary, 0.07) if glass else _mix(colors.surface_card, colors.text_primary, 0.07)
        # 滚动条把手：深浅主题都用正文色 + 透明度，保证在卡片底色上始终可辨
        self._scroll_handle = _rgba(colors.text_primary, 0.36 if glass else 0.30)
        self._scroll_handle_hover = _rgba(colors.text_primary, 0.56 if glass else 0.48)
        self._scroll_handle_pressed = _rgba(colors.text_primary, 0.72 if glass else 0.64)

        # 每种模式下的具体描边
        self._window_border = self._stroke if glass else colors.border_soft
        self._card_border = self._stroke if glass else colors.border_soft
        #: 语义色：直接取主题语义色
        self._danger = QColor(colors.state_danger).name()
        self._success = QColor(colors.state_success).name()
        #: 控件描边：输入框/按钮比卡片描边更深，保证浅色主题下可辨认
        self._control_stroke = (
            _rgba(colors.text_primary, 0.42) if glass else _mix(colors.surface_canvas, colors.text_primary, 0.34)
        )
        self._control_stroke_secondary = (
            _rgba(colors.text_primary, 0.26) if glass else _mix(colors.surface_canvas, colors.text_primary, 0.20)
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
        tokens = self.tokens
        return f"""
            #CWindow_Frame {{
                background: {self._window_bg};
                border-radius: {tokens.radius.window}px;
                border: {tokens.border.width}px solid {self._window_border};
            }}
            /* 设置背景图后由 CWindow.paintEvent 负责绘制，样式表底色必须透明
               （必须用 background 覆盖，只写 background-color 会留下渐变） */
            #CWindow_Frame[hasBackgroundImage="true"] {{
                background: transparent;
            }}
            /* 最大化/贴边：由 CWindow 改这条动态属性即可，无需重建整张样式表 */
            #CWindow_Frame[frameStyle="flat"] {{
                border-radius: 0px;
                border: 0px solid transparent;
            }}
            #CLeftMenu_Bg_Frame {{
                background: {self._sidebar_bg};
            }}
            /* Overlay 模式：左菜单浮在内容区上，改用接近不透明的面板底色 */
            #CLeftMenu_Bg_Frame[overlay="true"] {{
                background: {self._overlay_panel_bg};
                border: 1px solid {self._overlay_panel_border};
            }}
            #CTitleBar_Bg_Frame {{
                background-color: {self._panel_bg};
                border-radius: {tokens.radius.window}px;
            }}
            #CCredits_Bg_Frame {{
                background-color: {self._panel_bg};
                border-radius: {tokens.radius.window}px;
            }}
            #CCredits_Bg_Frame QLabel {{
                font: {tokens.typography.size_caption}pt "{tokens.typography.family}";
                color: {tokens.colors.text_muted};
                padding-left: {tokens.spacing.padding_md}px;
                padding-right: {tokens.spacing.padding_md}px;
            }}
            #CCard_Frame {{
                border: {tokens.border.width}px solid {self._card_border};
                border-radius: {tokens.radius.window}px;
                background-color: {self._card_bg};
            }}
            /* 预览页分区卡片的标题行：强调色短竖线 + 标题 + 延伸发丝线 */
            #CSectionTitle_Rule {{
                background-color: {tokens.colors.accent};
                border-radius: 1px;
            }}
            #CSectionTitle_Label {{
                color: {tokens.colors.text_title};
            }}
            #CSectionTitle_Divider {{
                background-color: {self._hairline};
            }}
            /* 预览区空状态：未安装插件时内容区只有这两行文字，
               必须显式给色，否则 Qt 会用调色板的默认前景色（深色主题下不可见） */
            #GalleryEmptyStateTitle {{
                color: {tokens.colors.text_title};
                font: {tokens.typography.size_display}pt "{tokens.typography.family}";
                font-weight: 600;
                background: transparent;
            }}
            #GalleryEmptyStateHint {{
                color: {tokens.colors.text_muted};
                font: {tokens.typography.size_text}pt "{tokens.typography.family}";
                background: transparent;
            }}
            #CHDiv_Frame {{
                background-color: {self._hairline};
            }}
            #CVDiv_Frame {{
                background-color: {self._hairline};
            }}
            QFrame {{
                color: {tokens.colors.text_primary};
            }}
            /* 不给 QFrame 设全局 font：Qt 会为每个被样式化的 QFrame/QLabel
               建立字体解析缓存，首次应用样式表时实测多占约 65 MB。
               需要字体的组件都在自身局部设置（菜单按钮、标题、设置页等）。 */
        """
