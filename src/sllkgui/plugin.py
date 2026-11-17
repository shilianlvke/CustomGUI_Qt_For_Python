"""插件作者公开门面。

插件只应从这里导入基座类型::

    from sllkgui.plugin import (
        GalleryContext, GallerySettings, GalleryShortcut, GalleryShortcuts,
        GalleryTray, Permission, Plugin, PluginError, Setting, SettingOption,
        SettingsAction, SettingsInfo, SettingsPage, SettingsSection, ShortcutBinding,
    )

设置声明示例（在 ``on_load`` 中）::

    ctx.settings.define(
        SettingsPage(
            page_id="",
            title="桌面整理",
            sections=[
                SettingsSection(
                    title="行为",
                    items=[
                        Setting.switch("auto_refresh", True, "自动刷新"),
                        Setting.select("sort_mode", "name", "排序方式",
                                       [("name", "名称"), ("time", "时间")]),
                        Setting.number("columns", 4, "列数", minimum=1, maximum=12),
                    ],
                )
            ],
        )
    )
    columns = ctx.settings.get("columns", 4)
"""

from __future__ import annotations

from .appcore.settings.schema import (
    Setting,
    SettingOption,
    SettingsAction,
    SettingsInfo,
    SettingsPage,
    SettingsSection,
)
from .gallery.api import (
    PLUGIN_API_VERSION,
    GalleryContext,
    GallerySettings,
    GalleryShortcut,
    GalleryShortcuts,
    GalleryTray,
    Permission,
    Plugin,
    ShortcutBinding,
    ShortcutConflict,
    TrayEntry,
    TrayGroup,
)
from .gallery.errors import GalleryError as PluginError

__all__ = [
    "PLUGIN_API_VERSION",
    "GalleryContext",
    "GallerySettings",
    "GalleryShortcut",
    "GalleryShortcuts",
    "GalleryTray",
    "Permission",
    "Plugin",
    "PluginError",
    "Setting",
    "SettingOption",
    "SettingsAction",
    "SettingsInfo",
    "SettingsPage",
    "SettingsSection",
    "ShortcutBinding",
    "ShortcutConflict",
    "TrayEntry",
    "TrayGroup",
]
