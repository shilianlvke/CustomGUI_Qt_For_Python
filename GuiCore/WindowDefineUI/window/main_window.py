"""模块说明。"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout

from AppCore import AppSettings
from GuiCore.styles import Styles


class CWindow(QFrame):
    """主窗口背景容器。

    职责:
    - 创建窗口根布局并应用全局样式。
    - 按配置决定是否启用阴影效果。
    """

    def __init__(self, *, horizontal: bool = True) -> None:
        """初始化窗口容器。

        参数:
        - horizontal: True 使用水平布局，False 使用垂直布局。

        返回:
        - None
        """
        super().__init__()
        self.setObjectName("CWindow_Frame")
        if horizontal:
            self.layout = QHBoxLayout(self)
        else:
            self.layout = QVBoxLayout(self)
        margin = AppSettings.window_margin
        self.layout.setContentsMargins(margin, margin, margin, margin)
        self.layout.setSpacing(AppSettings.window_space)
        if AppSettings.custom_title_bar and AppSettings.window_shadow:
            self.shadow = QGraphicsDropShadowEffect()
            self.shadow.setBlurRadius(20)
            self.shadow.setXOffset(0)
            self.shadow.setYOffset(0)
            self.shadow.setColor(QColor(0, 0, 0, 160))
            self.setGraphicsEffect(self.shadow)
        self.setStyleSheet(Styles().style)
