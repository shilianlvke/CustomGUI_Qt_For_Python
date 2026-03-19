from qt_core import (
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
    Slot,
)
from AppCore import PathFactory, ColorPalette, get_design_tokens


class CLeftMenuButton(QPushButton):

    style_change = Slot("style_change")

    def __init__(
        self,
        app_parent,
        text,
        btn_id=None,
        tooltip_text="",
        margin=4,
        icon_path="icon_add_user",
        icon_active_menu="active_menu",
        is_active=False,
        is_active_tab=False,
        is_toggle_active=False,
        minimum_width=50,
        maximum_width=240,
        font_family=None,
    ):
        super().__init__()
        self.setText(text)
        self.setFont(font_family)
        self.setCursor(Qt.PointingHandCursor)
        self.setMaximumHeight(50)
        self.setMinimumHeight(50)
        self.setObjectName(btn_id)
        # APP PATH
        self._icon_path = PathFactory.set_svg_icon(icon_path)
        self._icon_active_menu = PathFactory.set_svg_icon(icon_active_menu)
        self._icon_enter = False
        # PROPERTIES
        self._margin = margin
        self._set_icon_color = ColorPalette.custom_icon_color  # Set icon color
        self._set_bg_color = ColorPalette.custom_dark_one  # Set BG color
        self._parent = app_parent
        self._is_active = is_active
        self._is_active_tab = is_active_tab
        self._is_toggle_active = is_toggle_active
        self._minimum_width = minimum_width
        self._maximum_width = maximum_width
        # TOOLTIP
        self._tooltip_text = tooltip_text
        self.tooltip = _ToolTip(app_parent, tooltip_text)
        self.tooltip.hide()

    # 绘制事件
    def paintEvent(self, event):
        # PAINTER
        p = QPainter()
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setFont(self.font())

        # RECTANGLES
        # rect = QRect(4, 5, self.width(), self.height() - 10)
        rect_inside = QRect(4, 5, self.width() - 8, self.height() - 10)
        rect_icon = QRect(0, 0, 50, self.height())
        rect_blue = QRect(4, 5, 20, self.height() - 10)
        rect_inside_active = QRect(7, 5, self.width(), self.height() - 10)
        rect_text = QRect(45, 0, self.width() - 50, self.height())

        if self._is_active:
            # DRAW BG BLUE
            p.setBrush(QColor(ColorPalette.custom_context_color))
            p.drawRoundedRect(rect_blue, 8, 8)

            # BG INSIDE
            p.setBrush(QColor(ColorPalette.custom_bg_one))
            p.drawRoundedRect(rect_inside_active, 8, 8)

            # DRAW ACTIVE
            icon_path = self._icon_active_menu
            self._set_icon_color = ColorPalette.custom_icon_active
            self.icon_active(p, icon_path, self.width())

            # DRAW TEXT
            p.setPen(QColor(ColorPalette.custom_text_active))
            p.drawText(rect_text, Qt.AlignVCenter, self.text())

            # DRAW ICONS
            self.icon_paint(p, self._icon_path, rect_icon, ColorPalette.custom_context_color)

        elif self._is_active_tab:
            # DRAW BG BLUE
            p.setBrush(QColor(ColorPalette.custom_dark_four))
            p.drawRoundedRect(rect_blue, 8, 8)

            # BG INSIDE
            p.setBrush(QColor(ColorPalette.custom_bg_one))
            p.drawRoundedRect(rect_inside_active, 8, 8)

            # DRAW ACTIVE
            icon_path = self._icon_active_menu
            self._set_icon_color = ColorPalette.custom_icon_active
            self.icon_active(p, icon_path, self.width())

            # DRAW TEXT
            p.setPen(QColor(ColorPalette.custom_text_active))
            p.drawText(rect_text, Qt.AlignVCenter, self.text())

            # DRAW ICONS
            self.icon_paint(p, self._icon_path, rect_icon, self._set_icon_color)

        # NORMAL BG
        else:
            if self._is_toggle_active:
                # BG INSIDE
                p.setBrush(QColor(ColorPalette.custom_dark_three))
                p.drawRoundedRect(rect_inside, 8, 8)

                # DRAW TEXT
                p.setPen(QColor(ColorPalette.custom_text_foreground))
                p.drawText(rect_text, Qt.AlignVCenter, self.text())

                self.icon_paint(p, self._icon_path, rect_icon, ColorPalette.custom_context_color)
            else:
                if not self._icon_enter:
                    self._set_icon_color = ColorPalette.custom_icon_color  # Set icon color
                    self._set_bg_color = ColorPalette.custom_dark_one  # Set BG color
                # BG INSIDE
                p.setBrush(QColor(self._set_bg_color))
                p.drawRoundedRect(rect_inside, 8, 8)

                # DRAW TEXT
                p.setPen(QColor(ColorPalette.custom_text_foreground))
                p.drawText(rect_text, Qt.AlignVCenter, self.text())

                # DRAW ICONS
                self.icon_paint(p, self._icon_path, rect_icon, self._set_icon_color)

        p.end()

    # 设置活跃的界面
    def set_active(self, is_active):
        self._is_active = is_active
        if not is_active:
            self._set_icon_color = ColorPalette.custom_icon_color
            self._set_bg_color = ColorPalette.custom_dark_one
        self.repaint()

    # 设置活跃的导航栏
    def set_active_tab(self, is_active):
        self._is_active_tab = is_active
        if not is_active:
            self._set_icon_color = ColorPalette.custom_icon_color
            self._set_bg_color = ColorPalette.custom_dark_one
        self.repaint()

    # 返回是否是活跃界面
    def is_active(self):
        return self._is_active

    # 返回是否是活跃导航
    def is_active_tab(self):
        return self._is_active_tab

    # 设置活动切换
    def set_active_toggle(self, is_active):
        self._is_toggle_active = is_active

    # 设置图标
    def set_icon(self, icon_path):
        self._icon_path = icon_path
        self.repaint()

    # 用颜色绘制图标
    def icon_paint(self, qp, image, rect, color):
        icon = QPixmap(image)
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(icon.rect(), color)
        qp.drawPixmap((rect.width() - icon.width()) / 2, (rect.height() - icon.height()) / 2, icon)
        painter.end()

    # 绘制活动图标/右侧
    def icon_active(self, qp, image, width):
        icon = QPixmap(image)
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(icon.rect(), ColorPalette.custom_bg_one)
        qp.drawPixmap(width - 5, 0, icon)
        painter.end()

    # 更改样式
    # 具有自定义样式的函数
    def change_style(self, event):
        if event == QEvent.Enter:
            if not self._is_active:
                self._set_icon_color = ColorPalette.custom_icon_hover
                self._set_bg_color = ColorPalette.custom_dark_three
        elif event == QEvent.Leave:
            if not self._is_active:
                self._set_icon_color = ColorPalette.custom_icon_color
                self._set_bg_color = ColorPalette.custom_dark_one
        elif event == QEvent.MouseButtonPress:
            if not self._is_active:
                self._set_icon_color = ColorPalette.custom_context_color
                self._set_bg_color = ColorPalette.custom_dark_four
        elif event == QEvent.MouseButtonRelease:
            if not self._is_active:
                self._set_icon_color = ColorPalette.custom_icon_hover
                self._set_bg_color = ColorPalette.custom_dark_three

    # 鼠标悬停
    # 当鼠标位于BTN上时触发的事件
    def enterEvent(self, event):
        self._icon_enter = True
        self.change_style(QEvent.Enter)
        if self.width() in range(self._minimum_width - 5, self._minimum_width + 5) and self._tooltip_text:
            self.move_tooltip()
            self.tooltip.show()

    # 鼠标离开
    # 鼠标离开BTN时触发的事件
    def leaveEvent(self, event):
        self._icon_enter = False
        self.change_style(QEvent.Leave)
        self.tooltip.hide()

    # 鼠标按下
    # 按下左键时触发的事件
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.tooltip.hide()
            self.clicked.emit()
            self.change_style(QEvent.MouseButtonPress)
            self.tooltip.update_style()

    # 鼠标释放
    # 松开鼠标按钮后触发的事件
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonRelease)
            self.released.emit()

    # 移动工具提示
    def move_tooltip(self):
        # 获取主窗口父窗口
        gp = self.mapToGlobal(QPoint(0, 0))

        # 设置小部件以获取位置
        # 返回小部件在应用程序中的绝对位置
        pos = self._parent.mapFromGlobal(gp)

        # 格式位置
        # 使用偏移调整工具提示位置
        pos_x = pos.x() + self.width() + 5
        pos_y = pos.y() + (self.width() - self.tooltip.height()) // 2

        # 为小部件设置位置
        # 移动工具提示位置
        self.tooltip.move(pos_x, pos_y)


# TOOLTIP
# ///////////////////////////////////////////////////////////////
class _ToolTip(QLabel):
    # TOOLTIP / LABEL StyleSheet

    def __init__(self, parent, tooltip):
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
        self.update_style()
        super().show()

    def update_style(self):
        tokens = get_design_tokens()
        self.style = f"""
            QLabel {{
                background-color: {tokens.colors.surface_sidebar};	
                color: {tokens.colors.text_primary};
                padding-left: {tokens.spacing.padding_md}px;
                padding-right: {tokens.spacing.padding_md}px;
                border-radius: {tokens.radius.tooltip}px;
                border: 0px solid {tokens.colors.border_transparent};
                border-left: {tokens.border.accent_width}px solid {tokens.colors.border_context};
                font: {tokens.typography.weight_tooltip} {tokens.typography.size_text}pt "{tokens.typography.family}";
            }}
        """
        self.setStyleSheet(self.style)
