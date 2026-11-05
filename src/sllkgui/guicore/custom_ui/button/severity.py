"""按钮语义色：Windows Fluent Design 令牌映射。

设计约定：

1. 颜色不写死为 Tailwind/PrimeVue 色阶，全部从当前主题的 ``ColorPalette`` 解析，
   四套主题（default / bright / eye / dracula）自动得到一致的语义层级；
2. ``primary`` / ``info`` / ``help`` 使用主题强调色，success / warn / danger 使用
   主题的语义色（``custom_green`` / ``custom_yellow`` / ``custom_red``）；
3. neutral（secondary / plain）使用 Fluent 控件层色：常态为面板层，悬停/按下按
   正文色做 6% / 10% 的轻微叠加，避免 Aura 的大面积灰阶跳变；
4. outlined / text 变体不铺实色，只用语义色描边 + 低透明度底色，符合 Fluent
   的“轻量控件”层级。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtGui import QColor

from sllkgui.appcore import ColorPalette


class Severity(StrEnum):
    """按钮语义色。"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    INFO = "info"
    WARN = "warn"
    HELP = "help"
    DANGER = "danger"
    CONTRAST = "contrast"


class Variant(StrEnum):
    """按钮变体。"""

    SOLID = "solid"
    OUTLINED = "outlined"
    TEXT = "text"
    LINK = "link"


@dataclass(frozen=True)
class ButtonColors:
    """一个按钮在三种状态下的完整配色。"""

    background: QColor
    border: QColor
    text: QColor
    hover_background: QColor
    hover_border: QColor
    hover_text: QColor
    active_background: QColor
    active_border: QColor
    active_text: QColor


_TRANSPARENT = QColor(0, 0, 0, 0)
_WHITE = QColor("#ffffff")


def is_dark_theme() -> bool:
    """按内容区背景亮度判断当前主题深浅（四套主题通用）。"""
    return QColor(ColorPalette.custom_bg_one).lightness() < 128


def _alpha(color: QColor, alpha: int) -> QColor:
    result = QColor(color)
    result.setAlpha(max(0, min(255, int(alpha))))
    return result


def _mix(color: QColor, target: QColor, ratio: float) -> QColor:
    """把 ``color`` 按 ``ratio`` 混向 ``target``（0=原色，1=目标色）。"""
    return QColor(
        round(color.red() + (target.red() - color.red()) * ratio),
        round(color.green() + (target.green() - color.green()) * ratio),
        round(color.blue() + (target.blue() - color.blue()) * ratio),
        color.alpha(),
    )


def _luminance(color: QColor) -> float:
    """WCAG 相对亮度（0=黑，1=白）。"""

    def channel(value: int) -> float:
        ratio = value / 255.0
        return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def _contrast_ratio(first: QColor, second: QColor) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _contrast_text(color: QColor) -> QColor:
    """在给定底色上挑一个可读的文字色（白或近黑）。"""
    black = QColor("#0b0b0b")
    return black if _contrast_ratio(black, color) >= _contrast_ratio(_WHITE, color) else _WHITE


def _semantic_base(severity: Severity) -> QColor:
    """语义色的主题基色；未单独定义的 severity 统一回落到强调色。"""
    if severity is Severity.SUCCESS:
        return QColor(ColorPalette.custom_green)
    if severity is Severity.WARN:
        return QColor(ColorPalette.custom_yellow)
    if severity is Severity.DANGER:
        return QColor(ColorPalette.custom_red)
    return QColor(ColorPalette.custom_context_color)


def _neutral(dark: bool) -> tuple[QColor, QColor, QColor, QColor]:
    """中性控件的 (常态底色, 悬停底色, 按下底色, 描边)。

    Fluent 标准按钮的常态底色比卡片略亮/略深一档，保证叠在卡片上仍可辨认；
    悬停/按下再按正文色做 6% / 10% 的轻微叠加。
    """
    rest = QColor(ColorPalette.custom_dark_four if dark else ColorPalette.custom_dark_two)
    target = _WHITE if dark else QColor(ColorPalette.custom_text_foreground)
    hover = _mix(rest, target, 0.06)
    active = _mix(rest, target, 0.10)
    border = _mix(rest, target, 0.26)
    return rest, hover, active, border


def _solid(
    background: QColor,
    hover: QColor,
    active: QColor,
    text: QColor,
    border: QColor | None = None,
) -> ButtonColors:
    edge = background if border is None else border
    return ButtonColors(
        background=background,
        border=edge,
        text=text,
        hover_background=hover,
        hover_border=edge,
        hover_text=text,
        active_background=active,
        active_border=edge,
        active_text=text,
    )


