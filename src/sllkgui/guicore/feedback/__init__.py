"""Toast 运行时总线（去重 / 通道 / 溢出 / 状态机）。

与 ``guicore.custom_ui.feedback`` 的分工：那边是**组件**（``CToast`` / ``CMessage``），
这边是**调度**。原生页与插件门面都从这里进，避免各自实现一套时长与去重。
"""

from .toast_bus import ToastBus as ToastBus
from .toast_bus import ToastRecord as ToastRecord
from .toast_bus import reset_toast_bus as reset_toast_bus
from .toast_bus import toast_bus as toast_bus

__all__ = ["ToastBus", "ToastRecord", "reset_toast_bus", "toast_bus"]
