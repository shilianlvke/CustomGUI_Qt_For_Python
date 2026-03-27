"""模块说明。"""

from qt_core import QMenu

style = """
QMenu {{
    border: {_border_size}px solid transparent;
    border-radius: {_radius}px;
    background-color: {_bg_color};
    color: {_text_color}
}}
QMenu::item {{
    padding-left: 20px;
    padding-top: 5px;
    padding-bottom: 5px;
    border: {_border_size}px solid transparent;
    border-radius: {_radius}px;
    background-color: transparent;
}}
QMenu::item:selected {{
    background-color: {_hover_color};
}}
QMenu::icon {{
    padding-left: 20px;
}}
"""


class CMenu(QMenu):
    """自定义菜单组件。"""

    def __init__(self, parent: object | None = None, **options: object) -> None:
        """初始化菜单组件。

        参数:
        - parent: 父组件。
        - width: 菜单宽度。
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - colorpalette: 颜色对象。
        - is_transparent: 是否使用透明背景。

        返回:
        - None
        """
        width = int(options.get("width", 64 + 36))
        radius = int(options.get("radius", 8))
        border_size = int(options.get("border_size", 2))
        colorpalette = options.get("colorpalette")
        is_transparent = bool(options.get("is_transparent", False))
        super().__init__(parent)
        self.setFixedWidth(width)
        self.radius = radius
        self.border_size = border_size
        self.color = colorpalette
        bg = "transparent" if is_transparent else colorpalette.custom_bg_one
        # 设置样式
        self.set_stylesheet(
            {
                "radius": radius,
                "border_size": border_size,
                "bg_color": bg,
                "text_color": colorpalette.custom_text_foreground,
                "hover_color": colorpalette.custom_bg_two,
                "press_active": colorpalette.custom_bg_three,
            }
        )

    def set_stylesheet(self, style_tokens: dict[str, object]) -> None:
        """设置菜单样式表。

        参数:
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - bg_color: 背景颜色。
        - text_color: 文本颜色。
        - hover_color: 悬停颜色。
        - press_active: 按下颜色。

        返回:
        - None
        """
        style_format = style.format(
            _radius=style_tokens["radius"],
            _border_size=style_tokens["border_size"],
            _bg_color=style_tokens["bg_color"],
            _text_color=style_tokens["text_color"],
            _hover_color=style_tokens["hover_color"],
            _press_color=style_tokens["press_active"],
        )
        self.setStyleSheet(style_format)
