"""图片展示组件模块。"""

from qt_core import QLabel, QPixmap, Qt, QVBoxLayout, QWidget


class CPixmap(QWidget):
    """图片展示组件。"""

    def __init__(self, pic_path: str) -> None:
        """初始化图片组件。

        参数:
        - pic_path: 图片路径。

        返回:
        - None
        """
        super().__init__()
        # PROPERTIES
        self._icon_path = pic_path

        # SETUP UI
        self.setup_ui()

    def setup_ui(self) -> None:
        """构建图片组件内部布局。

        返回:
        - None
        """
        # LAYOUT
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # LABEL
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # PAINTER
        self.set_icon(self._icon_path)

        # ADD TO LAYOUT
        self.layout.addWidget(self.icon)

    def set_icon(self, icon_path: str) -> None:
        """设置当前显示图片。

        参数:
        - icon_path: 图片路径。

        返回:
        - None
        """
        icon = QPixmap(icon_path)
        # SET PIXMAP
        self.icon.setPixmap(icon)
