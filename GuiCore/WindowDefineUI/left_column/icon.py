"""模块说明。"""

from qt_core import QLabel, QPainter, QPixmap, Qt, QVBoxLayout, QWidget


# PY ICON WITH CUSTOM COLORS
# ///////////////////////////////////////////////////////////////
class PyIcon(QWidget):
    """可着色图标组件。"""

    def __init__(self, icon_path: str, icon_color: object) -> None:
        """初始化图标组件。

        参数:
        - icon_path: 图标路径。
        - icon_color: 图标颜色。

        返回:
        - None
        """
        super().__init__()

        # PROPERTIES
        self._icon_path = icon_path
        self._icon_color = icon_color

        # SETUP UI
        self.setup_ui()

    def setup_ui(self) -> None:
        """构建图标组件布局。

        返回:
        - None
        """
        # LAYOUT
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # LABEL
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignCenter)

        # PAINTER
        self.set_icon(self._icon_path, self._icon_color)

        # ADD TO LAYOUT
        self.layout.addWidget(self.icon)

    def set_icon(self, icon_path: str, icon_color: object | None = None) -> None:
        """设置图标与颜色。

        参数:
        - icon_path: 图标路径。
        - icon_color: 可选覆盖颜色。

        返回:
        - None
        """
        # GET COLOR
        color = icon_color if icon_color is not None else self._icon_color

        # PAINTER / PIXMAP
        icon = QPixmap(icon_path)
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(icon.rect(), color)
        painter.end()

        # SET PIXMAP
        self.icon.setPixmap(icon)
