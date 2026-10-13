"""滚动区域组件：背景色实时跟随主题切换。"""

from PySide6.QtWidgets import QScrollArea

from AppCore import ColorPalette, get_theme_manager


class CScrollArea(QScrollArea):
    """带主题跟随背景色的滚动区域。

    - ``background`` 为 None 时使用当前主题的 ``custom_dark_three``；
    - 样式实时跟随主题切换（订阅刷新，组件销毁自动退订）。
    """

    def __init__(self, parent=None, background=None, object_name=None):
        super().__init__(parent)
        if object_name is not None:
            self.setObjectName(object_name)
        self._background = background
        self.update_style()
        get_theme_manager().subscribe(self.update_style)

    def update_style(self):
        """按当前调色板实时刷新背景色。"""
        color = self._background if self._background is not None else ColorPalette.custom_dark_three
        self.setStyleSheet(f"background: {color};")

    def set_background(self, color):
        """设置背景色（传 None 表示跟随主题默认色）。"""
        self._background = color
        self.update_style()
