"""数据表格（复刻 PrimeVue Aura DataTable / Column / Paginator）。

实现要点：

- 数据层用 ``QAbstractTableModel``，行数据是 ``dict``，列由 :class:`CTableColumn`
  描述；排序、过滤、分页都在模型侧完成，视图只负责呈现；
- 视觉层复用设计令牌与 ``CTableDelegate``：语义状态列画成 ``CTag`` 同款胶囊，
  分组行整行合并并画成浅色分组头；
- 冻结列用第二个 ``QTableView`` 共用同一个模型与选择模型，隐藏非冻结/冻结列，
  两个视图的垂直滚动与表头排序指示保持同步；
- 分页条 ``CPaginator`` 与表格模型双向绑定，页码、每页条数变化即时重排。

按职责拆成四个模块，改一处不用翻 900 行：

=================  ==========================================================
``roles.py``       item data role 约定（模型写入、委托读取）
``column.py``      列定义 ``CTableColumn``（格式化与语义标签回调）
``model.py``       数据模型 ``CTableModel``（过滤 → 排序 → 分组 → 分页）
``delegate.py``    单元格绘制 ``CTableDelegate``（分组头 / 语义标签 / 文本）
``view.py``        容器 ``CDataTable``（表格 + 冻结列 + 空态 + 分页条）
=================  ==========================================================

对外仍然只有 :mod:`customgui.guicore.custom_ui.data.table` 这一个入口。
"""

from .column import CTableColumn as CTableColumn
from .delegate import CTableDelegate as CTableDelegate
from .model import CTableModel as CTableModel
from .roles import DETAIL_ROLE as DETAIL_ROLE
from .roles import GROUP_ROLE as GROUP_ROLE
from .roles import RECORD_ROLE as RECORD_ROLE
from .roles import TAG_ROLE as TAG_ROLE
from .view import CDataTable as CDataTable

__all__ = [
    "CDataTable",
    "CTableColumn",
    "CTableDelegate",
    "CTableModel",
    "DETAIL_ROLE",
    "GROUP_ROLE",
    "RECORD_ROLE",
    "TAG_ROLE",
]
