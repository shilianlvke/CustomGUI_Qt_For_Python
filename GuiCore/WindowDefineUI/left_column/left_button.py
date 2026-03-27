"""左侧栏按钮组件模块。"""

from AppCore import ColorPalette
from qt_core import (
    QBrush,
    QColor,
    QEvent,
    QGraphicsDropShadowEffect,
    QLabel,
    QPainter,
    QPixmap,
    QPushButton,
    QRect,
    Qt,
)


class PyLeftButton(QPushButton):
    """左侧栏图标按钮组件。

    职责:
    - 提供左侧栏按钮绘制、状态切换与图标着色。
    - 支持悬停、按压反馈与提示信息显示。
    """

    def __init__(
        self,
        app_parent: object = None,
        tooltip_text: str = "",
        btn_id: str | None = None,
        width: int = 30,
        height: int = 30,
        radius: int = 8,
        icon_path: str = "no_icon.svg",
        is_active: bool = False,
        font_family: str = "",
    ) -> None:
        """初始化左侧栏按钮。

        参数:
        - app_parent: 应用父对象。
        - tooltip_text: 提示文本。
        - btn_id: 按钮对象名。
        - width: 按钮宽度。
        - height: 按钮高度。
        - radius: 圆角半径。
        - icon_path: 图标路径。
        - is_active: 初始激活状态。
        - font_family: 提示字体。

        返回:
        - None
        """
        super().__init__()

        # SET DEFAULT PARAMETERS
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName(btn_id)

        # PROPERTIES
        self._bg_color = ColorPalette.custom_bg_three
        self._bg_color_hover = ColorPalette.custom_bg_two
        self._bg_color_pressed = ColorPalette.custom_bg_one
        self._icon_color = ColorPalette.custom_icon_color
        self._icon_color_hover = ColorPalette.custom_icon_hover
        self._icon_color_pressed = ColorPalette.custom_icon_pressed
        self._icon_color_active = ColorPalette.custom_icon_pressed
        self._context_color = ColorPalette.custom_context_color
        self._top_margin = self.height() + 6
        self._is_active = is_active
        # Set Parameters
        self._set_bg_color = ColorPalette.custom_bg_three
        self._set_icon_path = icon_path
        self._set_icon_color = ColorPalette.custom_icon_color
        self._set_border_radius = radius
        self._app_parent = app_parent

        # TOOLTIP
        self._tooltip_text = tooltip_text
        self._tooltip = _ToolTip(
            app_parent,
            tooltip_text,
            ColorPalette.custom_dark_one,
            ColorPalette.custom_context_color,
            ColorPalette.custom_text_foreground,
            font_family,
        )
        self._tooltip.hide()

    # SET ACTIVE MENU
    # ///////////////////////////////////////////////////////////////
    def set_active(self, is_active: bool) -> None:
        """设置按钮激活状态。"""
        self._is_active = is_active
        self.repaint()

    # RETURN IF IS ACTIVE MENU
    # ///////////////////////////////////////////////////////////////
    def is_active(self) -> bool:
        """返回按钮是否处于激活状态。"""
        return self._is_active

    # PAINT EVENT
    # painting the button and the icon
    # ///////////////////////////////////////////////////////////////
    def paintEvent(self, event: object) -> None:
        """绘制按钮背景与图标。

        参数:
        - event: 绘制事件对象。

        返回:
        - None
        """
        # PAINTER
        paint = QPainter()
        paint.begin(self)
        paint.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_active:
            # BRUSH
            brush = QBrush(QColor(self._bg_color_pressed))
        else:
            # BRUSH
            brush = QBrush(QColor(self._set_bg_color))

        # CREATE RECTANGLE
        rect = QRect(0, 0, self.width(), self.height())
        paint.setPen(Qt.NoPen)
        paint.setBrush(brush)
        paint.drawRoundedRect(rect, self._set_border_radius, self._set_border_radius)

        # DRAW ICONS
        self.icon_paint(paint, self._set_icon_path, rect)

        # END PAINTER
        paint.end()

    # CHANGE STYLES
    # Functions with custom styles
    # ///////////////////////////////////////////////////////////////
    def change_style(self, event: QEvent) -> None:
        """根据交互事件切换样式。

        参数:
        - event: 事件类型。

        返回:
        - None
        """
        if event == QEvent.Enter:
            self._set_bg_color = self._bg_color_hover
            self._set_icon_color = self._icon_color_hover
            self.repaint()
        elif event == QEvent.Leave:
            self._set_bg_color = self._bg_color
            self._set_icon_color = self._icon_color
            self.repaint()
        elif event == QEvent.MouseButtonPress:
            self._set_bg_color = self._bg_color_pressed
            self._set_icon_color = self._icon_color_pressed
            self.repaint()
        elif event == QEvent.MouseButtonRelease:
            self._set_bg_color = self._bg_color_hover
            self._set_icon_color = self._icon_color_hover
            self.repaint()

    # MOUSE OVER
    # Event triggered when the mouse is over the BTN
    # ///////////////////////////////////////////////////////////////
    def enterEvent(self, event: object) -> None:
        """处理鼠标进入事件。"""
        self.change_style(QEvent.Enter)

    # MOUSE LEAVE
    # Event fired when the mouse leaves the BTN
    # ///////////////////////////////////////////////////////////////
    def leaveEvent(self, event: object) -> None:
        """处理鼠标离开事件。"""
        self.change_style(QEvent.Leave)

    # MOUSE PRESS
    # Event triggered when the left button is pressed
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event: object) -> None:
        """处理鼠标按下事件并发射点击信号。"""
        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonPress)
            # SET FOCUS
            self.setFocus()
            # EMIT SIGNAL
            self.clicked.emit()

    # MOUSE RELEASED
    # Event triggered after the mouse button is released
    # ///////////////////////////////////////////////////////////////
    def mouseReleaseEvent(self, event: object) -> None:
        """处理鼠标释放事件并发射释放信号。"""
        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonRelease)
            # EMIT SIGNAL
            self.released.emit()

    # DRAW ICON WITH COLORS
    # ///////////////////////////////////////////////////////////////
    def icon_paint(self, qp: object, image: str, rect: QRect) -> None:
        """按当前状态绘制图标颜色。

        参数:
        - qp: 目标画笔。
        - image: 图标路径。
        - rect: 图标绘制区域。

        返回:
        - None
        """
        icon = QPixmap(image)
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        if self._is_active:
            painter.fillRect(icon.rect(), self._context_color)
        else:
            painter.fillRect(icon.rect(), self._set_icon_color)
        qp.drawPixmap((rect.width() - icon.width()) / 2, (rect.height() - icon.height()) / 2, icon)
        painter.end()

    # SET ICON
    # ///////////////////////////////////////////////////////////////
    def set_icon(self, icon_path: str) -> None:
        """设置按钮图标路径并刷新。"""
        self._set_icon_path = icon_path
        self.repaint()

    # MOVE TOOLTIP
    # ///////////////////////////////////////////////////////////////
    def move_tooltip(self) -> None:
        """计算并移动提示框位置。

        返回:
        - None
        """


