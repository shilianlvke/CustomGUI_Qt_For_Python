"""模块说明。"""

import importlib
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
    app_settings = importlib.import_module("AppCore.SYS.other.folder_tools").AppSettings

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
            family=app_settings.family,
            size_title=app_settings.title_size,
            size_subtitle=app_settings.subtitle_size,
            size_text=app_settings.text_size,
            weight_tooltip=app_settings.tooltip_font,
        ),
        spacing=SpacingTokens(
            padding_sm=10,
            padding_md=app_settings.custom_padding,
        ),
        radius=RadiusTokens(
            window=app_settings.window_border_radius,
            tooltip=app_settings.tooltip_border_radius,
        ),
        border=BorderTokens(
            width=app_settings.window_border_size,
            accent_width=app_settings.custom_border,
        ),
        size=SizeTokens(
            icon=app_settings.icon_size,
        ),
    )
