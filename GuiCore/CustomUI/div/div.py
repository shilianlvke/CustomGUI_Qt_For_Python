from PySide6.QtWidgets import QHBoxLayout, QFrame, QWidget


# CUSTOM LEFT MENU
# ///////////////////////////////////////////////////////////////
class CHDiv(QWidget):
    """水平分割线组件。"""

    def __init__(self):
        """初始化水平分割线。"""

        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.frame_line = QFrame()
        self.frame_line.setObjectName("CHDiv_Frame")
        # self.frame_line.setStyleSheet(f"background: {ColorPalette.custom_bg_one};")
        self.frame_line.setMaximumHeight(1)
        self.frame_line.setMinimumHeight(1)
        self.layout.addWidget(self.frame_line)
        self.setMaximumHeight(1)


class CVDiv(QWidget):
    """垂直分割线组件。"""

    def __init__(self):
        """初始化垂直分割线。"""

        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.frame_line = QFrame()
        self.frame_line.setObjectName("CVDiv_Frame")
        self.frame_line.setMaximumWidth(1)
        self.frame_line.setMinimumWidth(1)
        self.layout.addWidget(self.frame_line)
        self.setMaximumWidth(20)
        self.setMinimumWidth(20)
