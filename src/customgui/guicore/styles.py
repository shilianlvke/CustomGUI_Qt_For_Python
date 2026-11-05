# 这里决定整个window的总体样式
from PySide6.QtGui import QColor

from customgui.appcore import AppSettings, Logger, PathFactory, get_design_tokens

from .acrylic import MIN_WINDOW_GLASS_ALPHA, acrylic_active, glass_alpha

# ----------------------------------------------------------------------
# 亚克力玻璃层的不透明度
# ----------------------------------------------------------------------
# 具体取值见 settings/window.yaml 的 ``glass`` 分组（0-1），
# 叠加顺序为：桌面 -> 亚克力色调（acrylic.opacity）-> 窗口 -> 侧栏/面板
# -> 区域卡片 -> 卡片。约束：太大看不到模糊，太小会牺牲文字可读性。
# 主界面（CWindow）本身就是背景层：由它铺这层玻璃，标题栏、侧栏、内容卡片
# 都是它的子控件，不再额外引入任何"背景窗口/背景控件"。这样标题栏的鼠标
# 命中区域、拖动与双击最大化等原生交互都留在原来的控件树上。



def _mix(start: str, end: str, ratio: float) -> str:
    """两个颜色按比例混合（``ratio``=0 取 start，=1 取 end）。"""
    begin, finish = QColor(start), QColor(end)
    return QColor(
        round(begin.red() + (finish.red() - begin.red()) * ratio),
        round(begin.green() + (finish.green() - begin.green()) * ratio),
        round(begin.blue() + (finish.blue() - begin.blue()) * ratio),
    ).name()


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


