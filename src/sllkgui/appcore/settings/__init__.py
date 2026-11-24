"""统一设置配置框架（基座 + 插件共用）。

分层：

- :mod:`schema`：设置项 / 分组 / 页面声明与取值校验；
- :mod:`registry`：命名空间隔离的全局注册表，拦截重复键；
- :mod:`store`：基座写 ``user.yaml``，插件按 ``plugin.<id>`` 分文件；
- :mod:`session`：草稿 / 脏值 / 保存 / 放弃 / 恢复默认；
- :mod:`base`：基座三张设置页（外观 / 界面 / 启动与窗口）。

用法::

    from sllkgui.appcore import SettingsSession, ensure_core_pages

    ensure_core_pages()
    session = SettingsSession()
    session.set("core.appearance.theme", "bright")
    session.save()
"""

from .base import KEY_BACKGROUND_BLUR as KEY_BACKGROUND_BLUR
from .base import KEY_BACKGROUND_FIT as KEY_BACKGROUND_FIT
from .base import KEY_BACKGROUND_IMAGE as KEY_BACKGROUND_IMAGE
from .base import KEY_DRAWER_MODE as KEY_DRAWER_MODE
from .base import KEY_GLASS_STRENGTH as KEY_GLASS_STRENGTH
from .base import KEY_LANGUAGE as KEY_LANGUAGE
from .base import KEY_MENU_MODE as KEY_MENU_MODE
from .base import KEY_REMEMBER_SIZE as KEY_REMEMBER_SIZE
from .base import KEY_SETTINGS_ACRYLIC as KEY_SETTINGS_ACRYLIC
from .base import KEY_THEME as KEY_THEME
from .base import KEY_TRANSPARENCY as KEY_TRANSPARENCY
from .base import build_core_pages
from .events import SettingsChangeBus, SettingsPageBus, settings_change_bus, settings_page_bus
from .registry import SettingsRegistry, set_settings_registry, settings_registry
from .schema import (
    Section,
    Setting,
    SettingControl,
    SettingKind,
    SettingOption,
    SettingsAction,
    SettingsConflictError,
    SettingsError,
    SettingsInfo,
    SettingsPage,
    SettingSpec,
    SettingsSection,
    SettingsValidationError,
    is_core_namespace,
    normalize_namespace,
    normalize_value,
    plugin_namespace,
)
from .session import SettingsSession
from .store import CoreSettingsBackend, PluginSettingsBackend, SettingsStore, settings_store

#: 基座页面只安装一次；重复调用是幂等的
_CORE_INSTALLED = False


def ensure_core_pages(registry: SettingsRegistry | None = None) -> tuple[SettingsPage, ...]:
    """确保基座设置页已注册（重复调用不会冲突）。"""
    global _CORE_INSTALLED
    target = registry if registry is not None else settings_registry()
    pages = []
    for page in build_core_pages():
        existing = target.page(page.page_id, namespace="core")
        if existing is None:
            pages.append(target.register(page, namespace="core"))
        else:
            pages.append(existing)
    _CORE_INSTALLED = True
    return tuple(pages)


def reset_core_settings_install() -> None:
    """测试辅助：允许在替换注册表后重新安装基座页面。"""
    global _CORE_INSTALLED
    _CORE_INSTALLED = False


__all__ = [
    "CoreSettingsBackend",
    "KEY_BACKGROUND_BLUR",
    "KEY_BACKGROUND_FIT",
    "KEY_BACKGROUND_IMAGE",
    "KEY_DRAWER_MODE",
    "KEY_GLASS_STRENGTH",
    "KEY_LANGUAGE",
    "KEY_MENU_MODE",
    "KEY_REMEMBER_SIZE",
    "KEY_SETTINGS_ACRYLIC",
    "KEY_THEME",
    "KEY_TRANSPARENCY",
    "PluginSettingsBackend",
    "Section",
    "Setting",
    "SettingControl",
    "SettingKind",
    "SettingOption",
    "SettingSpec",
    "SettingsAction",
    "SettingsChangeBus",
    "SettingsConflictError",
    "SettingsError",
    "SettingsInfo",
    "SettingsPage",
    "SettingsPageBus",
    "SettingsRegistry",
    "SettingsSection",
    "SettingsSession",
    "SettingsStore",
    "settings_store",
    "SettingsValidationError",
    "build_core_pages",
    "ensure_core_pages",
    "is_core_namespace",
    "normalize_namespace",
    "normalize_value",
    "plugin_namespace",
    "reset_core_settings_install",
    "set_settings_registry",
    "settings_change_bus",
    "settings_page_bus",
    "settings_registry",
]
