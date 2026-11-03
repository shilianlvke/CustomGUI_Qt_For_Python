"""按钮配色：对齐 PrimeVue Aura 主题的 severity × variant 色板。

设计约定：

1. 颜色不写进 QSS——按钮自绘，每次重绘按当前主题实时解析，主题切换自动生效；
2. ``primary`` 复用 ``ColorPalette`` 的 context 三态，与选中态/链接保持一致；
3. 其余 severity 严格按 Aura 的语义色阶取色（success=green、info=sky、warn=orange、
   help=purple、danger=red），深浅两套只是**取不同档位**，色相不变：
   solid 取 500/600/700（深色主题 400/300/200），outlined 描边取 200（深色 700），
   text/outlined 的 hover/active 底色取 50/100（深色按 Aura 的
   ``color-mix(..., transparent 96%/84%)`` 折成 4%/16% 透明叠加）；
4. 中性色（secondary / contrast / plain）取 Aura 的 surface 色阶：浅色主题 slate、
   深色主题 zinc，与 Aura 的 light/dark 色板一一对应。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtGui import QColor

from customgui.appcore import ColorPalette


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

#: Aura 全部语义色都取自这份 Tailwind 标尺，索引 0=50 … 10=950
_STEP = {50: 0, 100: 1, 200: 2, 300: 3, 400: 4, 500: 5, 600: 6, 700: 7, 800: 8, 900: 9, 950: 10}

_GREEN = (
    "#f0fdf4",
    "#dcfce7",
    "#bbf7d0",
    "#86efac",
    "#4ade80",
    "#22c55e",
    "#16a34a",
    "#15803d",
    "#166534",
    "#14532d",
    "#052e16",
)
_SKY = (
    "#f0f9ff",
    "#e0f2fe",
    "#bae6fd",
    "#7dd3fc",
    "#38bdf8",
    "#0ea5e9",
    "#0284c7",
    "#0369a1",
    "#075985",
    "#0c4a6e",
    "#082f49",
)
_ORANGE = (
    "#fff7ed",
    "#ffedd5",
    "#fed7aa",
    "#fdba74",
    "#fb923c",
    "#f97316",
    "#ea580c",
    "#c2410c",
    "#9a3412",
    "#7c2d12",
    "#431407",
)
_PURPLE = (
    "#faf5ff",
    "#f3e8ff",
    "#e9d5ff",
    "#d8b4fe",
    "#c084fc",
    "#a855f7",
    "#9333ea",
    "#7e22ce",
    "#6b21a8",
    "#581c87",
    "#3b0764",
)
_RED = (
    "#fef2f2",
    "#fee2e2",
    "#fecaca",
    "#fca5a5",
    "#f87171",
    "#ef4444",
    "#dc2626",
    "#b91c1c",
    "#991b1b",
    "#7f1d1d",
    "#450a0a",
)

#: 中性色阶：浅色主题 surface=slate，深色主题 surface=zinc（Aura 同款，同样从 50 档起）
_SLATE = (
    "#f8fafc",
    "#f1f5f9",
    "#e2e8f0",
    "#cbd5e1",
    "#94a3b8",
    "#64748b",
    "#475569",
    "#334155",
    "#1e293b",
    "#0f172a",
    "#020617",
)
_ZINC = (
    "#fafafa",
    "#f4f4f5",
    "#e4e4e7",
    "#d4d4d8",
    "#a1a1aa",
    "#71717a",
    "#52525b",
    "#3f3f46",
    "#27272a",
    "#18181b",
    "#09090b",
)

#: severity -> Aura 语义色阶
_HUES = {
    Severity.SUCCESS: _GREEN,
    Severity.INFO: _SKY,
    Severity.WARN: _ORANGE,
    Severity.HELP: _PURPLE,
    Severity.DANGER: _RED,
}


def is_dark_theme() -> bool:
    """按内容区背景亮度判断当前主题深浅（四套主题通用，无需新增配置）。"""
    return QColor(ColorPalette.custom_bg_one).lightness() < 128


def _step(scale: tuple[str, ...], step: int) -> QColor:
    return QColor(scale[_STEP[step]])


def _alpha(color: QColor, alpha: int) -> QColor:
    result = QColor(color)
    result.setAlpha(alpha)
    return result


def _mix(color: QColor, target: QColor, ratio: float) -> QColor:
    """把 ``color`` 按 ``ratio`` 混向 ``target``（0=原色，1=目标色）。"""
    return QColor(
        round(color.red() + (target.red() - color.red()) * ratio),
        round(color.green() + (target.green() - color.green()) * ratio),
        round(color.blue() + (target.blue() - color.blue()) * ratio),
        color.alpha(),
    )


def _soften(color: QColor, dark: bool) -> QColor:
    """primary 的描边色：浅色主题向白靠（≈200 档），深色主题向黑靠（≈700 档）。"""
    return _mix(color, QColor("#000000"), 0.55) if dark else _mix(color, QColor("#ffffff"), 0.78)


def _wash(color: QColor, dark: bool, strong: bool) -> QColor:
    """hover/active 底色：浅色主题向白大量稀释（≈50/100 档），深色主题按 4%/16% 叠加。"""
    if dark:
        return _alpha(color, 41 if strong else 10)
    return _mix(color, QColor("#ffffff"), 0.84 if strong else 0.92)


def _luminance(color: QColor) -> float:
    """WCAG 相对亮度（0=黑，1=白）。"""

    def channel(value: int) -> float:
        ratio = value / 255.0
        return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def _contrast_text(color: QColor) -> QColor:
    """在给定底色上挑一个可读的文字色。

    Aura 的 ``primary.contrast.color`` 对 500 档主色一律取白字，只有真正的浅色
    （黄、白一类）才翻成近黑——用相对亮度卡在 0.5 比看 HSL 亮度更接近这个行为。
    """
    return QColor("#09090b") if _luminance(color) > 0.5 else QColor("#ffffff")


def _solid(
    background: QColor,
    hover_background: QColor,
    active_background: QColor,
    text: QColor,
    hover_text: QColor | None = None,
    active_text: QColor | None = None,
) -> ButtonColors:
    """实心按钮：描边跟随底色（Aura 的 border 恒等于 background）。"""
    return ButtonColors(
        background=background,
        border=background,
        text=text,
        hover_background=hover_background,
        hover_border=hover_background,
        hover_text=hover_text or text,
        active_background=active_background,
        active_border=active_background,
        active_text=active_text or text,
    )


def _tinted(
    text: QColor,
    border: QColor,
    hover_background: QColor,
    active_background: QColor,
) -> ButtonColors:
    """透明底按钮（outlined / text）：文字色与描边稳定，只有底色随状态变化。"""
    return ButtonColors(
        background=_TRANSPARENT,
        border=border,
        text=text,
        hover_background=hover_background,
        hover_border=border,
        hover_text=text,
        active_background=active_background,
        active_border=border,
        active_text=text,
    )


def _plain_colors(dark: bool, variant: Variant) -> ButtonColors:
    """plain（中性）按钮：忽略 severity，走 surface 色阶。"""
    surface = _ZINC if dark else _SLATE
    if variant is Variant.SOLID:
        return _solid(
            _step(surface, 800) if dark else _step(surface, 100),
            _step(surface, 700) if dark else _step(surface, 200),
            _step(surface, 600) if dark else _step(surface, 300),
            _step(surface, 300) if dark else _step(surface, 700),
        )
    color = QColor("#ffffff") if dark else _step(surface, 700)
    border = _step(surface, 600) if dark else _step(surface, 200)
    hover_background = _step(surface, 800) if dark else _step(surface, 50)
    active_background = _step(surface, 700) if dark else _step(surface, 100)
    return _tinted(
        color,
        border if variant is Variant.OUTLINED else _TRANSPARENT,
        hover_background,
        active_background,
    )


def colors_for(severity: str | Severity, variant: str | Variant, plain: bool = False) -> ButtonColors:
    """解析一个按钮的配色。

    Args:
        severity: 语义色，见 :class:`Severity`。
        variant: 变体，见 :class:`Variant`。
        plain: 中性按钮（Sakai 的 ``plain``），忽略 severity 走灰阶。
    """
    severity = normalize_severity(severity)
    variant = Variant(variant)
    dark = is_dark_theme()
    surface = _ZINC if dark else _SLATE

    if plain:
        return _plain_colors(dark, variant)

    if severity is Severity.PRIMARY:
        base = QColor(ColorPalette.custom_context_color)
        hover = QColor(ColorPalette.custom_context_hover)
        active = QColor(ColorPalette.custom_context_pressed)
        text = _contrast_text(base)
        if variant is Variant.SOLID:
            return _solid(base, hover, active, text)
        if variant is Variant.LINK:
            return _tinted(base, _TRANSPARENT, _TRANSPARENT, _TRANSPARENT)
        return _tinted(
            base,
            _soften(base, dark) if variant is Variant.OUTLINED else _TRANSPARENT,
            _wash(base, dark, strong=False),
            _wash(base, dark, strong=True),
        )

    if severity is Severity.SECONDARY:
        if variant is Variant.SOLID:
            # Aura 的 secondary 文字色在 hover/active 会逐级加深
            return _solid(
                _step(surface, 800) if dark else _step(surface, 100),
                _step(surface, 700) if dark else _step(surface, 200),
                _step(surface, 600) if dark else _step(surface, 300),
                _step(surface, 300) if dark else _step(surface, 600),
                _step(surface, 200) if dark else _step(surface, 700),
                _step(surface, 100) if dark else _step(surface, 800),
            )
        color = _step(surface, 400) if dark else _step(surface, 500)
        border = _step(surface, 700) if dark else _step(surface, 200)
        if variant is Variant.TEXT:
            # text 变体的深色主题用实心 surface 底色（不是半透明白）
            hover_background = _step(surface, 800) if dark else _step(surface, 50)
            active_background = _step(surface, 700) if dark else _step(surface, 100)
        else:
            hover_background = QColor(255, 255, 255, 10) if dark else _step(surface, 50)
            active_background = QColor(255, 255, 255, 41) if dark else _step(surface, 100)
        return _tinted(
            color,
            border if variant is Variant.OUTLINED else _TRANSPARENT,
            hover_background,
            active_background,
        )

    if severity is Severity.CONTRAST:
        if variant is Variant.SOLID:
            if dark:
                return _solid(
                    QColor("#ffffff"),
                    _step(_ZINC, 100),
                    _step(_ZINC, 200),
                    _step(_ZINC, 950),
                )
            return _solid(
                _step(_SLATE, 950),
                _step(_SLATE, 900),
                _step(_SLATE, 800),
                QColor("#ffffff"),
            )
        color = QColor("#ffffff") if dark else _step(_SLATE, 950)
        border = _step(_ZINC, 500) if dark else _step(_SLATE, 700)
        hover_background = _step(surface, 800) if dark else _step(surface, 50)
        active_background = _step(surface, 700) if dark else _step(surface, 100)
        return _tinted(
            color,
            border if variant is Variant.OUTLINED else _TRANSPARENT,
            hover_background,
            active_background,
        )

    scale = _HUES[severity]
    if variant is Variant.SOLID:
        if dark:
            return _solid(
                _step(scale, 400),
                _step(scale, 300),
                _step(scale, 200),
                _step(scale, 950),
            )
        return _solid(
            _step(scale, 500),
            _step(scale, 600),
            _step(scale, 700),
            QColor("#ffffff"),
        )

    # outlined / text / link：文字用 500（深色 400），底色用 50/100（深色 4%/16%）
    color = _step(scale, 400) if dark else _step(scale, 500)
    if variant is Variant.LINK:
        return _tinted(color, _TRANSPARENT, _TRANSPARENT, _TRANSPARENT)
    if dark:
        hover_background = _alpha(color, 10)
        active_background = _alpha(color, 41)
        border = _step(scale, 700)
    else:
        hover_background = _step(scale, 50)
        active_background = _step(scale, 100)
        border = _step(scale, 200)
    return _tinted(
        color,
        border if variant is Variant.OUTLINED else _TRANSPARENT,
        hover_background,
        active_background,
    )


#: PrimeVue 常用别名（Message / Toast 用 info/success/warn/error）
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
    dark = is_dark_theme()
    if severity is Severity.PRIMARY:
        return QColor(ColorPalette.custom_context_color)
    if severity is Severity.SECONDARY:
        return _step(_ZINC if dark else _SLATE, 800 if dark else 100)
    if severity is Severity.CONTRAST:
        return QColor("#ffffff") if dark else _step(_SLATE, 950)
    return _step(_HUES[severity], 400 if dark else 500)


def contrast_text(color: QColor) -> QColor:
    """给定底色上可读的文字色（白或近黑）。"""
    return _contrast_text(QColor(color))


__all__ = [
    "ButtonColors",
    "Severity",
    "Variant",
    "colors_for",
    "contrast_text",
    "is_dark_theme",
    "normalize_severity",
    "severity_color",
]
