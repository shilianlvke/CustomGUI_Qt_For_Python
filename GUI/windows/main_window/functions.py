"""模块说明。"""

from pathlib import Path

from PySide6 import QtCore, QtGui

from AppCore import AppSettings
from qt_core import (
    QEasingCurve,
    QFileDialog,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QPushButton,
    QWidget,
)


# FUNCTIONS
class MainFunctions:
    """主窗口通用功能集合。

    职责:
    - 提供页面切换、侧栏切换、按钮查询与文件选择等通用操作。
    """

    # SET MAIN WINDOW PAGES
    # ///////////////////////////////////////////////////////////////
    def set_page(self, page: QWidget) -> None:
        """切换主页面。

        参数:
        - page: 目标页面对象。

        返回:
        - None
        """
        self.ui.load_pages.pages.setCurrentWidget(page)

    # SET LEFT COLUMN PAGES
    # ///////////////////////////////////////////////////////////////
    def set_left_column_menu(self, menu: QWidget, title: str, icon_path: str) -> None:
        """设置左侧栏菜单页内容。

        参数:
        - menu: 目标菜单页对象。
        - title: 标题文本。
        - icon_path: 图标路径。

        返回:
        - None
        """
        self.ui.left_column.menus.menus.setCurrentWidget(menu)
        self.ui.left_column.title_label.setText(title)
        self.ui.left_column.icon.set_icon(icon_path)

    # RETURN IF LEFT COLUMN IS VISIBLE
    # ///////////////////////////////////////////////////////////////
    def left_column_is_visible(self) -> bool:
        """判断左侧栏是否可见。

        返回:
        - bool: 可见为 True，否则为 False。
        """
        width = self.ui.left_column_frame.width()
        return width != 0

    # RETURN IF RIGHT COLUMN IS VISIBLE
    # ///////////////////////////////////////////////////////////////
    def right_column_is_visible(self) -> bool:
        """判断右侧栏是否可见。

        返回:
        - bool: 可见为 True，否则为 False。
        """
        width = self.ui.right_column_frame.width()
        return width != 0

    # SET RIGHT COLUMN PAGES
    # ///////////////////////////////////////////////////////////////
    def set_right_column_menu(self, menu: QWidget) -> None:
        """设置右侧栏菜单页。

        参数:
        - menu: 目标菜单页对象。

        返回:
        - None
        """
        self.ui.right_column.menus.setCurrentWidget(menu)

    # GET TITLE BUTTON BY OBJECT NAME
    # ///////////////////////////////////////////////////////////////
    def get_title_bar_btn(self, object_name: str) -> QPushButton | None:
        """按对象名获取标题栏按钮。

        参数:
        - object_name: 按钮对象名。

        返回:
        - QPushButton | None: 匹配按钮对象。
        """
        return self.ui.title_bar_frame.findChild(QPushButton, object_name)

    # GET TITLE BUTTON BY OBJECT NAME
    # ///////////////////////////////////////////////////////////////
    def get_left_menu_btn(self, object_name: str) -> QPushButton | None:
        """按对象名获取左侧菜单按钮。

        参数:
        - object_name: 按钮对象名。

        返回:
        - QPushButton | None: 匹配按钮对象。
        """
        return self.ui.left_menu.findChild(QPushButton, object_name)

    # LEDT AND RIGHT COLUMNS / SHOW / HIDE
    # ///////////////////////////////////////////////////////////////
    def toggle_left_column(self) -> None:
        """切换左侧栏显隐状态。

        返回:
        - None
        """
        # GET ACTUAL CLUMNS SIZE
        width = self.ui.left_column_frame.width()
        right_column_width = self.ui.right_column_frame.width()
        MainFunctions.start_box_animation(self, width, right_column_width, "left")

    def toggle_right_column(self) -> None:
        """切换右侧栏显隐状态。

        返回:
        - None
        """
        # GET ACTUAL CLUMNS SIZE
        left_column_width = self.ui.left_column_frame.width()
        width = self.ui.right_column_frame.width()
        MainFunctions.start_box_animation(self, left_column_width, width, "right")

    def start_box_animation(self, left_box_width: int, right_box_width: int, direction: str) -> None:
        """执行左右侧栏联动动画。

        参数:
        - left_box_width: 当前左侧栏宽度。
        - right_box_width: 当前右侧栏宽度。
        - direction: 动画方向，``left`` 或 ``right``。

        返回:
        - None
        """
        time_animation = AppSettings.time_animation
        minimum_left = AppSettings.left_column_size.minimum
        maximum_left = AppSettings.left_column_size.maximum
        minimum_right = AppSettings.right_column_size.minimum
        maximum_right = AppSettings.right_column_size.maximum

        # Check Left Values
        left_width = maximum_left if left_box_width <= minimum_left and direction == "left" else minimum_left

        # Check Right values
        right_width = maximum_right if right_box_width <= minimum_right and direction == "right" else minimum_right

            # ANIMATION LEFT BOX
        self.left_box = QPropertyAnimation(self.ui.left_column_frame, b"minimumWidth")
        self.left_box.setDuration(time_animation)
        self.left_box.setStartValue(left_box_width)
        self.left_box.setEndValue(left_width)
        self.left_box.setEasingCurve(QEasingCurve.InOutQuart)

        # ANIMATION RIGHT BOX
        self.right_box = QPropertyAnimation(self.ui.right_column_frame, b"minimumWidth")
        self.right_box.setDuration(time_animation)
        self.right_box.setStartValue(right_box_width)
        self.right_box.setEndValue(right_width)
        self.right_box.setEasingCurve(QEasingCurve.InOutQuart)

        # GROUP ANIMATION
        self.group = QParallelAnimationGroup()
        self.group.stop()
        self.group.addAnimation(self.left_box)
        self.group.addAnimation(self.right_box)
        self.group.start()

    def set_select_path(self, obj: object) -> None:
        """弹窗选择目录并回填到输入控件。

        参数:
        - obj: 目标控件对象。

        返回:
        - None
        """
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        obj.setText(folder_path)

    def set_select_file(self, obj: object) -> None:
        """弹窗选择文件并回填到输入控件。

        参数:
        - obj: 目标控件对象。

        返回:
        - None
        """
        file_path, _file_name = QFileDialog.getOpenFileName(self, "选择文件")
        obj.setText(file_path)

    def open_directory(self) -> None:
        """打开输入框指定目录。

        返回:
        - None
        """
        if Path(self.app1_line_edit.text()).is_dir():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.app1_line_edit.text()))
