from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton
from AppCore import PathFactory


class CMenuButton(QPushButton):
    """带下拉菜单的按钮。

    样式约定（与 ``CPushButton`` 一致）：全部样式由 ``GuiCore/styles.py`` 的
    ``#CMenuButton_PushButton`` 提供（含 ``::menu-indicator`` 箭头图标），本类
    只声明 objectName，不做任何内联样式与主题订阅。
    """

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text: str | None = None,
        icon: QIcon | str | None = None,
        radius: int = 8,
        border_size: int = 2,
        colorpalette=None,
        is_transparent: bool = False,
    ):
        super().__init__()
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
