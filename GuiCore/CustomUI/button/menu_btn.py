from qt_core import QIcon, QPixmap, QPushButton, QSize, Qt
from AppCore import PathFactory

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

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text: str | None = None,
        icon: QIcon | str | None = None,
        radius: int = 8,
        border_size: int = 2,
        colorpalette=None,
        is_transparent: bool = False,
    ):
        super().__init__()
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
        # )

        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

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
