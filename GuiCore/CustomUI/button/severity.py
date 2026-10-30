"""按钮配色：Aura 主题的 severity × variant 色板。

设计约定：

1. 颜色不写进 QSS——按钮自绘，每次重绘按当前主题实时解析，主题切换自动生效；
2. ``primary`` 复用 ``ColorPalette`` 的 context 三态，与选中态/链接保持一致；
3. 其余 severity 采用 PrimeVue Aura 的深/浅两套色阶，深浅由当前主题背景亮度判定；
4. outlined / text 的 hover、active 背景用主色的低透明度叠加，等效 Aura 的
   ``color-mix(..., transparent 96%/84%)``。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QColor

from AppCore import ColorPalette


class Severity(str, Enum):
    """按钮语义色。"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    INFO = "info"
    WARN = "warn"
    HELP = "help"
    DANGER = "danger"
    CONTRAST = "contrast"


class Variant(str, Enum):
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

#: severity -> (底色, hover, active, 文字色) —— 深色主题（Aura dark）
_DARK_SOLID = {
    "secondary": ("#27272a", "#3f3f46", "#52525b", "#d4d4d8"),
    "success": ("#4ade80", "#86efac", "#bbf7d0", "#052e16"),
    "info": ("#38bdf8", "#7dd3fc", "#bae6fd", "#082f49"),
    "warn": ("#fb923c", "#fdba74", "#fed7aa", "#431407"),
    "help": ("#c084fc", "#d8b4fe", "#e9d5ff", "#3b0764"),
    "danger": ("#f87171", "#fca5a5", "#fecaca", "#450a0a"),
    "contrast": ("#ffffff", "#f4f4f5", "#e4e4e7", "#09090b"),
}

#: 同上，浅色主题（Aura light）
_LIGHT_SOLID = {
    "secondary": ("#f1f5f9", "#e2e8f0", "#cbd5e1", "#475569"),
    "success": ("#22c55e", "#16a34a", "#15803d", "#ffffff"),
    "info": ("#0ea5e9", "#0284c7", "#0369a1", "#ffffff"),
    "warn": ("#f97316", "#ea580c", "#c2410c", "#ffffff"),
    "help": ("#a855f7", "#9333ea", "#7e22ce", "#ffffff"),
    "danger": ("#ef4444", "#dc2626", "#b91c1c", "#ffffff"),
    "contrast": ("#020617", "#0f172a", "#1e293b", "#ffffff"),
}

#: 中性（plain）按钮：跟随主题的正文色阶
_DARK_PLAIN = ("#a1a1aa", "#d4d4d8", "#e4e4e7", "#a1a1aa")
_LIGHT_PLAIN = ("#71717a", "#52525b", "#3f3f46", "#52525b")


def is_dark_theme() -> bool:
    """按内容区背景亮度判断当前主题深浅（四套主题通用，无需新增配置）。"""
    return QColor(ColorPalette.custom_bg_one).lightness() < 128


def _contrast_text(color: QColor) -> QColor:
    """在给定底色上挑一个可读的文字色。"""
    return QColor("#09090b") if color.lightness() > 150 else QColor("#ffffff")


def _with_alpha(color: QColor, alpha: int) -> QColor:
    result = QColor(color)
    result.setAlpha(alpha)
    return result


def _outline_border(color: QColor, dark: bool) -> QColor:
    """描边色：深色主题压暗一些、浅色主题提亮一些，贴近 Aura 的 700/200 色阶。"""
    return color.darker(135) if dark else color.lighter(160)


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

    if plain:
        base, hover, active, text = _DARK_PLAIN if dark else _LIGHT_PLAIN
        base, hover, active, text = QColor(base), QColor(hover), QColor(active), QColor(text)
    elif severity is Severity.PRIMARY:
        base = QColor(ColorPalette.custom_context_color)
        hover = QColor(ColorPalette.custom_context_hover)
        active = QColor(ColorPalette.custom_context_pressed)
        text = _contrast_text(base)
    else:
        table = _DARK_SOLID if dark else _LIGHT_SOLID
        base, hover, active, text = table[severity.value]
        base, hover, active, text = QColor(base), QColor(hover), QColor(active), QColor(text)

    if variant is Variant.SOLID:
        return ButtonColors(
            background=base,
            border=base,
            text=text,
            hover_background=hover,
            hover_border=hover,
            hover_text=text,
            active_background=active,
            active_border=active,
            active_text=text,
        )

    # outlined / text / link：透明底 + 主色文字；hover/active 用主色低透明度叠加
    text_color = base
    if severity is Severity.SECONDARY:
        # secondary 的实心底本身是深/浅面，直接拿来当文字会与背景糊在一起
        text_color = QColor("#d4d4d8") if dark else QColor("#475569")
    hover_background = _with_alpha(text_color, 26 if dark else 20)
    active_background = _with_alpha(text_color, 46 if dark else 36)
    if variant is Variant.OUTLINED:
        border = QColor("#52525b") if dark else QColor("#cbd5e1")
        if severity is not Severity.SECONDARY:
            border = _outline_border(base, dark)
    else:
        border = _TRANSPARENT
    hover_border = border.darker(115) if variant is Variant.OUTLINED else _TRANSPARENT

    if variant is Variant.LINK:
        # 链接变体不加底色，hover 靠下划线（由组件绘制）
        hover_background = _TRANSPARENT
        active_background = _TRANSPARENT

    return ButtonColors(
        background=_TRANSPARENT,
        border=border,
        text=text_color,
        hover_background=hover_background,
        hover_border=hover_border,
        hover_text=text_color,
        active_background=active_background,
        active_border=hover_border,
        active_text=text_color,
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
    if severity is Severity.PRIMARY:
        return QColor(ColorPalette.custom_context_color)
    table = _DARK_SOLID if is_dark_theme() else _LIGHT_SOLID
    return QColor(table[severity.value][0])


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
