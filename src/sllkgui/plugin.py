"""插件作者公开门面。

插件只应从这里导入基座类型::

    from sllkgui.plugin import (
        GalleryContext, GalleryShortcut, GalleryShortcuts, GalleryTray,
        Permission, Plugin, PluginError, ShortcutBinding,
    )
"""

from __future__ import annotations

from .gallery.api import (
    PLUGIN_API_VERSION,
    GalleryContext,
    GalleryShortcut,
    GalleryShortcuts,
    GalleryTray,
    Permission,
    Plugin,
    ShortcutBinding,
    ShortcutConflict,
)
from .gallery.errors import GalleryError as PluginError

__all__ = [
    "PLUGIN_API_VERSION",
    "GalleryContext",
    "GalleryShortcut",
    "GalleryShortcuts",
    "GalleryTray",
    "Permission",
    "Plugin",
    "PluginError",
    "ShortcutBinding",
    "ShortcutConflict",
]
