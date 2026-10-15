from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton
from AppCore import PathFactory, get_design_tokens


class CMenuButton(QPushButton):
    """带下拉菜单的按钮。

    样式约定（与 ``CPushButton`` 一致）：**颜色与图标**由 ``GuiCore/styles.py``
    的 ``#CMenuButton_PushButton`` 提供（含 ``::menu-indicator`` 箭头图标），
    本类只声明 objectName，不做任何主题订阅；**实例级几何**（圆角、边框宽度、
    箭头偏移）由本类本地覆盖。

    ``radius`` / ``border_size`` 默认回落到设计令牌，显式传参即可覆盖。
    """

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text: str | None = None,
        icon: QIcon | str | None = None,
        radius: int | None = None,
        border_size: int | None = None,
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
        tokens = get_design_tokens()
        self.radius = tokens.radius.window if radius is None else radius
        self.border_size = tokens.border.width if border_size is None else border_size
        self.color = colorpalette
        self._apply_geometry()

        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

    def _apply_geometry(self):
        """实例级几何：圆角、边框宽度与下拉箭头偏移（与主题无关，故不放进全局样式表）。"""
        self.setStyleSheet(
            f"#CMenuButton_PushButton {{"
            f" border-width: {self.border_size}px;"
            f" border-radius: {self.radius}px; }}"
            f"#CMenuButton_PushButton::menu-indicator {{"
            f" padding-right: 4px; }}"
            f"#CMenuButton_PushButton::menu-indicator:pressed,"
            f"#CMenuButton_PushButton::menu-indicator:open {{"
            f" position: relative; top: 2px; left: 2px; }}"
        )
