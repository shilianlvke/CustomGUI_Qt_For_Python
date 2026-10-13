from qt_core import QMenu

from AppCore import get_theme_manager

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
    def __init__(
        self,
        parent=None,
        width: int = 64 + 36,
        radius: int = 8,
        border_size: int = 2,
        colorpalette=None,
        is_transparent: bool = False,
    ):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.radius = radius
        self.border_size = border_size
        self.color = colorpalette
        self._is_transparent = is_transparent
        # 设置样式（实时取色，主题切换自动刷新）
        self.update_style()
        get_theme_manager().subscribe(self.update_style)

    def update_style(self):
        """按当前调色板实时刷新样式。"""
        bg = "transparent" if self._is_transparent else self.color.custom_bg_one
        self.set_stylesheet(
            self.radius,
            self.border_size,
            bg,
            self.color.custom_text_foreground,
            self.color.custom_bg_two,
            self.color.custom_bg_three,
        )

    def set_stylesheet(
        self,
        radius,
        border_size,
        bg_color,
        text_color,
        hover_color,
        press_active,
    ):
        style_format = style.format(
            _radius=radius,
            _border_size=border_size,
            _bg_color=bg_color,
            _text_color=text_color,
            _hover_color=hover_color,
            _press_color=press_active,
        )
        self.setStyleSheet(style_format)
