from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QSizeGrip, QWidget

from sllkgui.appcore import AppSettings


class CGrips(QWidget):
    def __init__(self, parent, position, disable_color=False):

        # SETUP UI
        # ///////////////////////////////////////////////////////////////
        super().__init__()
        self.parent = parent
        self.setParent(parent)
        # 夹点几何来自 settings（此处读取，避免导入期触发配置加载）
        grips = AppSettings.grips
        self._corner_size = int(grips.corner_size)
        self._corner_offset = int(grips.corner_offset)
        self._corner_inset = int(grips.corner_inset)
        self._edge_size = int(grips.edge_size)
        self.wi = Widgets(self._corner_size, self._edge_size)

        # SHOW TOP LEFT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "top_left":
            self.wi.top_left(self)
            grip = QSizeGrip(self.wi.top_left_grip)
            grip.setFixedSize(self.wi.top_left_grip.size())
            self.setGeometry(
                self._corner_offset, self._corner_offset, self._corner_size, self._corner_size
            )

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.top_left_grip, disable_color)

        # SHOW TOP RIGHT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "top_right":
            self.wi.top_right(self)
            grip = QSizeGrip(self.wi.top_right_grip)
            grip.setFixedSize(self.wi.top_right_grip.size())
            self.setGeometry(
                self.parent.width() - self._corner_inset,
                self._corner_offset,
                self._corner_size,
                self._corner_size,
            )

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.top_right_grip, disable_color)

        # SHOW BOTTOM LEFT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "bottom_left":
            self.wi.bottom_left(self)
            grip = QSizeGrip(self.wi.bottom_left_grip)
            grip.setFixedSize(self.wi.bottom_left_grip.size())
            self.setGeometry(
                self._corner_offset,
                self.parent.height() - self._corner_inset,
                self._corner_size,
                self._corner_size,
            )

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.bottom_left_grip, disable_color)

        # SHOW BOTTOM RIGHT GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "bottom_right":
            self.wi.bottom_right(self)
            grip = QSizeGrip(self.wi.bottom_right_grip)
            grip.setFixedSize(self.wi.bottom_right_grip.size())
            self.setGeometry(
                self.parent.width() - self._corner_inset,
                self.parent.height() - self._corner_inset,
                self._corner_size,
                self._corner_size,
            )

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.bottom_right_grip, disable_color)

        # SHOW TOP GRIP
        # ///////////////////////////////////////////////////////////////
        if position == "top":
            self.wi.top(self)
            self.setGeometry(0, self._corner_offset, self.parent.width(), self._edge_size)
            self.setMaximumHeight(self._edge_size)

            # RESIZE TOP
            def resize_top(event):
                delta = event.pos()
                height = max(self.parent.minimumHeight(), self.parent.height() - delta.y())
                geo = self.parent.geometry()
                geo.setTop(geo.bottom() - height)
                self.parent.setGeometry(geo)
                event.accept()

            self.wi.top_grip.mouseMoveEvent = resize_top

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.top_grip, disable_color)

        # SHOW BOTTOM GRIP
        # ///////////////////////////////////////////////////////////////
        elif position == "bottom":
            self.wi.bottom(self)
            self.setGeometry(
                0, self.parent.height() - self._edge_size, self.parent.width(), self._edge_size
            )
            self.setMaximumHeight(self._edge_size)

            # RESIZE BOTTOM
            def resize_bottom(event):
                delta = event.pos()
                height = max(self.parent.minimumHeight(), self.parent.height() + delta.y())
                self.parent.resize(self.parent.width(), height)
                event.accept()

            self.wi.bottom_grip.mouseMoveEvent = resize_bottom

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.bottom_grip, disable_color)

        # SHOW LEFT GRIP
        # ///////////////////////////////////////////////////////////////
        elif position == "left":
            self.wi.left(self)
            self.setGeometry(0, self._edge_size, self._edge_size, self.parent.height())
            self.setMaximumWidth(self._edge_size)

            # RESIZE LEFT
            def resize_left(event):
                delta = event.pos()
                width = max(self.parent.minimumWidth(), self.parent.width() - delta.x())
                geo = self.parent.geometry()
                geo.setLeft(geo.right() - width)
                self.parent.setGeometry(geo)
                event.accept()

            self.wi.left_grip.mouseMoveEvent = resize_left

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.left_grip, disable_color)

        # RESIZE RIGHT
        # ///////////////////////////////////////////////////////////////
        elif position == "right":
            self.wi.right(self)
            self.setGeometry(
                self.parent.width() - self._edge_size,
                self._edge_size,
                self._edge_size,
                self.parent.height(),
            )
            self.setMaximumWidth(self._edge_size)

            def resize_right(event):
                delta = event.pos()
                width = max(self.parent.minimumWidth(), self.parent.width() + delta.x())
                self.parent.resize(width, self.parent.height())
                event.accept()

            self.wi.right_grip.mouseMoveEvent = resize_right

            # ENABLE COLOR
            if disable_color:
                self._set_colored(self.wi.right_grip, disable_color)

    @staticmethod
    def _set_colored(frame, disable_color):
        """夹点配色统一由 ``sllkgui.guicore/styles.py`` 按 objectName 提供。

        ``hide_grips`` 为真时经动态属性 ``colored="false"`` 置为透明（无边框）。
        """
        frame.setProperty("colored", "false" if disable_color else "true")

    # MOUSE RELEASE
    # ///////////////////////////////////////////////////////////////
    def mouseReleaseEvent(self, event):
        self.mousePos = None

    # RESIZE EVENT
    # ///////////////////////////////////////////////////////////////
    def resizeEvent(self, event):
        if hasattr(self.wi, "top_grip"):
            self.wi.top_grip.setGeometry(0, 0, self.width(), self._edge_size)

        elif hasattr(self.wi, "bottom_grip"):
            self.wi.bottom_grip.setGeometry(0, 0, self.width(), self._edge_size)

        elif hasattr(self.wi, "left_grip"):
            self.wi.left_grip.setGeometry(0, 0, self._edge_size, self.height() - self._corner_inset)

        elif hasattr(self.wi, "right_grip"):
            self.wi.right_grip.setGeometry(0, 0, self._edge_size, self.height() - self._corner_inset)

        elif hasattr(self.wi, "top_right_grip"):
            self.wi.top_right_grip.setGeometry(
                self.width() - self._corner_size, 0, self._corner_size, self._corner_size
            )

        elif hasattr(self.wi, "bottom_left_grip"):
            self.wi.bottom_left_grip.setGeometry(
                0, self.height() - self._corner_size, self._corner_size, self._corner_size
            )

        elif hasattr(self.wi, "bottom_right_grip"):
            self.wi.bottom_right_grip.setGeometry(
                self.width() - self._corner_size,
                self.height() - self._corner_size,
                self._corner_size,
                self._corner_size,
            )


