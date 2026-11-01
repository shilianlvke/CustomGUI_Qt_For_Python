"""窗口装配层：把 guicore 的组件组装成可运行的主窗口。

``Ui_LeftColumn`` / ``Ui_RightColumn`` 已下沉到 ``customgui.guicore.window``
（它们是纯布局类），这里保留同名再导出，对外名字不变。
"""

from customgui.guicore.window import Ui_LeftColumn, Ui_RightColumn

from .pages import Ui_MainPages
from .windows import LoadingWindow, MainFunctions, SetupMainWindow, UiMainWindow

__all__ = [
    "Ui_LeftColumn",
    "Ui_RightColumn",
    "Ui_MainPages",
    "LoadingWindow",
    "MainFunctions",
    "SetupMainWindow",
    "UiMainWindow",
]
