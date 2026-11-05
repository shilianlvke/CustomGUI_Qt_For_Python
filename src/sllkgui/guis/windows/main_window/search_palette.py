"""标题栏搜索弹层：输入关键字过滤页面标题，回车或点击直接跳转。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal

from sllkgui.appcore import AppSettings, Language
from sllkgui.guicore import CInputText
from sllkgui.guicore.custom_ui.line_edit.overlay import CPopover
from sllkgui.guicore.custom_ui.menu.menu_list import CMenuList

from .registry import get_page_routes

#: 弹层一次最多展示的结果条数（超出后只保留最前面的匹配）。
#: 保留为兼容别名，运行时以 :attr:`AppSettings.search.max_results` 为准。
MAX_RESULTS = 8


class CSearchPalette(CPopover):
    """按页面标题过滤的快速跳转面板。

    标题栏搜索按钮的落点：输入关键字实时过滤全部页面路由，回车跳转第一条，
    点击条目跳转对应页面。路由在每次展开时重新解析，语言切换后立即生效。
    """

    #: 选中某个页面（参数是左菜单按钮 ID）
    selected = Signal(str)

    def __init__(self, window, parent=None):
        super().__init__(parent or window, width=340)
        self.setObjectName("CSearchPalette")
        self._window = window
        self._routes: dict[str, tuple[str, str]] = {}
        self._max_results = int(AppSettings.search.max_results)

        self._input = CInputText(
            placeholder=Language.resolve_key("language.UI.ui_Search", "Search pages…"),
            size="sm",
            icon="icon_search",
        )
        self._input.textChanged.connect(self._apply_filter)
        self._input.returnPressed.connect(self._activate_first)
        self.content_layout().addWidget(self._input)

        self._list = CMenuList(items=[])
        self._list.itemClicked.connect(self._activate_item)
        self.content_layout().addWidget(self._list)

    # ------------------------------------------------------------------
    # 展示
    # ------------------------------------------------------------------
    def show_for(self, anchor) -> None:
        """贴住标题栏按钮展开，并重置过滤条件。"""
        self._routes = dict(get_page_routes(Language))
        self._input.clear()
        self._apply_filter("")
        super().show_at(anchor)
        self._input.setFocus(Qt.OtherFocusReason)

    def routes(self) -> dict[str, tuple[str, str]]:
        return dict(self._routes)

    # ------------------------------------------------------------------
    # 过滤与跳转
    # ------------------------------------------------------------------
    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        items = []
        for btn_name, (_page_name, title) in self._routes.items():
            if needle and needle not in title.lower() and needle not in btn_name.lower():
                continue
            items.append({"label": title, "key": btn_name})
            if len(items) >= self._max_results:
                break
        self._list.set_items(items)
        self.adjustSize()

    def _activate_first(self) -> None:
        rows = self._list.visible_items()
        if rows:
            self._activate_item(rows[0])

    def _activate_item(self, item) -> None:
        key = getattr(item, "key", None)
        if key:
            self.selected.emit(key)
        self.hide()


__all__ = ["CSearchPalette", "MAX_RESULTS"]
