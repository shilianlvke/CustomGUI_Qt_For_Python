import webbrowser
from qt_core import (
    QCursor,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPixmap,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
)
from AppCore import PathFactory, ColorPalette


class CShowCard(QFrame):
    """展示卡片组件。

    职责:
    - 组合上半区自定义控件与下半区跳转区域。
    - 提供统一卡片样式与链接跳转行为。
    """

    def __init__(
        self,
        size: QSize = None,
        source_url="https://example.com",
        bottom_text="查看源代码",
        widget=None,
        radius: int = 8,
        border_size: int = 12,
    ):
        """初始化展示卡片。

        参数:
        - size: 卡片固定尺寸。
        - source_url: 点击跳转链接。
        - bottom_text: 底部提示文本。
        - widget: 顶部插入组件。
        - radius: 卡片圆角半径。
        - border_size: 卡片边框宽度。

        返回:
        - None
        """

        super().__init__()
        self.setObjectName("CShowCard")
        if size is not None:
            self.setFixedSize(size)
        self.setMinimumHeight(96)
        self.radius = radius
        self.border_size = border_size
        self.colorpalette = ColorPalette
        self.bottom_text = bottom_text
        self.source_url = source_url

        # 初始化上下区域
        self.top_area = QWidget()
        self.top_area.setObjectName("topArea")

        self.bottom_area = QWidget()
        self.bottom_area.setObjectName("bottomArea")
        self.bottom_area.setCursor(QCursor(Qt.PointingHandCursor))
        self.bottom_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 底部区域内容布局
        bottom_layout = QHBoxLayout(self.bottom_area)

        # 底部文字和图标（更简约的样式）
        self.source_label = QLabel(self.bottom_text)
        self.source_label.setObjectName("SourceLabel")
        self.icon_label = QLabel()  # 简约箭头图标
        pixmap = QPixmap(PathFactory.set_svg_icon("icon_share"))
        pixmap = pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.icon_label.setObjectName("IconLabel")
        self.icon_label.setPixmap(pixmap)

        bottom_layout.addWidget(self.source_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.icon_label)

        # 卡片主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)  # 无间距，更一体化
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_area)
        main_layout.addWidget(self.bottom_area)
        if widget is not None:
            self.set_top_widget(widget)
        # 样式
        self._setup_style()
        # 绑定点击事件
        self.bottom_area.mousePressEvent = self._on_source_click

    def _setup_style(self):
        """设置卡片样式表。

        返回:
        - None
        """

        self.setStyleSheet(f"""
            #CShowCard {{
                border: {self.border_size}px solid transparent;
                border-radius: {self.radius}px;
            }}
            #topArea {{
                background-color: {self.colorpalette.custom_bg_three};
                border-top-left-radius: {self.radius}px;
                border-top-right-radius: {self.radius}px;
            }}
            #bottomArea {{
                background-color: {self.colorpalette.custom_bg_two};
                border-bottom-left-radius: {self.radius}px;
                border-bottom-right-radius: {self.radius}px;
            }}
            #SourceLabel {{
                color: {self.colorpalette.custom_text_foreground};
                background-color: {self.colorpalette.custom_bg_two};
            }}
            #IconLabel {{
                background-color: {self.colorpalette.custom_bg_two};
            }}
        """)

    def set_top_widget(self, widget):
        """设置上半区组件内容。

        参数:
        - widget: 要放入上半区的组件。

        返回:
        - None
        """

        # 清空原有内容
        if self.top_area.layout():
            for i in reversed(range(self.top_area.layout().count())):
                item = self.top_area.layout().itemAt(i)
                if item.widget():
                    item.widget().setParent(None)
        else:
            self.top_area.setLayout(QHBoxLayout())

        # 设置上半部分布局（居中+内边距）
        top_layout = self.top_area.layout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        # top_layout.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(widget)

    def _on_source_click(self, event):
        """处理底部区域点击并打开链接。

        参数:
        - event: 鼠标事件对象。

        返回:
        - None
        """

        webbrowser.open(self.source_url)
