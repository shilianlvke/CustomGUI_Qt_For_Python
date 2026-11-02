"""右键上下文菜单。

继承自绘 ``CMenuListPopup``：位置由调用方通过 ``show_at`` 精确指定，
点击条目后自动关闭并发出 ``itemClicked``。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint

from .menu_list import CMenuListPopup


class CContextMenu(CMenuListPopup):
    """可在任意全局坐标弹出的右键菜单。"""

    def __init__(self, items=None, width: int = 220, parent=None):
        super().__init__(items=items, width=width, parent=parent)
        self.setObjectName("CContextMenu_Popup")

    def show_at(self, global_pos: QPoint) -> None:
        """在指定的全局坐标展开（菜单左上角对齐该坐标）。"""
        self.show_at_global(global_pos)


__all__ = ["CContextMenu"]