class Styles:
    """全局样式表：所有组件的**颜色 / 状态 / 字体**都集中在这里。

    约定（与 ``CPushButton`` 一致）：

    1. 组件在 ``__init__`` 里只声明 ``setObjectName("<组件名>_<Qt类名>")``；
    2. 组件的全部颜色/状态/字体样式在本文件内按该 objectName 定义；
    3. 组件**不订阅主题**——主题切换时由 ``CWindow.apply_style()`` 整体重建
       本样式表并下发（窗口级 + 应用级），组件自动跟随；
    4. **几何量不进本文件**：圆角、边框宽度、内边距、固定宽高、偏移等与主题
       无关的尺寸，一律由组件本地用一条只含几何属性的 ``setStyleSheet`` 提供
       （见 ``CStatusButton._apply_geometry``）；这些尺寸的取值**全部来自设计
       令牌**（``customgui.appcore.sysx.modules.token_module``），组件暴露的几何参数默认取
       ``None`` 并回落到对应令牌，显式传参即可覆盖。

    亚克力材质：``acrylic_active()`` 为真时，各层底色改用半透明 ``rgba()``，
    透出系统级模糊背景；不可用时保持原有的不透明主题色，避免「半透明但
    没有模糊」的脏画面。悬浮/按下等状态色同样按透明度分档，保证玻璃上仍然
    有清晰的层次。
    """

    def __init__(self):
        self.tokens = get_design_tokens()
        Logger.debug(f"生成全局样式（设计令牌）: {self.tokens}")
        # 资源以绝对路径注入 QSS，避免相对路径依赖工作目录（跨平台路径统一为正斜杠）
        self._icon_arrow_right = PathFactory.set_svg_icon("icon_arrow_right").replace("\\", "/")
        self._icon_arrow_down = PathFactory.set_svg_icon("icon_arrow_down").replace("\\", "/")

        colors = self.tokens.colors
        glass = acrylic_active()
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
        self._sidebar_bg = _rgba(colors.surface_sidebar, glass_alpha(glass_cfg.sidebar)) if glass else colors.surface_sidebar
        self._panel_bg = _rgba(colors.surface_panel, glass_alpha(glass_cfg.panel)) if glass else colors.surface_panel
        self._card_bg = _rgba(colors.surface_card, glass_alpha(glass_cfg.card)) if glass else colors.surface_card
        self._region_bg = _rgba(region_card_tint(), glass_alpha(glass_cfg.region)) if glass else region_card_tint()
        self._control_bg = _rgba(colors.surface_sidebar, glass_alpha(glass_cfg.control)) if glass else colors.surface_sidebar
        self._menu_bg = _rgba(colors.surface_interactive, glass_cfg.menu) if glass else colors.surface_interactive
        # Overlay 左菜单浮在内容之上，需要接近不透明的面板底色；沿用侧栏的
        # 0 透明度会让菜单和页面文字互相穿透。
        self._overlay_panel_bg = (
            _rgba(colors.surface_panel, glass_cfg.overlay_panel) if glass else colors.surface_panel
        )
        self._overlay_panel_border = _rgba(colors.text_primary, 0.14) if glass else colors.surface_interactive_pressed
        self._tooltip_bg = _rgba(colors.surface_sidebar, glass_cfg.tooltip) if glass else colors.surface_sidebar

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
        self._input_border = self._stroke if glass else colors.surface_interactive_pressed
        self._card_border = self._stroke if glass else colors.border_transparent

        self.style = f"""
            #CWindow_Frame {{
                background-color: {self._window_bg};
                border-radius: {self.tokens.radius.window}px;
                border: {self.tokens.border.width}px solid {self._window_border};
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

    def update_region_card_style(self):
        """内容区与四向抽屉共用的区域背景卡片。

        卡片只提供**底色 + 圆角**，不再描边：描边会在卡片与内部内容之间夹出
        一圈异色窄环，内容也就不可能和卡片"无缝拼接"。底色见
        :func:`region_card_tint`，圆角取 ``radius.window``，五个区域完全同一
        套规则，深浅主题自动跟随。

        亚克力模式下底色是半透明玻璃层，与上方的标题栏/侧栏形成层次；页面
        过场采用透明擦除，擦除空白直接露出这层玻璃，不再用实色近似。内容与
        卡片齐平由挂载处保证（``ui_main`` 的内容区布局、三向栏目的标题条布局
        边距均为 0），本文件只负责颜色，几何留在实例侧。
        """
        self.style += f"""
            #CRegion_Card_Frame {{
                background-color: {self._region_bg};
                border: 0px solid transparent;
                border-radius: {self.tokens.radius.window}px;
            }}
        """

    def update_btn_style(self):
        """按钮族样式。

        ``CMenuButton`` / ``CPushButton`` 的圆角与边框宽度属实例级几何，由组件
        本地覆盖；这里只提供颜色、内边距与 ``::menu-indicator`` 的图标资源。
        """
        self.style += f"""
            #CMenuButton_PushButton {{
                border-style: solid;
                border-color: {self._stroke};
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
                padding-left: {self.tokens.spacing.padding_md}px;
            }}
            #CMenuButton_PushButton:hover {{
                background-color: {self._fill_hover};
                border-color: {self._stroke_strong};
            }}
            #CMenuButton_PushButton:pressed {{
                background-color: {self._fill_pressed};
            }}
            #CMenuButton_PushButton::menu-indicator {{
                image: url({self._icon_arrow_right});
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
                subcontrol-position: right;
            }}
            #CMenuButton_PushButton::menu-indicator:pressed, #CMenuButton_PushButton::menu-indicator:open {{
                image: url({self._icon_arrow_down});
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
            }}
        """
        self.style += f"""
            #CPushButton_PushButton {{
                border: {self.tokens.border.width}px solid {self._stroke};
                border-radius: {self.tokens.radius.window}px;
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
            }}
            #CPushButton_PushButton:hover {{
                background-color: {self._fill_hover};
                border-color: {self._stroke_strong};
            }}
            #CPushButton_PushButton:pressed {{
                background-color: {self._fill_pressed};
            }}
            #CPushButton_PushButton:flat {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.text_primary};
            }}
        """

    def update_lineedit_style(self):
        """输入框族：颜色与状态（高度/圆角/内边距/字号由组件本地覆盖）。

        hover 描边取「常态描边 → 正文色」的 35% 混合：深色主题变亮、浅色主题变深，
        两个方向都更醒目；玻璃模式下描边本身已是低透明度正文色，混合后仍是
        同一色相，不会出现"浮在玻璃上的另一个色块"。文字色用 ``text_active``
        保证输入内容的可读性。
        """
        border = self._input_border
        hover_border = _mix(border, self.tokens.colors.text_primary, 0.35) if self.glass else border
        selection_bg = self._accent_soft
        self.style += f"""
            #CInputText_LineEdit, #CTextarea_PlainTextEdit {{
                background-color: {self._control_bg};
                border: 1px solid {border};
                color: {self.tokens.colors.text_active};
                placeholder-text-color: {self.tokens.colors.text_muted};
                selection-color: {self.tokens.colors.text_active};
                selection-background-color: {selection_bg};
            }}
            #CInputText_LineEdit:hover, #CTextarea_PlainTextEdit:hover {{
                border-color: {hover_border};
            }}
            #CInputText_LineEdit:focus, #CTextarea_PlainTextEdit:focus {{
                border-color: {self._accent_border};
            }}
            #CInputText_LineEdit[invalid="true"], #CTextarea_PlainTextEdit[invalid="true"] {{
                border-color: #f87171;
            }}
            #CInputText_LineEdit:disabled, #CTextarea_PlainTextEdit:disabled {{
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_muted};
            }}
            #CLineEdit_LineEdit {{
                background-color: {self._fill_rest};
                border-radius: {self.tokens.radius.window}px;
                border: {self.tokens.border.width}px solid {self._stroke};
                padding-left: {self.tokens.spacing.padding_sm}px;
                padding-right: {self.tokens.spacing.padding_sm}px;
                selection-color: {self.tokens.colors.text_active};
                selection-background-color: {self._accent_soft};
                color: {self.tokens.colors.text_primary};
            }}
        """

    def update_combobox_style(self):
        """CComboBox：自绘下拉框的底色、描边与三态（hover / focused / disabled）。

        ``CComboBox`` 不再继承 ``QComboBox``，弹层与箭头都是自绘的，因此这里
        不再声明 ``::drop-down`` / ``::down-arrow`` / ``QAbstractItemView`` 等
        子控件规则——那些规则只对原生弹出层生效，留着只会误导后来者。
        弹层内部的列表样式由组件自身按当前主题实时生成（见 ``popup.py``）。
        """
        self.style += f"""
            #CComboBox_Field {{
                border: {self.tokens.border.width}px solid {self._stroke};
                border-radius: {self.tokens.radius.window}px;
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
            }}
            #CComboBox_Field[hovered="true"] {{
                border-color: {self._stroke_strong};
                background-color: {self._fill_hover};
            }}
            #CComboBox_Field[focused="true"] {{
                border-color: {self._accent_border};
                background-color: {self._fill_hover};
            }}
            #CComboBox_Field:disabled {{
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_muted};
            }}
        """

    def update_status_button_style(self):
        """CStatusButton：颜色与三态边框色。

        圆角（``radius``）与边框宽度（``border_size``）是实例参数，由组件本地
        用一条只含几何属性的样式覆盖。状态经动态属性 ``status`` 选择。
        """
        self.style += f"""
            #CStatusButton_PushButton {{
                border-style: solid;
                border-color: {self._stroke};
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
            }}
            #CStatusButton_PushButton:hover {{
                background-color: {self._fill_hover};
                border-color: {self._stroke_strong};
            }}
            #CStatusButton_PushButton:pressed {{
                background-color: {self._fill_pressed};
            }}
            #CStatusButton_PushButton[status="1"] {{
                border-color: {self._accent_border};
                background-color: {self._accent_soft};
            }}
            #CStatusButton_PushButton[status="-1"] {{
                border-color: {self.tokens.colors.state_active};
            }}
        """

    def update_menu_style(self):
        """CMenu 弹出菜单：颜色与结构。

        弹出菜单是独立顶层窗口，不经过 CWindow，故依赖 ``CWindow.apply_style``
        下发的应用级样式表着色。圆角/边框宽度/菜单项内边距为实例级几何，由组件
        本地覆盖；``is_transparent`` 经动态属性 ``transparent`` 选择。

        玻璃模式下菜单保持高不透明度（``GLASS_MENU``）：弹层背后没有应用窗口
        的玻璃层可透，过低会直接看到未模糊的桌面。
        """
        self.style += f"""
            #CMenu_Menu {{
                border-style: solid;
                border-color: {self._stroke};
                background-color: {self._menu_bg};
                color: {self.tokens.colors.text_primary};
            }}
            #CMenu_Menu[transparent="true"] {{
                background-color: {self.tokens.colors.border_transparent};
            }}
            #CMenu_Menu::item {{
                border-style: solid;
                border-color: {self.tokens.colors.border_transparent};
                background-color: transparent;
            }}
            #CMenu_Menu::item:selected {{
                background-color: {self._accent_soft};
            }}
        """

    def update_show_card_style(self):
        """CShowCard：上下分区配色（颜色随主题；圆角由组件按实例覆盖）。"""
        self.style += f"""
            #CShowCard #topArea {{
                background-color: {self._fill_pressed};
            }}
            #CShowCard #bottomArea {{
                background-color: {self._fill_hover};
            }}
            #CShowCard #SourceLabel {{
                color: {self.tokens.colors.text_primary};
                background-color: {self._fill_hover};
            }}
            #CShowCard #IconLabel {{
                background-color: {self._fill_hover};
            }}
        """

    def update_tooltip_style(self):
        """提示气泡（``CToolTip``）：三种按钮共用一套样式。

        提示气泡挂在主窗口下（不经过 CWindow），故依赖应用级样式表；强调边方向
        通过动态属性 ``accent`` 选择（left / top / right）。圆角与左右内边距是
        实例级几何，由组件本地覆盖。

        气泡是顶层弹窗，与菜单同理保持较高不透明度，保证浮在任意背景上可读。
        """
        self.style += f"""
            #label_tooltip {{
                background-color: {self._tooltip_bg};
                color: {self.tokens.colors.text_primary};
                border: 0px solid {self.tokens.colors.border_transparent};
                font: {self.tokens.typography.weight_tooltip} {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
            }}
            #label_tooltip[accent="left"] {{
                border-left: {self.tokens.border.accent_width}px solid {self._accent_border};
            }}
            #label_tooltip[accent="top"] {{
                border-top: {self.tokens.border.accent_width}px solid {self._accent_border};
            }}
            #label_tooltip[accent="right"] {{
                border-right: {self.tokens.border.accent_width}px solid {self._accent_border};
            }}
        """

    def update_title_bar_style(self):
        """标题栏标题文字。"""
        self.style += f"""
            #CTitleBar_Title_Label {{
                font: {self.tokens.typography.size_title}pt "{self.tokens.typography.family}";
            }}
        """

    def update_columns_style(self):
        """四向抽屉（栏目）的标题区与无背景容器框。

        左/右/顶/底四列同构：标题背景框 + 标题文字，图标位/按钮位/内容框保持
        透明。背景框圆角与标题的内边距/字体是组件本地几何，由组件覆盖。容器框
        改用 ID 选择器（原来是不带选择器的裸规则，会级联到所有子孙控件）。
        """
        self.style += f"""
            #CLeftColumnTitle_Frame {{
                background-color: {self._fill_pressed};
            }}
            #CLeftColumnTitle_Label {{
                color: {self.tokens.colors.text_primary};
                background: none;
            }}
            #CLeftColumnIcon_Frame, #CLeftColumnBtn_Frame, #CLeftColumnContent_Frame {{
                background: none;
            }}
            #CTopColumnTitle_Frame {{
                background-color: {self._fill_pressed};
            }}
            #CTopColumnTitle_Label {{
                color: {self.tokens.colors.text_primary};
                background: none;
            }}
            #CTopColumnIcon_Frame, #CTopColumnBtn_Frame, #CTopColumnContent_Frame {{
                background: none;
            }}
            #CBottomColumnTitle_Frame {{
                background-color: {self._fill_pressed};
            }}
            #CBottomColumnTitle_Label {{
                color: {self.tokens.colors.text_primary};
                background: none;
            }}
            #CBottomColumnIcon_Frame, #CBottomColumnBtn_Frame, #CBottomColumnContent_Frame {{
                background: none;
            }}
        """

    def update_grips_style(self):
        """窗口缩放夹点（调试边界）。

        颜色沿用原有调试配色以保持外观不变；``hide_grips`` 为真时经动态属性
        ``colored="false"`` 置为透明。

        四角夹点内嵌一个 ``QSizeGrip``（原生缩放角）。历史实现用**裸规则**
        ``background: transparent`` 覆盖夹点，该规则会级联到子控件 ``QSizeGrip``，
        使其改用 ``QStyleSheetStyle`` 绘制、不再画出原生点阵；若这里只写 ID
        选择器，子控件不受影响会重新画出灰色点阵，故须显式补一条后代规则。
        """
        self.style += """
            #top_left_grip, #top_right_grip, #bottom_left_grip, #bottom_right_grip {
                background-color: #333;
                border: 2px solid #55FF00;
            }
            #top_left_grip QSizeGrip, #top_right_grip QSizeGrip,
            #bottom_left_grip QSizeGrip, #bottom_right_grip QSizeGrip {
                background: transparent;
            }
            #top_grip {
                background-color: rgb(85, 255, 255);
            }
            #bottom_grip {
                background-color: rgb(85, 170, 0);
            }
            #left {
                background-color: rgb(255, 121, 198);
            }
            #right {
                background-color: rgb(255, 0, 127);
            }
            #top_left_grip[colored="false"], #top_right_grip[colored="false"],
            #bottom_left_grip[colored="false"], #bottom_right_grip[colored="false"],
            #top_grip[colored="false"], #bottom_grip[colored="false"],
            #left[colored="false"], #right[colored="false"] {
                background: transparent;
                border: none;
            }
        """

    def update_table_style(self):
        """数据表格与分页条：表头、行、选中态、网格线、滚动条。

        玻璃模式下整张表是低透明度玻璃板，表头再叠一层更实的底色；网格线
        与选中态全部改用正文色/强调色的低透明度写法，避免在玻璃上出现
        与主题无关的硬色块。
        """
        selection = self._accent_soft
        self.style += f"""
            #CDataTable_View, #CDataTable_FrozenView {{
                background-color: {self._card_bg};
                alternate-background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
                border: 1px solid {self._stroke};
                border-radius: 8px;
                gridline-color: {self._gridline};
                selection-background-color: {selection};
                selection-color: {self.tokens.colors.text_active};
                outline: 0;
            }}
            #CDataTable_View::item, #CDataTable_FrozenView::item {{
                padding-left: 10px;
                padding-right: 10px;
                border: none;
                border-bottom: 1px solid {self._gridline};
            }}
            #CDataTable_View::item:hover, #CDataTable_FrozenView::item:hover {{
                background-color: {self._fill_hover};
            }}
            #CDataTable_View QHeaderView::section,
            #CDataTable_FrozenView QHeaderView::section {{
                background-color: {self._fill_hover};
                color: {self.tokens.colors.text_primary};
                border: none;
                border-bottom: 1px solid {self._stroke};
                padding: 8px 10px;
                font-weight: 600;
            }}
            #CDataTable_View QTableCornerButton::section,
            #CDataTable_FrozenView QTableCornerButton::section {{
                background-color: {self._fill_hover};
                border: none;
            }}
            #CDataTable_Empty, #CDataTable_Loading {{
                background-color: {self._card_bg};
                color: {self.tokens.colors.text_muted};
                border: 1px solid {self._stroke};
                border-radius: 8px;
            }}
            #CDataTable_Detail {{
                background-color: {self._fill_rest};
                border: 1px solid {self._stroke};
                border-radius: 8px;
            }}
            #CPaginator_Label {{
                color: {self.tokens.colors.text_muted};
                font: {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
                padding-left: 8px;
            }}
        """

    def update_scrollbar_style(self):
        """全局滚动条：透明轨道 + 细圆角把手，横纵一致，无原生箭头。

        历史实现只在表格与文件上传列表里各写了一份滚动条规则，
        ``CScrollArea``、``CTextarea`` 等可滚动控件没有规则，仍由平台样式
        绘制（带上下箭头、方形深色轨道）。此前 ``CScrollArea`` 一直隐藏滚动条
        所以看不出来；启用“按需显示”后，原生滚动条就与 Fluent 卡片格格不入。
        这里改为一条**全局规则**统一横/纵滚动条，各组件不再各写一份：

        - 轨道透明、无边框、无箭头（``add-line``/``sub-line`` 归零）；
        - 把手 12px 轨道内缩 3px，得到 6px 宽的胶囊形（圆角 3px）；
        - 常态/悬停/按下三档透明度，深浅主题与亚克力开关下都保持可辨。
        """
        thickness = 12
        inset = 3
        min_length = 32
        radius = 3
        self.style += f"""
            QScrollBar:vertical {{
                background: transparent;
                width: {thickness}px;
                margin: 0px;
                border: none;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: {thickness}px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {self._scroll_handle};
                min-height: {min_length}px;
                margin: {inset}px;
                border-radius: {radius}px;
            }}
            QScrollBar::handle:horizontal {{
                background: {self._scroll_handle};
                min-width: {min_length}px;
                margin: {inset}px;
                border-radius: {radius}px;
            }}
            QScrollBar::handle:vertical:hover,
            QScrollBar::handle:horizontal:hover {{
                background: {self._scroll_handle_hover};
            }}
            QScrollBar::handle:vertical:pressed,
            QScrollBar::handle:horizontal:pressed {{
                background: {self._scroll_handle_pressed};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            QAbstractScrollArea::corner {{
                background: transparent;
                border: none;
            }}
        """
