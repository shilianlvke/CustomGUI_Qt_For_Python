"""模块说明。"""

from dataclasses import dataclass

from .color_module import ColorPalette


@dataclass(frozen=True)
class ColorTokens:
    """设计系统颜色令牌集合。"""

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


@dataclass(frozen=True)
class TypographyTokens:
    """设计系统排版令牌集合。"""

    family: str
    size_title: int
    size_subtitle: int
    size_text: int
    weight_tooltip: int


@dataclass(frozen=True)
class SpacingTokens:
    """设计系统间距令牌集合。"""

    padding_sm: int
    padding_md: int


@dataclass(frozen=True)
class RadiusTokens:
    """设计系统圆角令牌集合。"""

    window: int
    tooltip: int


@dataclass(frozen=True)
class BorderTokens:
    """设计系统边框令牌集合。"""

    width: int
    accent_width: int


@dataclass(frozen=True)
class SizeTokens:
    """设计系统尺寸令牌集合。"""

    icon: int


@dataclass(frozen=True)
class DesignTokens:
    """聚合后的设计令牌对象。"""

    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    radius: RadiusTokens
    border: BorderTokens
    size: SizeTokens


def get_design_tokens() -> DesignTokens:
    """构建设计令牌快照。

    职责:
    - 从当前颜色与应用设置读取值。
    - 返回供 UI 层消费的统一 DesignTokens 对象。

    返回:
    - DesignTokens: 当前上下文下的设计令牌集合。
    """
    from AppCore.SYS.other.folder_tools import AppSettings  # noqa: PLC0415

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
        ),
        typography=TypographyTokens(
            family=AppSettings.family,
            size_title=AppSettings.title_size,
            size_subtitle=AppSettings.subtitle_size,
            size_text=AppSettings.text_size,
            weight_tooltip=AppSettings.tooltip_font,
        ),
        spacing=SpacingTokens(
            padding_sm=10,
            padding_md=AppSettings.custom_padding,
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
        ),
    )
