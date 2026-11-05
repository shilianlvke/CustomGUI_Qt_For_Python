"""树组件的 item data role 约定。

``CTree``（``QTreeWidget``）与 ``CTreeTable``（``QStandardItemModel``）用同一套
role，节点数据才能在两种视图之间互换。
"""

from PySide6.QtCore import Qt

#: 节点原始 ``dict``
NODE_ROLE = Qt.UserRole + 10
#: 节点选择键
KEY_ROLE = Qt.UserRole + 11

__all__ = ["KEY_ROLE", "NODE_ROLE"]
