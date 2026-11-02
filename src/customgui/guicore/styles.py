# 这里决定整个window的总体样式
from PySide6.QtGui import QColor

from customgui.appcore import Logger, PathFactory, get_design_tokens


def _mix(start: str, end: str, ratio: float) -> str:
    """两个颜色按比例混合（``ratio``=0 取 start，=1 取 end）。"""
    begin, finish = QColor(start), QColor(end)
    return QColor(
        round(begin.red() + (finish.red() - begin.red()) * ratio),
        round(begin.green() + (finish.green() - begin.green()) * ratio),
        round(begin.blue() + (finish.blue() - begin.blue()) * ratio),
    ).name()


def region_card_background() -> str:
    """区域背景卡片（主内容区 + 四向抽屉）的底色。

    取 ``surface_app`` 与 ``surface_panel`` 的中间调：既区别于窗口底色
    （否则整块卡片会看不见），也不与页面里的 ``surface_card`` 卡片撞色
    （否则插件页面自己的卡片会融进背景）。

    本函数是**唯一**取色处：样式表与页面过场遮罩共用它，过场擦除时才不会
    在卡片表面留下一条异色带（颜色跳变）。
    """
    colors = get_design_tokens().colors
    return _mix(colors.surface_app, colors.surface_panel, 0.5)


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
    """

    def __init__(self):
        self.tokens = get_design_tokens()
        Logger.debug(f"生成全局样式（设计令牌）: {self.tokens}")
        # 资源以绝对路径注入 QSS，避免相对路径依赖工作目录（跨平台路径统一为正斜杠）
        self._icon_arrow_right = PathFactory.set_svg_icon("icon_arrow_right").replace("\\", "/")
        self._icon_arrow_down = PathFactory.set_svg_icon("icon_arrow_down").replace("\\", "/")
        self.style = f"""
            #CWindow_Frame {{
                background-color: {self.tokens.colors.surface_app};
                border-radius: {self.tokens.radius.window};
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive_pressed};
            }}
            /* 最大化/贴边：由 CWindow 改这条动态属性即可，无需重建整张样式表 */
            #CWindow_Frame[frameStyle="flat"] {{
                border-radius: 0px;
                border: 0px solid transparent;
            }}
            #CLeftMenu_Bg_Frame {{
                background: {self.tokens.colors.surface_sidebar};
            }}
            #CTitleBar_Bg_Frame {{
                background: {self.tokens.colors.surface_panel};
                border-radius: {self.tokens.radius.window};
            }}
            #CCredits_Bg_Frame {{
                background: {self.tokens.colors.surface_panel};
                border-radius: {self.tokens.radius.window};
            }}
            #CCredits_Bg_Frame QLabel {{
                font: {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
                color: {self.tokens.colors.text_primary};
                padding-left: {self.tokens.spacing.padding_md}px;
                padding-right: {self.tokens.spacing.padding_md}px;
            }}
            #CCard_Frame {{
                border: {self.tokens.border.width}px solid transparent;
                border-radius: {self.tokens.radius.window}px;
                border-color: transparent;
                background-color: {self.tokens.colors.surface_card};
            }}
            #CHDiv_Frame {{
                background: {self.tokens.colors.surface_app};
            }}
            #CVDiv_Frame {{
                background: {self.tokens.colors.surface_app};
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

    def update_region_card_style(self):
        """内容区与四向抽屉共用的区域背景卡片。

        卡片只提供**底色 + 圆角**，不再描边：描边会在卡片与内部内容之间夹出
        一圈异色窄环，内容也就不可能和卡片"无缝拼接"。底色见
        :func:`region_card_background`（页面过场遮罩复用同一函数取色，切换时
        不跳色），圆角取 ``radius.window``，五个区域完全同一套规则，深浅主题
        自动跟随。

        内容与卡片齐平由挂载处保证（``ui_main`` 的内容区布局、三向栏目的标题
        条布局边距均为 0），本文件只负责颜色，几何留在实例侧。
        """
        self.style += f"""
            #CRegion_Card_Frame {{
                background-color: {region_card_background()};
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
                border-color: {self.tokens.colors.surface_interactive};
                background-color: {self.tokens.colors.surface_interactive};
                color: {self.tokens.colors.text_primary};
                padding-left: {self.tokens.spacing.padding_md}px;
            }}
            #CMenuButton_PushButton:hover {{
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CMenuButton_PushButton:pressed {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
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
                border: {self.tokens.border.width}px solid transparent;
                border-radius: {self.tokens.radius.window}px;
                background-color: {self.tokens.colors.surface_interactive};
                color: {self.tokens.colors.text_primary};
            }}
            #CPushButton_PushButton:hover {{
                background-color: {self.tokens.colors.surface_interactive_hover};
                border-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CPushButton_PushButton:pressed {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CPushButton_PushButton:flat {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.text_primary};
            }}
        """

    def update_lineedit_style(self):
        """输入框族：颜色与状态（高度/圆角/内边距/字号由组件本地覆盖）。

        hover 描边取「常态描边 → 正文色」的 35% 混合：深色主题变亮、浅色主题变深，
        两个方向都更醒目；直接用 ``surface_interactive_hover`` 会让深色主题的描边
        反而变淡。文字色用 ``text_active`` 保证输入内容的可读性。
        """
        border = self.tokens.colors.surface_interactive_pressed
        hover_border = _mix(border, self.tokens.colors.text_primary, 0.35)
        self.style += f"""
            #CInputText_LineEdit, #CTextarea_PlainTextEdit {{
                background-color: {self.tokens.colors.surface_sidebar};
                border: 1px solid {border};
                color: {self.tokens.colors.text_active};
                placeholder-text-color: {self.tokens.colors.text_muted};
                selection-color: {self.tokens.colors.text_active};
                selection-background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CInputText_LineEdit:hover, #CTextarea_PlainTextEdit:hover {{
                border-color: {hover_border};
            }}
            #CInputText_LineEdit:focus, #CTextarea_PlainTextEdit:focus {{
                border-color: {self.tokens.colors.border_context};
            }}
            #CInputText_LineEdit[invalid="true"], #CTextarea_PlainTextEdit[invalid="true"] {{
                border-color: #f87171;
            }}
            #CInputText_LineEdit:disabled, #CTextarea_PlainTextEdit:disabled {{
                background-color: {self.tokens.colors.surface_app};
                color: {self.tokens.colors.text_muted};
            }}
            #CLineEdit_LineEdit {{
                background-color: {self.tokens.colors.surface_interactive};
                border-radius: {self.tokens.radius.window}px;
                border: {self.tokens.border.width}px solid transparent;
                padding-left: {self.tokens.spacing.padding_sm}px;
                padding-right: {self.tokens.spacing.padding_sm}px;
                selection-color: {self.tokens.colors.surface_interactive_pressed};
                selection-background-color: {self.tokens.colors.surface_interactive_hover};
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
                border: {self.tokens.border.width}px solid {self.tokens.colors.border_transparent};
                border-radius: {self.tokens.radius.window}px;
                background-color: {self.tokens.colors.surface_interactive};
                color: {self.tokens.colors.text_primary};
            }}
            #CComboBox_Field[hovered="true"] {{
                border-color: {self.tokens.colors.border_context};
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CComboBox_Field[focused="true"] {{
                border-color: {self.tokens.colors.text_active};
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CComboBox_Field:disabled {{
                background-color: {self.tokens.colors.surface_app};
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
                border-color: {self.tokens.colors.border_transparent};
                background-color: {self.tokens.colors.surface_interactive};
                color: {self.tokens.colors.text_primary};
            }}
            #CStatusButton_PushButton:hover {{
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CStatusButton_PushButton:pressed {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CStatusButton_PushButton[status="1"] {{
                border-color: {self.tokens.colors.border_context};
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
        """
        self.style += f"""
            #CMenu_Menu {{
                border-style: solid;
                border-color: {self.tokens.colors.border_transparent};
                background-color: {self.tokens.colors.surface_interactive};
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
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
        """

    def update_show_card_style(self):
        """CShowCard：上下分区配色（颜色随主题；圆角由组件按实例覆盖）。"""
        self.style += f"""
            #CShowCard #topArea {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CShowCard #bottomArea {{
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CShowCard #SourceLabel {{
                color: {self.tokens.colors.text_primary};
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
            #CShowCard #IconLabel {{
                background-color: {self.tokens.colors.surface_interactive_hover};
            }}
        """

    def update_tooltip_style(self):
        """提示气泡（``CToolTip``）：三种按钮共用一套样式。

        提示气泡挂在主窗口下（不经过 CWindow），故依赖应用级样式表；强调边方向
        通过动态属性 ``accent`` 选择（left / top / right）。圆角与左右内边距是
        实例级几何，由组件本地覆盖。
        """
        self.style += f"""
            #label_tooltip {{
                background-color: {self.tokens.colors.surface_sidebar};
                color: {self.tokens.colors.text_primary};
                border: 0px solid {self.tokens.colors.border_transparent};
                font: {self.tokens.typography.weight_tooltip} {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
            }}
            #label_tooltip[accent="left"] {{
                border-left: {self.tokens.border.accent_width}px solid {self.tokens.colors.border_context};
            }}
            #label_tooltip[accent="top"] {{
                border-top: {self.tokens.border.accent_width}px solid {self.tokens.colors.border_context};
            }}
            #label_tooltip[accent="right"] {{
                border-right: {self.tokens.border.accent_width}px solid {self.tokens.colors.border_context};
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
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CLeftColumnTitle_Label {{
                color: {self.tokens.colors.text_primary};
                background: none;
            }}
            #CLeftColumnIcon_Frame, #CLeftColumnBtn_Frame, #CLeftColumnContent_Frame {{
                background: none;
            }}
            #CTopColumnTitle_Frame {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CTopColumnTitle_Label {{
                color: {self.tokens.colors.text_primary};
                background: none;
            }}
            #CTopColumnIcon_Frame, #CTopColumnBtn_Frame, #CTopColumnContent_Frame {{
                background: none;
            }}
            #CBottomColumnTitle_Frame {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
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
        """数据表格与分页条：表头、行、选中态、网格线、滚动条。"""
        selection = self.tokens.colors.surface_interactive_hover
        self.style += f"""
            #CDataTable_View, #CDataTable_FrozenView {{
                background-color: {self.tokens.colors.surface_card};
                alternate-background-color: {self.tokens.colors.surface_panel};
                color: {self.tokens.colors.text_primary};
                border: 1px solid {self.tokens.colors.surface_interactive_pressed};
                border-radius: 8px;
                gridline-color: {self.tokens.colors.surface_interactive_pressed};
                selection-background-color: {selection};
                selection-color: {self.tokens.colors.text_active};
                outline: 0;
            }}
            #CDataTable_View::item, #CDataTable_FrozenView::item {{
                padding-left: 10px;
                padding-right: 10px;
                border: none;
            }}
            #CDataTable_View::item:hover, #CDataTable_FrozenView::item:hover {{
                background-color: {self.tokens.colors.surface_interactive};
            }}
            #CDataTable_View QHeaderView::section,
            #CDataTable_FrozenView QHeaderView::section {{
                background-color: {self.tokens.colors.surface_panel};
                color: {self.tokens.colors.text_primary};
                border: none;
                border-bottom: 1px solid {self.tokens.colors.surface_interactive_pressed};
                padding: 8px 10px;
                font-weight: 600;
            }}
            #CDataTable_View QTableCornerButton::section,
            #CDataTable_FrozenView QTableCornerButton::section {{
                background-color: {self.tokens.colors.surface_panel};
                border: none;
            }}
            #CDataTable_View QScrollBar:vertical,
            #CDataTable_FrozenView QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 0px;
            }}
            #CDataTable_View QScrollBar::handle:vertical,
            #CDataTable_FrozenView QScrollBar::handle:vertical {{
                background: {self.tokens.colors.surface_interactive_pressed};
                min-height: 24px;
                border-radius: 4px;
            }}
            #CDataTable_View QScrollBar::add-line:vertical,
            #CDataTable_View QScrollBar::sub-line:vertical,
            #CDataTable_FrozenView QScrollBar::add-line:vertical,
            #CDataTable_FrozenView QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            #CDataTable_Empty, #CDataTable_Loading {{
                background-color: {self.tokens.colors.surface_card};
                color: {self.tokens.colors.text_muted};
                border: 1px solid {self.tokens.colors.surface_interactive_pressed};
                border-radius: 8px;
            }}
            #CDataTable_Detail {{
                background-color: {self.tokens.colors.surface_panel};
                border: 1px solid {self.tokens.colors.surface_interactive_pressed};
                border-radius: 8px;
            }}
            #CPaginator_Label {{
                color: {self.tokens.colors.text_muted};
                font: {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
                padding-left: 8px;
            }}
        """
