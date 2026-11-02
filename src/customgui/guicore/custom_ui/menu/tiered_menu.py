"""垂直分层菜单。

子菜单在当前列表内缩进展开（内联），不依赖额外弹层，适合放在侧栏或
设置页中使用；多级嵌套同样支持。
"""

from __future__ import annotations

from .menu_list import CMenuList


class CTieredMenu(CMenuList):
    """垂直分层菜单。

    带子项的条目点击后原地展开/收起；叶子项点击发出 ``itemClicked`` 并执行
    ``command``。
    """

    def __init__(self, items=None, width: int = 220, parent=None):
        super().__init__(items=items, width=width, inline=True, parent=parent)
        self.setObjectName("CTieredMenu_Widget")


__all__ = ["CTieredMenu"]