def _tinted(text: QColor, border: QColor, hover: QColor, active: QColor) -> ButtonColors:
    """透明底按钮：文字与描边稳定，仅底色随状态变化。"""
    return ButtonColors(
        background=_TRANSPARENT,
        border=border,
        text=text,
        hover_background=hover,
        hover_border=border,
        hover_text=text,
        active_background=active,
        active_border=border,
        active_text=text,
    )


def disabled_colors(variant: str | Variant = Variant.SOLID, plain: bool = False) -> ButtonColors:
    """Fluent 禁用态：中性底色 + 弱化文字，不再把语义色整体降透明度。"""
    variant = Variant(variant)
    rest, _hover, _active, border = _neutral(is_dark_theme())
    text = QColor(ColorPalette.custom_text_description)
    if variant in (Variant.TEXT, Variant.LINK):
        return _tinted(text, _TRANSPARENT, _TRANSPARENT, _TRANSPARENT)
    if variant is Variant.OUTLINED:
        return _tinted(text, border, _TRANSPARENT, _TRANSPARENT)
    return _solid(rest, rest, rest, text, border=border)


def colors_for(severity: str | Severity, variant: str | Variant, plain: bool = False) -> ButtonColors:
    """解析一个按钮的配色（Fluent 语义层级）。"""
    severity = normalize_severity(severity)
    variant = Variant(variant)
    dark = is_dark_theme()
    rest, hover, active, border = _neutral(dark)

    if plain:
        color = QColor(ColorPalette.custom_text_foreground)
        return _tinted(color, _TRANSPARENT, hover, active)

    if severity is Severity.SECONDARY:
        if variant is Variant.SOLID:
            return _solid(rest, hover, active, QColor(ColorPalette.custom_text_foreground), border=border)
        color = QColor(ColorPalette.custom_text_foreground)
        return _tinted(
            color,
            border if variant is Variant.OUTLINED else _TRANSPARENT,
            hover,
            active,
        )

    if severity is Severity.CONTRAST:
        if variant is Variant.SOLID:
            base = QColor("#ffffff") if dark else QColor(ColorPalette.custom_text_title)
            return _solid(base, _mix(base, rest, 0.08), _mix(base, rest, 0.14), _contrast_text(base))
        color = _WHITE if dark else QColor(ColorPalette.custom_text_title)
        return _tinted(
            color,
            color if variant is Variant.OUTLINED else _TRANSPARENT,
            hover,
            active,
        )

    base = _semantic_base(severity)
    text = base
    hover_tint = _alpha(base, 22 if not dark else 18)
    active_tint = _alpha(base, 38 if not dark else 30)

    if variant is Variant.SOLID:
        toward = _WHITE if dark else QColor("#000000")
        return _solid(
            base,
            _mix(base, toward, 0.08),
            _mix(base, toward, 0.16),
            _contrast_text(base),
        )
    if variant is Variant.LINK:
        return _tinted(text, _TRANSPARENT, _TRANSPARENT, _TRANSPARENT)
    return _tinted(
        text,
        _alpha(base, 200) if variant is Variant.OUTLINED else _TRANSPARENT,
        hover_tint,
        active_tint,
    )


#: 常用别名（Message / Toast 用 info/success/warn/error）
_ALIASES = {
    "error": Severity.DANGER,
    "warning": Severity.WARN,
}


def normalize_severity(value: str | Severity) -> Severity:
    """把 ``error`` / ``warning`` 等别名归一为 :class:`Severity`。"""
    if isinstance(value, Severity):
        return value
    key = str(value).strip().lower()
    return _ALIASES.get(key) or Severity(key)


def severity_color(severity: str | Severity) -> QColor:
    """语义色基色（实心标签/徽标底色）。"""
    severity = normalize_severity(severity)
    if severity is Severity.PRIMARY or severity is Severity.INFO or severity is Severity.HELP:
        return QColor(ColorPalette.custom_context_color)
    if severity is Severity.SECONDARY:
        return QColor(ColorPalette.custom_dark_three)
    if severity is Severity.CONTRAST:
        return _WHITE if is_dark_theme() else QColor(ColorPalette.custom_text_title)
    return _semantic_base(severity)


def contrast_text(color: QColor) -> QColor:
    """给定底色上可读的文字色（白或近黑）。"""
    return _contrast_text(QColor(color))


__all__ = [
    "ButtonColors",
    "Severity",
    "Variant",
    "colors_for",
    "contrast_text",
    "disabled_colors",
    "is_dark_theme",
    "normalize_severity",
    "severity_color",
]
