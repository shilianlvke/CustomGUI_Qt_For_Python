"""树与树形表格（复刻 Sakai / PrimeVue 的 Tree 与 TreeTable）。

设计要点：

- 数据统一用 ``list[dict]`` 表达，节点字段为 ``label/key/icon/children/disabled``；
- ``CTree`` 内部使用 ``QTreeWidget``，惰性展开与折叠交给 Qt，行外观由
  ``_CTreeDelegate`` 完全自绘（展开箭头、复选框、图标、文字）；
- ``CTreeTable`` 内部使用 ``QTreeView + QStandardItemModel``，列定义复用
  :class:`~..table.CTableColumn`，语义标签复用其 ``tag`` 回调；
- 所有颜色在绘制时实时读取 :func:`~...display.palette.tokens` 与
  :func:`~...panels.style.panel_colors`，主题切换后调用 ``update()`` 即可重绘。

两种视图的行内布局算法完全一致，所以几何与画笔工具都在 ``paint.py`` 里：

===============  ===========================================================
``roles.py``     item data role 约定（``NODE_ROLE`` / ``KEY_ROLE``）
``paint.py``     行内度量、箭头/复选框/图标绘制、节点字段取值
``delegate.py``  两个视图的行委托（单列自绘 / 多列复用 ``CTableColumn``）
``view.py``      ``CTree``（``QTreeWidget`` 版）
``treetable.py`` ``CTreeTable``（``QTreeView`` 版）
===============  ===========================================================

对外仍然只有 :mod:`sllkgui.guicore.custom_ui.data.tree` 这一个入口。
"""

from .roles import KEY_ROLE as KEY_ROLE
from .roles import NODE_ROLE as NODE_ROLE
from .treetable import CTreeTable as CTreeTable
from .view import CTree as CTree

__all__ = ["CTree", "CTreeTable", "KEY_ROLE", "NODE_ROLE"]
