"""顶列：uic 生成的布局（``ui.py``）+ 组件实现（``top_column.py``）。

与左列（``left_column``）同构：``ui.py`` 是纯布局类，不依赖任何上层装配
代码，因此放在 guicore 内供 ``CTopColumn`` 直接使用，避免 guicore → guis 倒挂。
"""

from .top_column import CTopColumn as CTopColumn
from .ui import Ui_TopColumn as Ui_TopColumn

__all__ = ["CTopColumn", "Ui_TopColumn"]
