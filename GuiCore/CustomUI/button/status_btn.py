"""模块说明。"""

from typing import override

from AppCore import ColorPalette, PathFactory
from qt_core import QIcon, QPixmap, QPushButton, QSize, Qt, Signal

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
    """状态切换按钮组件。

    职责:
    - 支持双态或三态状态循环。
    - 根据状态同步文本、图标与样式。
    """

    status_changed = Signal(int)

    def __init__(  # noqa: PLR0913
        self,
        size: QSize | None = None,
        text_negative: str | None = None,
        text_normal: str | None = None,
        text_positive: str | None = None,
        icon_negative: QIcon | str | None = None,
        icon_normal: QIcon | str | None = None,
        icon_positive: QIcon | str | None = None,
        radius: int = 8,
        border_size: int = 2,
        *,
        is_normal: bool = False,  # 三态开关
    ) -> None:
        """初始化状态按钮。

        参数:
        - size: 按钮尺寸。
        - text_negative: 负态文本。
        - text_normal: 中态文本。
        - text_positive: 正态文本。
        - icon_negative: 负态图标对象或路径。
        - icon_normal: 中态图标对象或路径。
        - icon_positive: 正态图标对象或路径。
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - is_normal: 是否启用三态模式。

        返回:
        - None
        """
        super().__init__()
        if size is None:
            size = QSize(64, 32)
        self.status_list = [-1, 0, 1] if is_normal else [0, 1]
        self.status = self.status_list[0]
        self.radius = radius
        self.border_size = border_size
        self.color = ColorPalette

        self._apply_optional_text("negative", text_negative)
        self._apply_optional_text("positive", text_positive)
        self._apply_optional_text("normal", text_normal)

        self._apply_optional_icon("negative", icon_negative, size)
        self._apply_optional_icon("positive", icon_positive, size)
        self._apply_optional_icon("normal", icon_normal, size)

        self.setFixedSize(size)
        # 绘制
        self.text_change()
        self.icon_change()
        self.style_change()
        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

    def _apply_optional_text(self, state_name: str, value: str | None) -> None:
        """按状态写入可选文本配置。"""
        if value is None:
            return
        setattr(self, f"text_{state_name}", value)

    def _apply_optional_icon(self, state_name: str, icon: QIcon | str | None, size: QSize) -> None:
        """按状态写入可选图标与尺寸配置。"""
        if icon is None:
            return
        if isinstance(icon, str):
            pixmap = QPixmap(icon)
            rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
            setattr(self, f"icon_{state_name}", QIcon(rounded_pixmap))
            setattr(self, f"icon_size_{state_name}", QSize(int(size.width() * 0.8), int(size.height() * 0.8)))
            return
        if isinstance(icon, QIcon):
            setattr(self, f"icon_{state_name}", icon)

    def set_stylesheet(  # noqa: PLR0913
        self,
        radius: int,
        border_size: int,
        bg_color: str,
        text_color: str,
        hover_color: str,
        press_active: str,
        border_hover_color: str,
    ) -> None:
        """设置按钮样式表。

        参数:
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - bg_color: 背景颜色。
        - text_color: 文本颜色。
        - hover_color: 悬停颜色。
        - press_active: 按下颜色。
        - border_hover_color: 边框颜色。

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
            _border_hover_color=border_hover_color,
        )
        self.setStyleSheet(style_format)

    def text_change(self) -> None:
        """根据当前状态更新按钮文本。"""
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

    def icon_change(self) -> None:
        """根据当前状态更新按钮图标。"""
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

    def style_change(self) -> None:
        """根据当前状态更新按钮样式。"""
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

    @override
    def mousePressEvent(self, event: object) -> None:
        """处理鼠标点击并推进状态机。

        参数:
        - event: 鼠标事件对象。

        返回:
        - None
        """
        super().mousePressEvent(event)
        self.status = self.status_list[(self.status_list.index(self.status) + 1) % len(self.status_list)]
        self.status_changed.emit(self.status)
        self.text_change()
        self.icon_change()
        self.style_change()
