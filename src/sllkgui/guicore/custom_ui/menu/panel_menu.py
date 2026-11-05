"""垂直手风琴式面板菜单。

分组项可展开，子项可点击；默认同一时间只展开一个分组（``multiple=True``
可同时展开多个分组）。
"""

from __future__ import annotations

from .menu_list import CMenuList


class CPanelMenu(CMenuList):
    """垂直手风琴式菜单。

    Args:
        items: 菜单项（通常顶层为分组，``items`` 为子项）。
        width: 固定宽度。
        multiple: 为真时允许多个分组同时展开。
    """

    def __init__(self, items=None, width: int = 220, multiple: bool = False, parent=None):
        super().__init__(items=items, width=width, inline=True, parent=parent)
        self.setObjectName("CPanelMenu_Widget")
        self._multiple = multiple

    def toggle(self, path: str) -> None:
        """展开/收起分组；默认保持手风琴互斥。"""
        if path in self._expanded:
            super().toggle(path)
            return
        if not self._multiple:
            parts = [part for part in path.strip("/").split("/") if part]
            ancestors = {f"/{'/'.join(parts[:index])}" for index in range(1, len(parts))}
            self._expanded = ancestors
        super().toggle(path)


__all__ = ["CPanelMenu"]
