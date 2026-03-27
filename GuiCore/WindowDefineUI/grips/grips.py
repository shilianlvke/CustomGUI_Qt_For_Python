"""模块说明。"""

from typing import override

from qt_core import QCursor, QFrame, QRect, QSize, QSizeGrip, Qt, QWidget


class CGrips(QWidget):
    """窗口缩放夹点组件。

    职责:
    - 根据位置创建对应的边缘/角落缩放区域。
    - 响应鼠标拖动调整窗口尺寸。
    """

    def __init__(self, parent: QWidget, position: str, *, disable_color: bool = False) -> None:
        """初始化夹点组件。

        参数:
        - parent: 父窗口对象。
        - position: 夹点位置标识。
        - disable_color: 是否禁用调试颜色背景。

        返回:
        - None
        """
        # SETUP UI
        # ///////////////////////////////////////////////////////////////
        super().__init__()
        self.parent = parent
        self.setParent(parent)
        self.wi = Widgets()

        # SHOW TOP LEFT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "top_left":
            self.wi.top_left(self)
            grip = QSizeGrip(self.wi.top_left_grip)
            grip.setFixedSize(self.wi.top_left_grip.size())
            self.setGeometry(5, 5, 15, 15)

            # ENABLE COLOR
            if disable_color:
                self.wi.top_left_grip.setStyleSheet("background: transparent")

        # SHOW TOP RIGHT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "top_right":
            self.wi.top_right(self)
            grip = QSizeGrip(self.wi.top_right_grip)
            grip.setFixedSize(self.wi.top_right_grip.size())
            self.setGeometry(self.parent.width() - 20, 5, 15, 15)

            # ENABLE COLOR
            if disable_color:
                self.wi.top_right_grip.setStyleSheet("background: transparent")

        # SHOW BOTTOM LEFT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "bottom_left":
            self.wi.bottom_left(self)
            grip = QSizeGrip(self.wi.bottom_left_grip)
            grip.setFixedSize(self.wi.bottom_left_grip.size())
            self.setGeometry(5, self.parent.height() - 20, 15, 15)

            # ENABLE COLOR
            if disable_color:
                self.wi.bottom_left_grip.setStyleSheet("background: transparent")

        # SHOW BOTTOM RIGHT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "bottom_right":
            self.wi.bottom_right(self)
            grip = QSizeGrip(self.wi.bottom_right_grip)
            grip.setFixedSize(self.wi.bottom_right_grip.size())
            self.setGeometry(self.parent.width() - 20, self.parent.height() - 20, 15, 15)

            # ENABLE COLOR
            if disable_color:
                self.wi.bottom_right_grip.setStyleSheet("background: transparent")

        # SHOW TOP GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "top":
            self.wi.top(self)
            self.setGeometry(0, 5, self.parent.width(), 10)
            self.setMaximumHeight(10)

            # RESIZE TOP
            def resize_top(event: object) -> None:
                delta = event.pos()
                height = max(self.parent.minimumHeight(), self.parent.height() - delta.y())
                geo = self.parent.geometry()
                geo.setTop(geo.bottom() - height)
                self.parent.setGeometry(geo)
                event.accept()

            self.wi.top_grip.mouseMoveEvent = resize_top

            # ENABLE COLOR
            if disable_color:
                self.wi.top_grip.setStyleSheet("background: transparent")

        # SHOW BOTTOM GRIP
        # ///////////////////////////////////////////////////////////////
        elif position == "bottom":
            self.wi.bottom(self)
            self.setGeometry(0, self.parent.height() - 10, self.parent.width(), 10)
            self.setMaximumHeight(10)

            # RESIZE BOTTOM
            def resize_bottom(event: object) -> None:
                delta = event.pos()
                height = max(self.parent.minimumHeight(), self.parent.height() + delta.y())
                self.parent.resize(self.parent.width(), height)
                event.accept()

            self.wi.bottom_grip.mouseMoveEvent = resize_bottom

            # ENABLE COLOR
            if disable_color:
                self.wi.bottom_grip.setStyleSheet("background: transparent")

        # SHOW LEFT GRIP
        # ///////////////////////////////////////////////////////////////
        elif position == "left":
            self.wi.left(self)
            self.setGeometry(0, 10, 10, self.parent.height())
            self.setMaximumWidth(10)

            # RESIZE LEFT
            def resize_left(event: object) -> None:
                delta = event.pos()
                width = max(self.parent.minimumWidth(), self.parent.width() - delta.x())
                geo = self.parent.geometry()
                geo.setLeft(geo.right() - width)
                self.parent.setGeometry(geo)
                event.accept()

            self.wi.left_grip.mouseMoveEvent = resize_left

            # ENABLE COLOR
            if disable_color:
                self.wi.left_grip.setStyleSheet("background: transparent")

        # RESIZE RIGHT
        # ///////////////////////////////////////////////////////////////
        elif position == "right":
            self.wi.right(self)
            self.setGeometry(self.parent.width() - 10, 10, 10, self.parent.height())
            self.setMaximumWidth(10)

            def resize_right(event: object) -> None:
                delta = event.pos()
                width = max(self.parent.minimumWidth(), self.parent.width() + delta.x())
                self.parent.resize(width, self.parent.height())
                event.accept()

            self.wi.right_grip.mouseMoveEvent = resize_right

            # ENABLE COLOR
            if disable_color:
                self.wi.right_grip.setStyleSheet("background: transparent")

    # MOUSE RELEASE
    # ///////////////////////////////////////////////////////////////
    @override
    def mouseReleaseEvent(self, event: object) -> None:
        """处理鼠标释放事件。

        参数:
        - event: 鼠标事件对象。

        返回:
        - None
        """
        _ = event
        self.mousePos = None

    # RESIZE EVENT
    # ///////////////////////////////////////////////////////////////
    @override
    def resizeEvent(self, event: object) -> None:
        """处理组件缩放并同步内部夹点几何。

        参数:
        - event: 缩放事件对象。

        返回:
        - None
        """
        _ = event
        if hasattr(self.wi, "top_grip"):
            self.wi.top_grip.setGeometry(0, 0, self.width(), 10)

        elif hasattr(self.wi, "bottom_grip"):
            self.wi.bottom_grip.setGeometry(0, 0, self.width(), 10)

        elif hasattr(self.wi, "left_grip"):
            self.wi.left_grip.setGeometry(0, 0, 10, self.height() - 20)

        elif hasattr(self.wi, "right_grip"):
            self.wi.right_grip.setGeometry(0, 0, 10, self.height() - 20)

        elif hasattr(self.wi, "top_right_grip"):
            self.wi.top_right_grip.setGeometry(self.width() - 15, 0, 15, 15)

        elif hasattr(self.wi, "bottom_left_grip"):
            self.wi.bottom_left_grip.setGeometry(0, self.height() - 15, 15, 15)

        elif hasattr(self.wi, "bottom_right_grip"):
            self.wi.bottom_right_grip.setGeometry(self.width() - 15, self.height() - 15, 15, 15)


