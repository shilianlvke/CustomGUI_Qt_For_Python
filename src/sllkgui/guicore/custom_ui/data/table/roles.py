"""表格模型的 item data role 约定（模型写入、委托读取）。

放在独立模块而不是 ``model.py``：委托与容器视图都要读这些 role，
散在模型里会让三者互相 import，形成环。
"""

from PySide6.QtCore import Qt

#: 单元格语义标签：(severity, text)
TAG_ROLE = Qt.UserRole + 1
#: 分组头行标记
GROUP_ROLE = Qt.UserRole + 2
#: 单元格对应的原始行数据
RECORD_ROLE = Qt.UserRole + 3
#: 行展开详情行标记
DETAIL_ROLE = Qt.UserRole + 4

__all__ = ["DETAIL_ROLE", "GROUP_ROLE", "RECORD_ROLE", "TAG_ROLE"]
