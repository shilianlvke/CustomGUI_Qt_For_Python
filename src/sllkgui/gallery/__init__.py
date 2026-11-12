"""Gallery 插件运行时。

顶层只导出不依赖 PySide6 的模块，CLI 在无显示环境可直接使用；窗口相关符号
通过模块 ``__getattr__`` 惰性导入，避免 ``import sllkgui.gallery`` 时拉起 Qt。
"""

from __future__ import annotations

from typing import Any

from .api import PLUGIN_API_VERSION, GalleryContext, Permission, Plugin
from .defaults import DEFAULT_SOURCE_URL, GALLERY_DIRNAME, MANIFEST_NAME
from .errors import GalleryError
from .loader import discover_plugin_dirs, load_plugin
from .manager import PluginManager
from .manifest import DependencySpec, PluginManifest, SurfaceSpec, load_manifest
from .registry import GalleryRegistry, PluginRecord, SurfaceRecord, current_registry
from .runtime import GalleryRuntime
from .source import PluginEntry, SourceIndex, SourceManager, VersionEntry
from .state import InstalledPlugin, RegistryState, SourceRecord, SourcesState
from .store import GalleryStore

__all__ = [
    "DEFAULT_SOURCE_URL",
    "DependencySpec",
    "GALLERY_DIRNAME",
    "GalleryContext",
    "GalleryError",
    "GalleryRegistry",
    "GalleryRuntime",
    "GalleryStore",
    "InstalledPlugin",
    "MANIFEST_NAME",
    "PLUGIN_API_VERSION",
    "Permission",
    "Plugin",
    "PluginEntry",
    "PluginManager",
    "PluginManifest",
    "PluginRecord",
    "RegistryState",
    "SourceIndex",
    "SourceManager",
    "SourceRecord",
    "SourcesState",
    "SurfaceRecord",
    "SurfaceSpec",
    "VersionEntry",
    "current_registry",
    "discover_plugin_dirs",
    "load_manifest",
    "load_plugin",
]


def __getattr__(name: str) -> Any:
    if name in {"GalleryWindow", "load_gallery", "load_run"}:
        from . import window as _window

        return getattr(_window, name)
    raise AttributeError(name)
