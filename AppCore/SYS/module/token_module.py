"""设计令牌模块。

职责:
- 定义设计系统的令牌集合结构（颜色、排版、间距、圆角、边框、尺寸）。
- 从当前主题与窗口设置派生设计令牌快照。
"""

from dataclasses import dataclass

from .token_models import ThemeColors, WindowSettings


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


def build_design_tokens(theme: ThemeColors, settings: WindowSettings) -> DesignTokens:
    """从主题与窗口设置派生设计令牌快照。

    参数:
    - theme: 当前主题颜色模型。
    - settings: 窗口设置模型。

    返回:
    - DesignTokens: 派生出的设计令牌集合。
    """
    return DesignTokens(
        colors=ColorTokens(
            surface_app=theme.custom_bg_one,
            surface_sidebar=theme.custom_dark_one,
            surface_panel=theme.custom_dark_three,
            surface_card=theme.custom_dark_three,
            surface_interactive=theme.custom_bg_one,
            surface_interactive_hover=theme.custom_bg_two,
            surface_interactive_pressed=theme.custom_bg_three,
            text_primary=theme.custom_text_foreground,
            text_muted=theme.custom_text_description,
            text_active=theme.custom_text_active,
            border_context=theme.custom_context_color,
            border_transparent=theme.custom_transparent,
        ),
        typography=TypographyTokens(
            family=settings.family,
            size_title=settings.title_size,
            size_subtitle=settings.subtitle_size,
            size_text=settings.text_size,
            weight_tooltip=settings.tooltip_font,
        ),
        spacing=SpacingTokens(
            padding_sm=10,
            padding_md=settings.custom_padding,
        ),
        radius=RadiusTokens(
            window=settings.window_border_radius,
            tooltip=settings.tooltip_border_radius,
        ),
        border=BorderTokens(
            width=settings.window_border_size,
            accent_width=settings.custom_border,
        ),
        size=SizeTokens(
            icon=settings.icon_size,
        ),
    )
