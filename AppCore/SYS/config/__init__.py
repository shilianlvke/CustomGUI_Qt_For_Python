"""CustomGUI 配置系统（纯标准库核心，PyYAML 仅存在于 yaml_io 边界）。

使用方式：::

    from AppCore import AppSettings, AppThemes, initialize_app_context

    initialize_app_context()  # 可选：显式加载；不调用则首次访问时惰性加载
    AppSettings.theme_name                 # 强类型 str
    AppSettings.lef_menu_size.minimum      # 强类型 SizeRange
    AppThemes[AppSettings.theme_name].data # Attrs（属性/字典双访问）
"""

from .mapping import Attrs, deep_merge, to_attrs, to_dict
from .paths import iter_files, project_root, resolve_path
from .schema import (
    AppSettingsModel,
    SizeRange,
    ThemeModel,
    coerce_value,
    from_mapping,
    validate_language_data,
    validate_settings_data,
    validate_theme_data,
)
from .yaml_io import dump_yaml_file, load_yaml_file
from .registry import (
    AppContext,
    AppLanguages,
    AppOthers,
    AppSettings,
    AppThemes,
    ConfigFile,
    ConfigGroup,
    ConfigRegistry,
    get_app_context,
    initialize_app_context,
)

__all__ = [
    "Attrs",
    "deep_merge",
    "to_attrs",
    "to_dict",
    "project_root",
    "resolve_path",
    "iter_files",
    "AppSettingsModel",
    "SizeRange",
    "ThemeModel",
    "coerce_value",
    "from_mapping",
    "validate_settings_data",
    "validate_theme_data",
    "validate_language_data",
    "load_yaml_file",
    "dump_yaml_file",
    "ConfigFile",
    "ConfigGroup",
    "ConfigRegistry",
    "AppContext",
    "get_app_context",
    "initialize_app_context",
    "AppSettings",
    "AppThemes",
    "AppLanguages",
    "AppOthers",
]
