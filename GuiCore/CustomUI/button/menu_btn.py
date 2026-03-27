"""模块说明。"""

from AppCore import PathFactory
from qt_core import QIcon, QPixmap, QPushButton, QSize, Qt

style = """
/* 主控件样式 */
QPushButton {{
    border: {_border_size}px solid {_bg_color};
    border-radius: {_radius}px;
    background-color: {_bg_color};
    color: {_text_color};
    padding-left: 10px
}}
QPushButton:hover {{
    background-color: {_press_color};
}}
QPushButton:pressed {{
    background-color: {_press_color};
}}
QPushButton::menu-indicator {{
    image: url(resource/CustomUI/images/svg_icons/icon_arrow_right.svg);
    width: 16px;
    height: 16px;
    padding-right: 4px;
    subcontrol-position: right;
}}
QPushButton::menu-indicator:pressed, QPushButton::menu-indicator:open {{
    image: url(resource/CustomUI/images/svg_icons/icon_arrow_down.svg);
    width: 16px;
    height: 16px;
    position: relative;
    top: 2px; left: 2px; /* shift the arrow by 2 px */
}}
"""


class CMenuButton(QPushButton):
    """带菜单指示器的按钮组件。"""

    def __init__(
        self,
        size: QSize | None = None,
        text: str | None = None,
        icon: QIcon | str | None = None,
        radius: int = 8,
        border_size: int = 2,
        colorpalette: object | None = None,
        *,
        is_transparent: bool = False,
    ) -> None:
        """初始化菜单按钮。

        参数:
        - size: 按钮基础尺寸。
        - text: 按钮文本。
        - icon: 图标对象或路径。
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - colorpalette: 颜色对象。
        - is_transparent: 透明样式开关。

        返回:
        - None
        """
        _ = is_transparent
        super().__init__()
        if size is None:
            size = QSize(64, 32)
        self.setObjectName("CMenuButton_PushButton")
        if text is not None:
            self.setText(text)
        if icon is not None:
            if isinstance(icon, str):
                pixmap = QPixmap(icon)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                icon = QIcon(rounded_pixmap)
                icon_size = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
                self.setIconSize(icon_size)
            self.setIcon(icon)
        if size is not None:
            temp_size = QSize(int(size.width() + 36), size.height())
            self.setFixedSize(temp_size)
        self.radius = radius
        self.border_size = border_size
        self.color = colorpalette
        # 设置样式
        # self.set_stylesheet(
        #     radius,
        #     border_size,
        #     bg,
        #     colorpalette.custom_text_foreground,
        #     colorpalette.custom_bg_one,
        #     colorpalette.custom_bg_three,

        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

    def set_stylesheet(
        self,
        radius: int,
        border_size: int,
        bg_color: str,
        text_color: str,
        hover_color: str,
        press_active: str,
    ) -> None:
        """设置菜单按钮样式表。

        参数:
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - bg_color: 背景色。
        - text_color: 文本色。
        - hover_color: 悬停色。
        - press_active: 按下色。

        返回:
        - None
        """
        style_format = style.format(
            _radius=radius,
            _border_size=border_size,
            _bg_color=bg_color,
            _text_color=text_color,
            _hover_color=hover_color,
            _press_color=press_active,
        )
        self.setStyleSheet(style_format)