# GRIP WIDGTES
# ///////////////////////////////////////////////////////////////
class Widgets:
    """夹点子部件构建器。"""

    def top_left(self, form: QWidget) -> None:
        """创建左上角夹点。"""
        self.top_left_grip = QFrame(form)
        self.top_left_grip.setObjectName("top_left_grip")
        self.top_left_grip.setFixedSize(15, 15)
        self.top_left_grip.setStyleSheet("background-color: #333; border: 2px solid #55FF00;")

    def top_right(self, form: QWidget) -> None:
        """创建右上角夹点。"""
        self.top_right_grip = QFrame(form)
        self.top_right_grip.setObjectName("top_right_grip")
        self.top_right_grip.setFixedSize(15, 15)
        self.top_right_grip.setStyleSheet("background-color: #333; border: 2px solid #55FF00;")

    def bottom_left(self, form: QWidget) -> None:
        """创建左下角夹点。"""
        self.bottom_left_grip = QFrame(form)
        self.bottom_left_grip.setObjectName("bottom_left_grip")
        self.bottom_left_grip.setFixedSize(15, 15)
        self.bottom_left_grip.setStyleSheet("background-color: #333; border: 2px solid #55FF00;")

    def bottom_right(self, form: QWidget) -> None:
        """创建右下角夹点。"""
        self.bottom_right_grip = QFrame(form)
        self.bottom_right_grip.setObjectName("bottom_right_grip")
        self.bottom_right_grip.setFixedSize(15, 15)
        self.bottom_right_grip.setStyleSheet("background-color: #333; border: 2px solid #55FF00;")

    def top(self, form: QWidget) -> None:
        """创建顶部边缘夹点。"""
        self.top_grip = QFrame(form)
        self.top_grip.setObjectName("top_grip")
        self.top_grip.setGeometry(QRect(0, 0, 500, 10))
        self.top_grip.setStyleSheet("background-color: rgb(85, 255, 255);")
        self.top_grip.setCursor(QCursor(Qt.SizeVerCursor))

    def bottom(self, form: QWidget) -> None:
        """创建底部边缘夹点。"""
        self.bottom_grip = QFrame(form)
        self.bottom_grip.setObjectName("bottom_grip")
        self.bottom_grip.setGeometry(QRect(0, 0, 500, 10))
        self.bottom_grip.setStyleSheet("background-color: rgb(85, 170, 0);")
        self.bottom_grip.setCursor(QCursor(Qt.SizeVerCursor))

    def left(self, form: QWidget) -> None:
        """创建左侧边缘夹点。"""
        self.left_grip = QFrame(form)
        self.left_grip.setObjectName("left")
        self.left_grip.setGeometry(QRect(0, 10, 10, 480))
        self.left_grip.setMinimumSize(QSize(10, 0))
        self.left_grip.setCursor(QCursor(Qt.SizeHorCursor))
        self.left_grip.setStyleSheet("background-color: rgb(255, 121, 198);")

    def right(self, form: QWidget) -> None:
        """创建右侧边缘夹点。"""
        self.right_grip = QFrame(form)
        self.right_grip.setObjectName("right")
        self.right_grip.setGeometry(QRect(0, 0, 10, 500))
        self.right_grip.setMinimumSize(QSize(10, 0))
        self.right_grip.setCursor(QCursor(Qt.SizeHorCursor))
        self.right_grip.setStyleSheet("background-color: rgb(255, 0, 127);")
