"""插件管理页（基座原生页面）的包结构。

模块分层（只允许向下依赖）：

    page ← panels ← entries ← theme ← context
"""

from .page import StorePage as StorePage
from .page import build_plugin_store_page as build_plugin_store_page

__all__ = ["StorePage", "build_plugin_store_page"]
