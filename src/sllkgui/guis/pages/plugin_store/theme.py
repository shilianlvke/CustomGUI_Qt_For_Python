"""页面级样式：文本角色、行选中/悬停与通知条避让。

基座组件只提供结构与字号，颜色统一由令牌派生。插件管理页需要在
``CCard`` 内部表达「标题 / 次要文字 / 成功 / 警告 / 危险」五种文本角色，
以及列表行的悬停与选中底，因此在这里生成一条**只命中页面自有对象名**的
轻量样式表；主题切换时整表重建，不需要遍历控件逐个改色。
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from sllkgui.appcore import get_design_tokens

#: 页面自有样式表的对象/属性名，避免与全局 QSS 的组件规则冲突
ROLE_PROP = "sllkRole"
ROW_OBJECT = "CPlugin_Row"
ROW_BAR_OBJECT = "CPlugin_RowBar"
UPDATE_DOT_OBJECT = "CPlugin_UpdateDot"
BUSY_OBJECT = "CPlugin_Busy"
STAT_DIVIDER_OBJECT = "CPlugin_StatDivider"


def _rgba(value: str, alpha: float) -> str:
    """把令牌色转成 QSS 的 ``rgba()`` 写法（Qt 不认 ``#RRGGBBAA``）。"""
    color = QColor(value)
    if not color.isValid():
        return value
    channel = max(0, min(255, round(color.alpha() * max(0.0, min(1.0, alpha)))))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {channel})"


def repolish(widget: QWidget) -> None:
    """动态属性变化后强制重新解析样式（Qt 不会自动重绘属性选择器）。"""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def text_role(widget: QWidget, role: str) -> QWidget:
    """给标签挂上文本角色（``title`` / ``muted`` / ``body`` / 语义色）。"""
    if widget.property(ROLE_PROP) != role:
        widget.setProperty(ROLE_PROP, role)
        repolish(widget)
    return widget


def page_sheet() -> str:
    """当前主题下的页面样式表；主题切换后重新调用即可。"""
    colors = get_design_tokens().colors
    hover = _rgba(colors.text_primary, 0.09)
    selected = _rgba(colors.accent, 0.12)
    accent_wash = _rgba(colors.accent, 0.10)
    accent_border = _rgba(colors.accent, 0.55)
    hairline = _rgba(colors.text_primary, 0.10)
    return f"""
        QLabel[{ROLE_PROP}="title"] {{
            color: {colors.text_title};
            background: transparent;
        }}
        QLabel[{ROLE_PROP}="muted"] {{
            color: {colors.text_muted};
            background: transparent;
        }}
        QLabel[{ROLE_PROP}="body"] {{
            color: {colors.text_primary};
            background: transparent;
        }}
        QLabel[{ROLE_PROP}="success"] {{
            color: {colors.state_success};
            background: transparent;
        }}
        QLabel[{ROLE_PROP}="warning"] {{
            color: {colors.state_warning};
            background: transparent;
        }}
        QLabel[{ROLE_PROP}="danger"] {{
            color: {colors.state_danger};
            background: transparent;
        }}
        QLabel[{ROLE_PROP}="title"]:disabled,
        QLabel[{ROLE_PROP}="body"]:disabled {{
            color: {colors.text_muted};
        }}

        #{ROW_OBJECT} {{
            background: transparent;
            border-radius: 6px;
        }}
        #{ROW_OBJECT}[hover="true"] {{
            background: {hover};
        }}
        #{ROW_OBJECT}[selected="true"] {{
            background: {selected};
        }}
        #{ROW_BAR_OBJECT} {{
            background: {colors.accent};
            border-radius: 1px;
        }}
        #{UPDATE_DOT_OBJECT} {{
            background: {colors.accent};
            border-radius: 3px;
        }}
        #{BUSY_OBJECT} {{
            background: {accent_wash};
            border: 1px solid {accent_border};
            border-radius: 4px;
        }}
        #{BUSY_OBJECT} QLabel {{
            color: {colors.text_primary};
            background: transparent;
        }}
        #{STAT_DIVIDER_OBJECT} {{
            background: {hairline};
            border: 0px;
        }}
    """


__all__ = [
    "BUSY_OBJECT",
    "ROLE_PROP",
    "ROW_BAR_OBJECT",
    "ROW_OBJECT",
    "STAT_DIVIDER_OBJECT",
    "UPDATE_DOT_OBJECT",
    "page_sheet",
    "repolish",
    "text_role",
]