# GRIP WIDGTES
# ///////////////////////////////////////////////////////////////
class Widgets:
    def __init__(self, corner_size: int = 15, edge_size: int = 10):
        self.corner_size = corner_size
        self.edge_size = edge_size

    def top_left(self, form):
        self.top_left_grip = QFrame(form)
        self.top_left_grip.setObjectName("top_left_grip")
        self.top_left_grip.setFixedSize(self.corner_size, self.corner_size)

    def top_right(self, form):
        self.top_right_grip = QFrame(form)
        self.top_right_grip.setObjectName("top_right_grip")
        self.top_right_grip.setFixedSize(self.corner_size, self.corner_size)

    def bottom_left(self, form):
        self.bottom_left_grip = QFrame(form)
        self.bottom_left_grip.setObjectName("bottom_left_grip")
        self.bottom_left_grip.setFixedSize(self.corner_size, self.corner_size)

    def bottom_right(self, form):
        self.bottom_right_grip = QFrame(form)
        self.bottom_right_grip.setObjectName("bottom_right_grip")
        self.bottom_right_grip.setFixedSize(self.corner_size, self.corner_size)

    def top(self, form):
        self.top_grip = QFrame(form)
        self.top_grip.setObjectName("top_grip")
        self.top_grip.setGeometry(QRect(0, 0, 500, self.edge_size))
        self.top_grip.setCursor(QCursor(Qt.SizeVerCursor))

    def bottom(self, form):
        self.bottom_grip = QFrame(form)
        self.bottom_grip.setObjectName("bottom_grip")
        self.bottom_grip.setGeometry(QRect(0, 0, 500, self.edge_size))
        self.bottom_grip.setCursor(QCursor(Qt.SizeVerCursor))

    def left(self, form):
        self.left_grip = QFrame(form)
        self.left_grip.setObjectName("left")
        self.left_grip.setGeometry(QRect(0, self.edge_size, self.edge_size, 480))
        self.left_grip.setMinimumSize(QSize(self.edge_size, 0))
        self.left_grip.setCursor(QCursor(Qt.SizeHorCursor))

    def right(self, form):
        self.right_grip = QFrame(form)
        self.right_grip.setObjectName("right")
        self.right_grip.setGeometry(QRect(0, 0, self.edge_size, 500))
        self.right_grip.setMinimumSize(QSize(self.edge_size, 0))
        self.right_grip.setCursor(QCursor(Qt.SizeHorCursor))
