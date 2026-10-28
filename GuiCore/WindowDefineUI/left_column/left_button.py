from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QPushButton
from AppCore import ColorPalette

from ...CustomUI import CToolTip


class PyLeftButton(QPushButton):
    def __init__(
        self,
        # parent,
        app_parent=None,
        tooltip_text="",
        btn_id=None,
        width=30,
        height=30,
        radius=8,
        icon_path="no_icon.svg",
        is_active=False,
        font_family="",
    ):
        super().__init__()

        # SET DEFAULT PARAMETERS
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName(btn_id)

        # PROPERTIES（颜色实时读取 ColorPalette，主题切换自动生效）
        self._state = "normal"  # normal / hover / pressed
        self._top_margin = self.height() + 6
        self._is_active = is_active
        self._set_icon_path = icon_path
        self._set_border_radius = radius
        # Parent
        # self._parent = parent
        self._app_parent = app_parent

        # TOOLTIP
        self._tooltip_text = tooltip_text
        self._tooltip = CToolTip(app_parent, tooltip_text, accent="right")
        self._tooltip.hide()

    # 按状态实时取色
    def _bg_color(self):
        if self._state == "pressed":
            return ColorPalette.custom_bg_one
        if self._state == "hover":
            return ColorPalette.custom_bg_two
        return ColorPalette.custom_bg_three

    def _icon_color(self):
        if self._state == "pressed":
            return ColorPalette.custom_icon_pressed
        if self._state == "hover":
            return ColorPalette.custom_icon_hover
        return ColorPalette.custom_icon_color

    # SET ACTIVE MENU
    # ///////////////////////////////////////////////////////////////
    def set_active(self, is_active):
        self._is_active = is_active
        self.update()

    # RETURN IF IS ACTIVE MENU
    # ///////////////////////////////////////////////////////////////
    def is_active(self):
        return self._is_active

    # PAINT EVENT
    # painting the button and the icon
    # ///////////////////////////////////////////////////////////////
    def paintEvent(self, event):
        # PAINTER
        paint = QPainter()
        paint.begin(self)
        paint.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_active:
            brush = QBrush(QColor(ColorPalette.custom_bg_one))
        else:
            brush = QBrush(QColor(self._bg_color()))

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
        if event == QEvent.Enter:
            self._state = "hover"
            self.update()
        elif event == QEvent.Leave:
            self._state = "normal"
            self.update()
        elif event == QEvent.MouseButtonPress:
            self._state = "pressed"
            self.update()
        elif event == QEvent.MouseButtonRelease:
            self._state = "hover"
            self.update()

    # MOUSE OVER
    # Event triggered when the mouse is over the BTN
    # ///////////////////////////////////////////////////////////////
    def enterEvent(self, event):
        self.change_style(QEvent.Enter)
        # self.move_tooltip()
        # self._tooltip.show()

    # MOUSE LEAVE
    # Event fired when the mouse leaves the BTN
    # ///////////////////////////////////////////////////////////////
    def leaveEvent(self, event):
        self.change_style(QEvent.Leave)
        # self.move_tooltip()
        # self._tooltip.hide()

    # MOUSE PRESS
    # Event triggered when the left button is pressed
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonPress)
            # SET FOCUS
            self.setFocus()
            # EMIT SIGNAL
            return self.clicked.emit()

    # MOUSE RELEASED
    # Event triggered after the mouse button is released
    # ///////////////////////////////////////////////////////////////
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonRelease)
            # EMIT SIGNAL
            return self.released.emit()

    # DRAW ICON WITH COLORS
    # ///////////////////////////////////////////////////////////////
    def icon_paint(self, qp, image, rect):
        icon = QPixmap(image)
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        if self._is_active:
            painter.fillRect(icon.rect(), ColorPalette.custom_context_color)
        else:
            painter.fillRect(icon.rect(), self._icon_color())
        qp.drawPixmap((rect.width() - icon.width()) / 2, (rect.height() - icon.height()) / 2, icon)
        painter.end()

    # SET ICON
    # ///////////////////////////////////////////////////////////////
    def set_icon(self, icon_path):
        self._set_icon_path = icon_path
        self.update()

    # 更新提示文本（语言切换时使用）
    def set_tooltip(self, text):
        self._tooltip_text = text
        self._tooltip.setText(text)
        self._tooltip.adjustSize()