# TOOLTIP
# ///////////////////////////////////////////////////////////////
class _ToolTip(QLabel):
    """左侧按钮提示框组件。"""

    # TOOLTIP / LABEL StyleSheet
    style_tooltip = """
    QLabel {{
        background-color: {_dark_one};
        color: {_text_foreground};
        padding-left: 10px;
        padding-right: 10px;
        border-radius: 17px;
        border: 0px solid transparent;
        border-right: 3px solid {_context_color};
        font: 800 9pt "{_family}";
    }}
    """

    def __init__(
        self,
        parent: object,
        tooltip: str,
        dark_one: str,
        context_color: str,
        text_foreground: str,
        family: str,
    ) -> None:
        """初始化提示框。

        参数:
        - parent: 父组件。
        - tooltip: 提示文本。
        - dark_one: 背景色。
        - context_color: 强调边框色。
        - text_foreground: 文本色。
        - family: 字体名。
        """
        QLabel.__init__(self)

        # LABEL SETUP
        style = self.style_tooltip.format(
            _dark_one=dark_one,
            _context_color=context_color,
            _text_foreground=text_foreground,
            _family=family,
        )
        self.setObjectName("label_tooltip")
        self.setStyleSheet(style)
        self.setMinimumHeight(34)
        self.setParent(parent)
        self.setText(tooltip)
        self.adjustSize()

        # SET DROP SHADOW
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(30)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(0)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow)
