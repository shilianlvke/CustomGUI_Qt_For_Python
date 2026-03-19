from qt_core import QIcon, QPixmap, QPushButton, QSize, Qt, Signal
from AppCore import PathFactory, ColorPalette

style = """
/* 主控件样式 */
QPushButton {{
    border: {_border_size}px solid transparent;
    border-radius: {_radius}px;
    border-color: {_border_hover_color};
    background-color: {_bg_color};
    color: {_text_color};
}}
QPushButton:hover {{
    background-color: {_hover_color};
}}
QPushButton:pressed {{
    background-color: {_press_color};
}}
"""


class CStatusButton(QPushButton):

    statusChanged = Signal(int)

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text_negative: str | None = None,
        text_normal: str | None = None,
        text_positive: str | None = None,
        icon_negative: QIcon | str | None = None,
        icon_normal: QIcon | str | None = None,
        icon_positive: QIcon | str | None = None,
        radius: int = 8,
        border_size: int = 2,
        is_normal: bool = False,  # 三态开关
    ):
        super().__init__()
        self.status_list = [-1, 0, 1] if is_normal else [0, 1]
        self.status = self.status_list[0]
        self.radius = radius
        self.border_size = border_size
        self.color = ColorPalette

        if text_negative is not None:
            self.text_negative = text_negative
        if text_positive is not None:
            self.text_positive = text_positive
        if text_normal is not None:
            self.text_normal = text_normal
        if icon_negative is not None:
            if isinstance(icon_negative, str):
                pixmap = QPixmap(icon_negative)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                self.icon_negative = QIcon(rounded_pixmap)
                self.icon_size_negative = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
            elif isinstance(icon_negative, QIcon):
                self.icon_negative = icon_negative
        if icon_positive is not None:
            if isinstance(icon_positive, str):
                pixmap = QPixmap(icon_positive)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                self.icon_positive = QIcon(rounded_pixmap)
                self.icon_size_size = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
            elif isinstance(icon_positive, QIcon):
                self.icon_positive = icon_positive
        if icon_normal is not None:
            if isinstance(icon_normal, str):
                pixmap = QPixmap(icon_normal)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                self.icon_normal = QIcon(rounded_pixmap)
                self.icon_size_normal = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
            elif isinstance(icon_normal, QIcon):
                self.icon_normal = icon_normal
        if size is not None:
            self.setFixedSize(size)
        # 绘制
        self.text_change()
        self.icon_change()
        self.style_change()
        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

    def set_stylesheet(self, radius, border_size, bg_color, text_color, hover_color, press_active, border_hover_color):
        style_format = style.format(
            _radius=radius,
            _border_size=border_size,
            _bg_color=bg_color,
            _text_color=text_color,
            _hover_color=hover_color,
            _press_color=press_active,
            _border_hover_color=border_hover_color,
        )
        self.setStyleSheet(style_format)

    def text_change(self):
        if self.status == 1:
            if hasattr(self, "text_positive"):
                self.setText(self.text_positive)
            else:
                self.setText("")
        elif self.status == 0:
            if hasattr(self, "text_negative"):
                self.setText(self.text_negative)
            else:
                self.setText("")
        elif self.status == -1:
            if hasattr(self, "text_normal"):
                self.setText(self.text_normal)
            else:
                self.setText("")

    def icon_change(self):
        if self.status == 1:
            if hasattr(self, "icon_positive"):
                self.setIcon(self.icon_positive)
            if hasattr(self, "icon_size_positive"):
                self.setIconSize(self.icon_size_positive)
        elif self.status == 0:
            if hasattr(self, "icon_negative"):
                self.setIcon(self.icon_negative)
            if hasattr(self, "icon_size_negative"):
                self.setIconSize(self.icon_size_negative)
        elif self.status == -1:
            if hasattr(self, "icon_normal"):
                self.setIcon(self.icon_normal)
            if hasattr(self, "icon_size_normal"):
                self.setIconSize(self.icon_size_normal)

    def style_change(self):
        if self.status == 1:
            border_haver_color = self.color.custom_context_color
        elif self.status == 0:
            border_haver_color = "transparent"
        elif self.status == -1:
            border_haver_color = self.color.custom_bg_active_one
        self.set_stylesheet(
            self.radius,
            self.border_size,
            self.color.custom_bg_one,
            self.color.custom_text_foreground,
            self.color.custom_bg_two,
            self.color.custom_bg_three,
            border_haver_color,
        )

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.status = self.status_list[(self.status_list.index(self.status) + 1) % len(self.status_list)]
        self.statusChanged.emit(self.status)
        self.text_change()
        self.icon_change()
        self.style_change()
