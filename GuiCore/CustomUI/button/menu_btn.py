"""模块说明。"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton

from AppCore import PathFactory


class CMenuButton(QPushButton):
    """带菜单指示器的按钮组件。"""

    def __init__(self, size: QSize | None = None, **options: object) -> None:
        """初始化菜单按钮。

        参数:
        - size: 按钮基础尺寸。
        - text: 按钮文本。
        - icon: 图标对象或路径。
        - radius: 圆角半径。
        - border_size: 边框宽度。
        - colorpalette: 颜色对象。
        - is_transparent: 透明样式开关。

        返回:
        - None
        """
        text = options.get("text")
        icon = options.get("icon")
        radius = int(options.get("radius", 8))
        border_size = int(options.get("border_size", 2))
        colorpalette = options.get("colorpalette")
        _ = options.get("is_transparent", False)
        super().__init__()
        if size is None:
            size = QSize(64, 32)
        self.setObjectName("CMenuButton_PushButton")
        if text is not None:
            self.setText(text)
        if icon is not None:
            if isinstance(icon, str):
                pixmap = QPixmap(icon)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                icon = QIcon(rounded_pixmap)
                icon_size = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
                self.setIconSize(icon_size)
            self.setIcon(icon)
        if size is not None:
            temp_size = QSize(int(size.width() + 36), size.height())
            self.setFixedSize(temp_size)
        self.radius = radius
        self.border_size = border_size
        self.color = colorpalette

        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)
