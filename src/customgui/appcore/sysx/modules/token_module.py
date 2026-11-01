from dataclasses import dataclass

from .color_module import ColorPalette


@dataclass(frozen=True)
class ColorTokens:
    surface_app: str
    surface_sidebar: str
    surface_panel: str
    surface_card: str
    surface_interactive: str
    surface_interactive_hover: str
    surface_interactive_pressed: str
    text_primary: str
    text_muted: str
    text_active: str
    border_context: str
    border_transparent: str
    state_active: str


@dataclass(frozen=True)
class TypographyTokens:
    family: str
    size_title: int
    size_subtitle: int
    size_text: int
    weight_tooltip: int
    size_label: int  # 小号标签字号（如左列标题），单位 pt
    weight_label: int  # 小号标签字重


@dataclass(frozen=True)
class SpacingTokens:
    padding_sm: int
    padding_md: int
    menu_item_left: int  # 弹出菜单项与其图标的左内边距
    menu_item_vertical: int  # 弹出菜单项的上下内边距
    menu_indicator_right: int  # 菜单按钮下拉箭头的右内边距
    menu_indicator_offset: int  # 菜单按钮下拉箭头按下/展开时的位移
    label_padding_bottom: int  # 左列标题标签的下内边距


@dataclass(frozen=True)
class RadiusTokens:
    window: int  # 窗口及其内部通用容器的圆角
    tooltip: int


@dataclass(frozen=True)
class BorderTokens:
    width: int
    accent_width: int


@dataclass(frozen=True)
class SizeTokens:
    icon: int
    control_height: int  # 单行输入框等控件的固定高度
    drop_down_width: int  # 下拉框箭头区域宽度
    card_inset: int  # 卡片透明边框宽度（给圆角留出的内缩量）


@dataclass(frozen=True)
class DesignTokens:
    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    radius: RadiusTokens
    border: BorderTokens
    size: SizeTokens


def get_design_tokens() -> DesignTokens:
    from ..config import AppSettings

    return DesignTokens(
        colors=ColorTokens(
            surface_app=ColorPalette.custom_bg_one,
            surface_sidebar=ColorPalette.custom_dark_one,
            surface_panel=ColorPalette.custom_dark_three,
            surface_card=ColorPalette.custom_dark_three,
            surface_interactive=ColorPalette.custom_bg_one,
            surface_interactive_hover=ColorPalette.custom_bg_two,
            surface_interactive_pressed=ColorPalette.custom_bg_three,
            text_primary=ColorPalette.custom_text_foreground,
            text_muted=ColorPalette.custom_text_description,
            text_active=ColorPalette.custom_text_active,
            border_context=ColorPalette.custom_context_color,
            border_transparent=ColorPalette.custom_transparent,
            state_active=ColorPalette.custom_bg_active_one,
        ),
        typography=TypographyTokens(
            family=AppSettings.family,
            size_title=AppSettings.title_size,
            size_subtitle=AppSettings.subtitle_size,
            size_text=AppSettings.text_size,
            weight_tooltip=AppSettings.tooltip_font,
            size_label=9,
            weight_label=700,
        ),
        spacing=SpacingTokens(
            padding_sm=10,
            padding_md=AppSettings.custom_padding,
            menu_item_left=20,
            menu_item_vertical=5,
            menu_indicator_right=4,
            menu_indicator_offset=2,
            label_padding_bottom=2,
        ),
        radius=RadiusTokens(
            window=AppSettings.window_border_radius,
            tooltip=AppSettings.tooltip_border_radius,
        ),
        border=BorderTokens(
            width=AppSettings.window_border_size,
            accent_width=AppSettings.custom_border,
        ),
        size=SizeTokens(
            icon=AppSettings.icon_size,
            control_height=32,
            drop_down_width=20,
            card_inset=12,
        ),
    )
