from qt_core import (
    QBrush,
    QColor,
    QEvent,
    QGraphicsDropShadowEffect,
    QLabel,
    QPainter,
    QPixmap,
    QPoint,
    QPushButton,
    QRect,
    Qt,
)
from AppCore import ColorPalette, AppSettings


# PY TITLE BUTTON
# ///////////////////////////////////////////////////////////////
class CTitleButton(QPushButton):
    """标题栏控制按钮组件。"""

    def __init__(
        self,
        parent,
        app_parent=None,
        tooltip_text="",
        btn_id=None,
        width=30,
        height=30,
        radius=8,
        bg_color="#343b48",
        icon_color="#c3ccdf",
        icon_path="no_icon.svg",
        is_active=False,
    ):
        """初始化标题栏按钮。

        参数:
        - parent: 所属窗口。
        - app_parent: 应用父对象。
        - tooltip_text: 提示文本。
        - btn_id: 按钮对象名。
        - width: 按钮宽度。
        - height: 按钮高度。
        - radius: 圆角半径。
        - bg_color: 背景色。
        - icon_color: 图标色。
        - icon_path: 图标路径。
        - is_active: 初始激活状态。

        返回:
        - None
        """

        super().__init__()

        # SET DEFAULT PARAMETERS
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName(btn_id)
        self._icon_enter = False
        # PROPERTIES
        self._top_margin = self.height() + 6
        self._is_active = is_active
        # Set Parameters
        self._set_bg_color = bg_color
        self._set_icon_path = icon_path
        self._set_icon_color = icon_color
        self._set_border_radius = radius
        # Parent
        self._parent = parent

        # TOOLTIP
        self._tooltip_text = tooltip_text
        self._tooltip = _ToolTip(app_parent, tooltip_text)
        self._tooltip.hide()

    # SET ACTIVE MENU
    # ///////////////////////////////////////////////////////////////
    def set_active(self, is_active):
        """设置按钮激活状态。"""

        self._is_active = is_active
        self.repaint()

    # RETURN IF IS ACTIVE MENU
    # ///////////////////////////////////////////////////////////////
    def is_active(self):
        """返回按钮是否激活。"""

        return self._is_active

    # PAINT EVENT
    # painting the button and the icon
    # ///////////////////////////////////////////////////////////////
    def paintEvent(self, event):
        """绘制按钮背景与图标。"""

        # PAINTER
        paint = QPainter()
        paint.begin(self)
        paint.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_active:
            # BRUSH
            brush = QBrush(QColor(ColorPalette.custom_text_foreground))
        else:
            if not self._icon_enter:
                self._set_icon_color = ColorPalette.custom_icon_color  # Set icon color
                self._set_bg_color = ColorPalette.custom_dark_three  # Set BG color
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
    def change_style(self, event):
        """根据交互事件更新样式状态。"""

        if event == QEvent.Enter:
            self._set_bg_color = ColorPalette.custom_bg_three
            self._set_icon_color = ColorPalette.custom_icon_hover
        elif event == QEvent.Leave:
            self._set_bg_color = ColorPalette.custom_dark_three
            self._set_icon_color = ColorPalette.custom_icon_color
        elif event == QEvent.MouseButtonPress:
            self._set_bg_color = ColorPalette.custom_bg_one
            self._set_icon_color = ColorPalette.custom_icon_pressed
        elif event == QEvent.MouseButtonRelease:
            self._set_bg_color = ColorPalette.custom_bg_three
            self._set_icon_color = ColorPalette.custom_icon_hover

    # MOUSE OVER
    # Event triggered when the mouse is over the BTN
    # ///////////////////////////////////////////////////////////////
    def enterEvent(self, event):
        """处理鼠标进入并显示提示框。"""

        self._icon_enter = True
        self.change_style(QEvent.Enter)
        self.move_tooltip()
        self._tooltip.show()

    # MOUSE LEAVE
    # Event fired when the mouse leaves the BTN
    # ///////////////////////////////////////////////////////////////
    def leaveEvent(self, event):
        """处理鼠标离开并隐藏提示框。"""

        self._icon_enter = False
        self.change_style(QEvent.Leave)
        self.move_tooltip()
        self._tooltip.hide()

    # MOUSE PRESS
    # Event triggered when the left button is pressed
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event):
        """处理鼠标按下并发射点击信号。"""

        if event.button() == Qt.LeftButton:
            # SET FOCUS
            self.setFocus()
            # EMIT SIGNAL
            self.clicked.emit()
            self.change_style(QEvent.MouseButtonPress)
            self._tooltip.update_style()

    # MOUSE RELEASED
    # Event triggered after the mouse button is released
    # ///////////////////////////////////////////////////////////////
    def mouseReleaseEvent(self, event):
        """处理鼠标释放并发射释放信号。"""

        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonRelease)
            # EMIT SIGNAL
            self.released.emit()

    # DRAW ICON WITH COLORS
    # ///////////////////////////////////////////////////////////////
    def icon_paint(self, qp, image, rect):
        """按当前状态绘制图标颜色。"""

        icon = QPixmap(image)
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        if self._is_active:
            painter.fillRect(icon.rect(), ColorPalette.custom_icon_active)
        else:
            painter.fillRect(icon.rect(), self._set_icon_color)
        qp.drawPixmap((rect.width() - icon.width()) / 2, (rect.height() - icon.height()) / 2, icon)
        painter.end()

    # SET ICON
    # ///////////////////////////////////////////////////////////////
    def set_icon(self, icon_path):
        """设置按钮图标并刷新。"""

        self._set_icon_path = icon_path
        self.repaint()

    # MOVE TOOLTIP
    # ///////////////////////////////////////////////////////////////
    def move_tooltip(self):
        """计算并移动提示框位置。"""

        # GET MAIN WINDOW PARENT
        gp = self.mapToGlobal(QPoint(0, 0))

        # SET WIDGET TO GET POSTION
        # Return absolute position of widget inside app
        pos = self._parent.mapFromGlobal(gp)

        # FORMAT POSITION
        # Adjust tooltip position with offset
        pos_x = (pos.x() - self._tooltip.width()) + self.width() + 5
        pos_y = pos.y() + self._top_margin

        # SET POSITION TO WIDGET
        # Move tooltip position
        self._tooltip.move(pos_x, pos_y)


# TOOLTIP
# ///////////////////////////////////////////////////////////////
class _ToolTip(QLabel):
    """标题栏按钮提示框组件。"""

    # TOOLTIP / LABEL StyleSheet

    def __init__(self, parent, tooltip):
        """初始化提示框。"""

        QLabel.__init__(self)
        # LABEL SETUP
        self.setObjectName("label_tooltip")
        self.update_style()
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

    def show(self):
        """显示提示框前刷新样式。"""

        self.update_style()
        super().show()

    def update_style(self):
        """更新提示框样式文本。"""

        self.style = f"""
            QLabel {{
                background-color: {ColorPalette.custom_dark_one};	
                color: {ColorPalette.custom_text_foreground};
                padding-left: {AppSettings.custom_padding}px;
                padding-right: {AppSettings.custom_padding}px;
                border-radius: {AppSettings.tooltip_border_radius}px;
                border: 0px solid {ColorPalette.custom_transparent};
                border-top: {AppSettings.custom_border}px solid {ColorPalette.custom_context_color};
               font: {AppSettings.tooltip_font} {AppSettings.text_size}pt "{AppSettings.family}";
            }}
        """
        self.setStyleSheet(self.style)
