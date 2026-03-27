"""模块说明。"""

# 这里决定整个window的总体样式
from AppCore import get_design_tokens


class Styles:
    """全局样式生成器。

    职责:
    - 根据设计令牌构建应用样式表字符串。
    - 聚合按钮、输入框、下拉框等组件样式。
    """

    def __init__(self) -> None:
        """初始化样式生成器并构建样式文本。"""
        self.tokens = get_design_tokens()
        self.style = f"""
            #CWindow_Frame {{
                background-color: {self.tokens.colors.surface_app};
                border-radius: {self.tokens.radius.window};
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive_pressed};
            }}
            #CLeftMenu_Bg_Frame {{
                background: {self.tokens.colors.surface_sidebar};
                border-radius: {self.tokens.radius.window};
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
        self.update_lineedit_style()
        self.update_combobox_style()

    def update_btn_style(self) -> None:
        """追加按钮相关样式片段。

        返回:
        - None
        """
        self.style += f"""
            #CMenuButton_PushButton {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive};
                border-radius: {self.tokens.radius.window}px;
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
                image: url(resource/CustomUI/images/svg_icons/icon_arrow_right.svg);
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
                padding-right: 4px;
                subcontrol-position: right;
            }}
            #CMenuButton_PushButton::menu-indicator:pressed, #CMenuButton_PushButton::menu-indicator:open {{
                image: url(resource/CustomUI/images/svg_icons/icon_arrow_down.svg);
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
                position: relative;
                top: 2px; left: 2px; /* shift the arrow by 2 px */
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

    def update_lineedit_style(self) -> None:
        """追加输入框相关样式片段。

        返回:
        - None
        """
        self.style += f"""
            #CLineEdit_LineEdit {{
                background-color: {self.tokens.colors.surface_interactive};
                border-radius: {self.tokens.radius.window}px;
                border: {self.tokens.border.width}px solid transparent;
                padding-left: {self.tokens.spacing.padding_sm}px;
                padding-right: {self.tokens.spacing.padding_sm}px;
                selection-color: {self.tokens.colors.surface_interactive_pressed};
                selection-background-color: {self.tokens.colors.surface_interactive_hover};
                color: {self.tokens.colors.text_primary};
                height: 32px;
            }}
            #CLineEdit_LineEdit:focus {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive_hover};
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CLineEdit_LineEdit:hover {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive_hover};
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
        """

    def update_combobox_style(self) -> None:
        """追加下拉框相关样式片段。

        返回:
        - None
        """
        self.style += f"""
            #CComboBox_ComboBox {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive};
                border-radius: {self.tokens.radius.window}px;
                background-color: {self.tokens.colors.surface_interactive};
                color: {self.tokens.colors.text_primary};
                padding-left: {self.tokens.spacing.padding_sm}px;
            }}
            #CComboBox_ComboBox:hover {{
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CComboBox_ComboBox QAbstractItemView {{
                border: {self.tokens.border.width}px solid {self.tokens.colors.surface_interactive};
                border-radius: {self.tokens.radius.window}px;
                outline: none;  /* 移除选中虚线框 */
                color: {self.tokens.colors.text_primary};
                background-color: transparent;
            }}
            #CComboBox_ComboBox QAbstractItemView::item {{
                padding-left:{self.tokens.spacing.padding_sm}px;
                color: {self.tokens.colors.text_primary};
                background-color: {self.tokens.colors.surface_interactive};
            }}
            #CComboBox_ComboBox QAbstractItemView::item:hover {{
                /*border-radius: {self.tokens.radius.window}px;*/
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CComboBox_ComboBox QAbstractItemView::item:selected {{
                /*border-radius: {self.tokens.radius.window}px;*/
                background-color: {self.tokens.colors.surface_interactive_pressed};
            }}
            #CComboBox_ComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 20px;
                border: none;
            }}
            #CComboBox_ComboBox::down-arrow {{
                image: url(resource/CustomUI/images/svg_icons/icon_arrow_right.svg);
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
            }}
            #CComboBox_ComboBox::down-arrow:on {{
                image: url(resource/CustomUI/images/svg_icons/icon_arrow_down.svg);
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
            }}
        """
