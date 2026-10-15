"""CustomGUI 配置系统（纯标准库核心，PyYAML 仅存在于 yaml_io 边界）。

使用方式：::

    from AppCore import AppSettings, AppThemes, initialize_app_context

    initialize_app_context()  # 可选：显式加载；不调用则首次访问时惰性加载
    AppSettings.theme_name                 # 强类型 str
    AppSettings.lef_menu_size.minimum      # 强类型 SizeRange
    AppThemes[AppSettings.theme_name].data # Attrs（属性/字典双访问）

本包顶层只暴露上述「配置访问入口」。框架内部实现按子模块组织，
需要时直接从子模块导入，避免包顶层堆砌无人使用的再导出：

    from AppCore.SYS.config.registry import ConfigRegistry
    from AppCore.SYS.config.schema import AppSettingsModel, SizeRange
    from AppCore.SYS.config.yaml_io import load_yaml_file
"""

from .mapping import Attrs, to_attrs
from .paths import apps_root
from .registry import (
    AppLanguages,
    AppOthers,
    AppSettings,
    AppThemes,
    get_app_context,
    initialize_app_context,
)

__all__ = [
    "AppSettings",
    "AppThemes",
    "AppLanguages",
    "AppOthers",
    "get_app_context",
    "initialize_app_context",
    "Attrs",
    "to_attrs",
    "apps_root",
]
