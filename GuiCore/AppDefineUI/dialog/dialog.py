from qt_core import QDialog, QPoint, QVBoxLayout, Qt
from AppCore import AppSettings, Language
from GuiCore import CCard, CTitleBar, CWindow


class CDialog(QDialog):

    def __init__(self, title):
        super().__init__()
        self.dragPos = QPoint(0, 0)
        layout = QVBoxLayout()
        self.setLayout(layout)
        # self.setFixedSize(QSize(500, 600))
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

    def mousePressEvent(self, event):
        self.dragPos = event.globalPosition().toPoint()
        # 点击窗口其他区域时转移焦点
        self.focusNextChild()
