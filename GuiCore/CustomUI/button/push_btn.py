from qt_core import QIcon, QPixmap, QPushButton, QSize, Qt
from AppCore import PicFixFactory


class CPushButton(QPushButton):
    """自定义按钮组件。"""

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text: str | None = None,
        icon: QIcon | str | None = None,
        is_trans: bool = False,
    ):
        """初始化按钮组件。

        参数:
        - size: 按钮尺寸。
        - text: 按钮文本。
        - icon: 图标对象或图标路径。
        - is_trans: 透明样式开关（预留参数）。

        返回:
        - None
        """

        super().__init__()
        self.setObjectName("CPushButton_PushButton")
        if text is not None:
            self.setText(text)
        if icon is not None:
            if isinstance(icon, str):
                pixmap = QPixmap(icon)
                rounded_pixmap = PicFixFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                icon = QIcon(rounded_pixmap)
                icon_size = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
                self.setIconSize(icon_size)
            self.setIcon(icon)
        if size is not None:
            self.setFixedSize(size)

        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)
