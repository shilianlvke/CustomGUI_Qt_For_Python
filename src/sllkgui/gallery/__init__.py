"""Gallery 插件运行时。

顶层只导出**轻量**符号（协议、清单、错误码、状态结构），重依赖模块
（加载器、依赖安装、Git 后端、窗口）一律通过模块 ``__getattr__`` 惰性导入。

这样做的直接目的：``import sllkgui.gallery.lint`` 不再连带拉起
``loader`` → ``dependencies`` → ``yaml`` / ``packaging`` 之外的整条链，
插件规范校验可以在只装了最少依赖的环境里跑（源仓库 CI 的准入场景）。
"""

from __future__ import annotations

from typing import Any

from .api import PLUGIN_API_VERSION, GalleryContext, Permission, Plugin
from .defaults import DEFAULT_SOURCE_URL, GALLERY_DIRNAME, MANIFEST_NAME
from .errors import GalleryError
from .manifest import DependencySpec, PluginManifest, SurfaceSpec, load_manifest
from .registry import GalleryRegistry, PluginRecord, SurfaceRecord, current_registry
from .state import InstalledPlugin, RegistryState, SourceRecord, SourcesState

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
    """惰性导出重依赖模块的符号。

    延迟到真正访问时才 import，``import sllkgui.gallery`` 因此保持轻量：
    既不拉起 Qt，也不拉起依赖安装 / Git 后端等重链路。
    """
    if name in {"GalleryWindow", "load_gallery", "load_run"}:
        from . import window as _window

        return getattr(_window, name)
    if name in {"discover_plugin_dirs", "load_plugin"}:
        from . import loader as _loader

        return getattr(_loader, name)
    if name == "PluginManager":
        from .manager import PluginManager

        return PluginManager
    if name == "GalleryRuntime":
        from .runtime import GalleryRuntime

        return GalleryRuntime
    if name == "GalleryStore":
        from .store import GalleryStore

        return GalleryStore
    if name in {"PluginEntry", "SourceIndex", "SourceManager", "VersionEntry"}:
        from . import source as _source

        return getattr(_source, name)
    raise AttributeError(name)
