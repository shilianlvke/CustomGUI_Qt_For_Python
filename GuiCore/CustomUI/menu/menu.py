from PySide6.QtWidgets import QMenu

# 菜单项的固定布局度量（与主题无关，故不进全局样式表）
_ITEM_PADDING_LEFT = 20
_ITEM_PADDING_Y = 5


class CMenu(QMenu):
    """下拉菜单。

    样式约定（与 ``CPushButton`` 一致）：**颜色**由 ``GuiCore/styles.py`` 的
    ``#CMenu_Menu`` 提供，透明度经动态属性 ``transparent`` 选择。菜单是独立
    顶层窗口，不经过 ``CWindow``，因此依赖 ``CWindow.apply_style`` 下发的应用级
    样式表着色。**实例级几何**（圆角、边框宽度、菜单项内边距）由本类本地覆盖。
    """

    def __init__(
        self,
        parent=None,
        width: int = 64 + 36,
        radius: int = 8,
        border_size: int = 2,
        colorpalette=None,
        is_transparent: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("CMenu_Menu")
        self.setFixedWidth(width)
        self.radius = radius
        self.border_size = border_size
        self.color = colorpalette
        self._is_transparent = is_transparent
        self._apply_geometry()
        self.setProperty("transparent", "true" if is_transparent else "false")

    def _apply_geometry(self):
        """实例级几何：圆角、边框宽度与菜单项内边距（与主题无关，故不放进全局样式表）。"""
        self.setStyleSheet(
            f"#CMenu_Menu {{ border-width: {self.border_size}px;"
            f" border-radius: {self.radius}px; }}"
            f"#CMenu_Menu::item {{ border-width: {self.border_size}px;"
            f" border-radius: {self.radius}px;"
            f" padding-left: {_ITEM_PADDING_LEFT}px;"
            f" padding-top: {_ITEM_PADDING_Y}px;"
            f" padding-bottom: {_ITEM_PADDING_Y}px; }}"
            f"#CMenu_Menu::icon {{ padding-left: {_ITEM_PADDING_LEFT}px; }}"
        )
