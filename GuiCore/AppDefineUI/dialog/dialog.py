"""模块说明。"""

from typing import override

from AppCore import AppSettings
from GuiCore.CustomUI import CCard
from GuiCore.WindowDefineUI import CTitleBar, CWindow
from qt_core import QDialog, QMouseEvent, QPoint, Qt, QVBoxLayout


class CDialog(QDialog):
    """通用对话框基类。

    职责:
    - 统一构建自定义标题栏与内容容器。
    - 支持无边框拖拽体验。
    """

    def __init__(self, title: str) -> None:
        """初始化对话框。

        参数:
        - title: 对话框标题文本。

        返回:
        - None
        """
        super().__init__()
        self.dragPos = QPoint(0, 0)
        layout = QVBoxLayout()
        self.setLayout(layout)
        if AppSettings.custom_title_bar:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.BG = CWindow(horizontal=False)
        layout.addWidget(self.BG)
        self.BG.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        if AppSettings.custom_title_bar:
            self.title_bar = CTitleBar(
                self,
                self,
            )
            self.title_bar.setMaximumHeight(40)
            self.title_bar.set_title(title)
            self.BG.layout.addWidget(self.title_bar)

        content = CCard()
        self.content_layout = QVBoxLayout()
        content.setLayout(self.content_layout)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.BG.layout.addWidget(content)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """记录拖拽起点并转移焦点。

        参数:
        - event: 鼠标事件对象。

        返回:
        - None
        """
        self.dragPos = event.globalPosition().toPoint()
        # 点击窗口其他区域时转移焦点
        self.focusNextChild()
