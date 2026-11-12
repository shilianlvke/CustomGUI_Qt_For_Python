"""设计令牌：颜色 / 排版 / 间距 / 圆角 / 描边 / 尺寸的唯一取值入口。

表现层（``sllkgui.guicore``）不直接拼色值，一律经 ``get_design_tokens()``
读取本模块的令牌。令牌在每次调用时按当前 ``ColorPalette`` 与 ``AppSettings``
重新计算，因此主题切换后重新取一次即可拿到新值（``Styles`` 就是这样做的）。

颜色部分按**表面阶梯**组织：画布 → 侧栏 → 面板 → 卡片 → 抬升层，另加
交互层（常态 / 悬停 / 按下）与强调色梯度。强调色梯度由主题的
``custom_context_color`` 派生，深浅主题共用同一套派生规则。
"""

from __future__ import annotations

from dataclasses import dataclass

from .color_module import ColorPalette


def _rgb(value: str) -> tuple[int, int, int] | None:
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def _mix(first: str, second: str, ratio: float) -> str:
    """按比例混合两个颜色（0 = 全取 first，1 = 全取 second）。"""
    begin, finish = _rgb(first), _rgb(second)
    if begin is None or finish is None:
        return first
    ratio = max(0.0, min(1.0, float(ratio)))
    mixed = tuple(round(start + (end - start) * ratio) for start, end in zip(begin, finish, strict=True))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _luminance(value: str) -> float:
    """WCAG 相对亮度（0 = 黑，1 = 白）。"""
    rgb = _rgb(value)
    if rgb is None:
        return 0.0

    def channel(raw: int) -> float:
        ratio = raw / 255.0
        return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(item) for item in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def readable_on(background: str, *, light: str = "#ffffff", dark: str = "#10140f") -> str:
    """在给定底色上挑一个对比度更高的文字色（默认白 / 近黑）。"""
    return dark if _contrast(dark, background) >= _contrast(light, background) else light


@dataclass(frozen=True)
class ColorTokens:
    # ---- 表面阶梯 ----
    surface_app: str  # 画布（兼容旧字段名，等价于 surface_canvas）
    surface_canvas: str
    surface_sunken: str
    surface_sidebar: str
    surface_panel: str
    surface_card: str
    surface_raised: str
    surface_overlay: str
    # ---- 交互层 ----
    surface_interactive: str
    surface_interactive_hover: str
    surface_interactive_pressed: str
    # ---- 文本 ----
    text_title: str
    text_primary: str
    text_muted: str
    text_active: str
    text_on_accent: str
    # ---- 强调色 ----
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str  # 强调色 16% 混合，用于选中底
    accent_wash: str  # 强调色 8% 混合，用于极轻的着色区
    # ---- 描边 ----
    border_hairline: str
    border_soft: str
    border_strong: str
    border_context: str
    border_transparent: str
    # ---- 语义色 ----
    state_active: str
    state_success: str
    state_warning: str
    state_danger: str


@dataclass(frozen=True)
class TypographyTokens:
    family: str
    size_display: int  # 页面/区块主标题
    size_title: int
    size_subtitle: int
    size_text: int
    size_caption: int  # 页脚、键名等最小号文字
    weight_tooltip: int
    size_label: int  # 小号标签字号（如左列标题），单位 pt
    weight_label: int  # 小号标签字重
    tracking_title: float  # 标题字距（像素），小字号中文不宜过大


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
    control: int  # 标准控件（按钮 / 输入框 / 菜单项）的圆角
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
    accent_bar: int  # 侧栏选中指示条宽度


@dataclass(frozen=True)
class DesignTokens:
    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    radius: RadiusTokens
    border: BorderTokens
    size: SizeTokens


def _color_tokens() -> ColorTokens:
    canvas = ColorPalette.custom_bg_one
    sidebar = ColorPalette.custom_dark_one
    panel = ColorPalette.custom_dark_two
    card = ColorPalette.custom_dark_three
    raised = ColorPalette.custom_dark_four
    accent = ColorPalette.custom_context_color
    text_primary = ColorPalette.custom_text_foreground
    # 浮层永远取「当前主题里最亮的那一档表面」：深色主题用抬升层，
    # 浅色主题用卡片白，否则浅色菜单会比页面卡片更暗、看起来像凹陷。
    overlay = raised if _luminance(canvas) < 0.5 else card
    # 发丝线用正文色的低透明度混合，深浅主题都能得到「深色上是浅色高光、
    # 浅色上是灰色阴影」的分层效果，且不会出现纯黑描边的脏边。
    return ColorTokens(
        surface_app=canvas,
        surface_canvas=canvas,
        surface_sunken=sidebar,
        surface_sidebar=sidebar,
        surface_panel=panel,
        surface_card=card,
        surface_raised=raised,
        surface_overlay=overlay,
        surface_interactive=ColorPalette.custom_bg_one,
        surface_interactive_hover=ColorPalette.custom_bg_two,
        surface_interactive_pressed=ColorPalette.custom_bg_three,
        text_title=ColorPalette.custom_text_title,
        text_primary=text_primary,
        text_muted=ColorPalette.custom_text_description,
        text_active=ColorPalette.custom_text_active,
        text_on_accent=readable_on(accent),
        accent=accent,
        accent_hover=ColorPalette.custom_context_hover,
        accent_pressed=ColorPalette.custom_context_pressed,
        accent_soft=_mix(card, accent, 0.18),
        accent_wash=_mix(card, accent, 0.08),
        border_hairline=_mix(canvas, text_primary, 0.10),
        border_soft=_mix(canvas, text_primary, 0.16),
        border_strong=_mix(canvas, text_primary, 0.28),
        border_context=accent,
        border_transparent=ColorPalette.custom_transparent,
        state_active=ColorPalette.custom_green,
        state_success=ColorPalette.custom_green,
        state_warning=ColorPalette.custom_yellow,
        state_danger=ColorPalette.custom_red,
    )


def get_design_tokens() -> DesignTokens:
    from ..config import AppSettings

    text_size = AppSettings.text_size
    return DesignTokens(
        colors=_color_tokens(),
        typography=TypographyTokens(
            family=AppSettings.family,
            size_display=AppSettings.title_size + 2,
            size_title=AppSettings.title_size,
            size_subtitle=AppSettings.subtitle_size,
            size_text=text_size,
            size_caption=max(8, text_size - 2),
            weight_tooltip=AppSettings.tooltip_font,
            size_label=9,
            weight_label=600,
            tracking_title=0.3,
        ),
        spacing=SpacingTokens(
            padding_sm=8,
            padding_md=AppSettings.custom_padding,
            menu_item_left=16,
            menu_item_vertical=6,
            menu_indicator_right=4,
            menu_indicator_offset=2,
            label_padding_bottom=2,
        ),
        radius=RadiusTokens(
            window=AppSettings.window_border_radius,
            control=AppSettings.button.radius,
            tooltip=AppSettings.tooltip_border_radius,
        ),
        border=BorderTokens(
            width=AppSettings.window_border_size,
            accent_width=AppSettings.custom_border,
        ),
        size=SizeTokens(
            icon=AppSettings.icon_size,
            control_height=32,
            drop_down_width=24,
            card_inset=8,
            accent_bar=3,
        ),
    )


__all__ = [
    "BorderTokens",
    "ColorTokens",
    "DesignTokens",
    "RadiusTokens",
    "SizeTokens",
    "SpacingTokens",
    "TypographyTokens",
    "get_design_tokens",
    "readable_on",
]
