from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton
from AppCore import PathFactory


class CStatusButton(QPushButton):
    """多态按钮：点击在若干状态间循环，边框颜色随状态变化。

    样式约定（与 ``CPushButton`` 一致）：颜色、悬停/按下、各状态的边框色统一
    由 ``GuiCore/styles.py`` 的 ``#CStatusButton_PushButton`` 提供；状态经动态
    属性 ``status`` 由 QSS 属性选择器匹配。本类只保留实例级几何（圆角、边框
    宽度）覆盖，且不订阅主题——主题切换由全局样式表整体重建后自动生效。
    """

    statusChanged = Signal(int)

    def __init__(
        self,
        size: QSize = QSize(64, 32),
        text_negative: str | None = None,
        text_normal: str | None = None,
        text_positive: str | None = None,
        icon_negative: QIcon | str | None = None,
        icon_normal: QIcon | str | None = None,
        icon_positive: QIcon | str | None = None,
        radius: int = 8,
        border_size: int = 2,
        is_normal: bool = False,  # 三态开关
    ):
        super().__init__()
        self.setObjectName("CStatusButton_PushButton")
        self.status_list = [-1, 0, 1] if is_normal else [0, 1]
        self.status = self.status_list[0]
        self.radius = radius
        self.border_size = border_size

        if text_negative is not None:
            self.text_negative = text_negative
        if text_positive is not None:
            self.text_positive = text_positive
        if text_normal is not None:
            self.text_normal = text_normal
        if icon_negative is not None:
            if isinstance(icon_negative, str):
                pixmap = QPixmap(icon_negative)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                self.icon_negative = QIcon(rounded_pixmap)
                self.icon_size_negative = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
            elif isinstance(icon_negative, QIcon):
                self.icon_negative = icon_negative
        if icon_positive is not None:
            if isinstance(icon_positive, str):
                pixmap = QPixmap(icon_positive)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                self.icon_positive = QIcon(rounded_pixmap)
                self.icon_size_size = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
            elif isinstance(icon_positive, QIcon):
                self.icon_positive = icon_positive
        if icon_normal is not None:
            if isinstance(icon_normal, str):
                pixmap = QPixmap(icon_normal)
                rounded_pixmap = PathFactory.create_rounded_pixmap(pixmap, pixmap.height() / 2)
                self.icon_normal = QIcon(rounded_pixmap)
                self.icon_size_normal = QSize(int(size.width() * 0.8), int(size.height() * 0.8))
            elif isinstance(icon_normal, QIcon):
                self.icon_normal = icon_normal
        if size is not None:
            self.setFixedSize(size)
        # 绘制
        self.text_change()
        self.icon_change()
        self._apply_geometry()
        self._sync_status_property()
        # 禁用虚线焦点框
        self.setFocusPolicy(Qt.StrongFocus)

    def _apply_geometry(self):
        """实例级几何：圆角与边框宽度（与主题无关，故不放进全局样式表）。"""
        self.setStyleSheet(
            f"#CStatusButton_PushButton {{"
            f" border-width: {self.border_size}px;"
            f" border-radius: {self.radius}px; }}"
        )

    def _sync_status_property(self):
        """把当前状态写入动态属性并重新抛光，使 QSS 属性选择器立即生效。"""
        self.setProperty("status", self.status)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def text_change(self):
        if self.status == 1:
            if hasattr(self, "text_positive"):
                self.setText(self.text_positive)
            else:
                self.setText("")
        elif self.status == 0:
            if hasattr(self, "text_negative"):
                self.setText(self.text_negative)
            else:
                self.setText("")
        elif self.status == -1:
            if hasattr(self, "text_normal"):
                self.setText(self.text_normal)
            else:
                self.setText("")

    def icon_change(self):
        if self.status == 1:
            if hasattr(self, "icon_positive"):
                self.setIcon(self.icon_positive)
            if hasattr(self, "icon_size_positive"):
                self.setIconSize(self.icon_size_positive)
        elif self.status == 0:
            if hasattr(self, "icon_negative"):
                self.setIcon(self.icon_negative)
            if hasattr(self, "icon_size_negative"):
                self.setIconSize(self.icon_size_negative)
        elif self.status == -1:
            if hasattr(self, "icon_normal"):
                self.setIcon(self.icon_normal)
            if hasattr(self, "icon_size_normal"):
                self.setIconSize(self.icon_size_normal)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.status = self.status_list[(self.status_list.index(self.status) + 1) % len(self.status_list)]
        self.statusChanged.emit(self.status)
        self.text_change()
        self.icon_change()
        self._sync_status_property()
