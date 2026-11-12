"""插件作者公开 API：生命周期、上下文与权限枚举。

本模块**不导入 PySide6**，`plugin.py`/`gallery` CLI 在无显示环境也能加载；
Surface 工厂返回值在类型层面只约束为 ``object``，实际必须是 ``QWidget``，
由加载器在运行期校验。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .defaults import PLUGIN_API_VERSION as PLUGIN_API_VERSION

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    import logging

    from PySide6.QtWidgets import QWidget


class Permission(StrEnum):
    """声明式权限：安装前展示，用于知情同意，不是沙箱。"""

    NETWORK = "network"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    SUBPROCESS = "subprocess"
    CLIPBOARD = "clipboard"
    NOTIFICATIONS = "notifications"
    AUTOSTART = "autostart"
    SYSTEM_INFO = "system.info"


class GalleryContext(ABC):
    """插件运行上下文：所有基座能力都从这里进入。"""

    @property
    @abstractmethod
    def plugin_id(self) -> str: ...

    @property
    @abstractmethod
    def plugin_version(self) -> str: ...

    @property
    @abstractmethod
    def data_dir(self) -> Path: ...

    @property
    @abstractmethod
    def cache_dir(self) -> Path: ...

    @property
    @abstractmethod
    def locale(self) -> str: ...

    @property
    @abstractmethod
    def theme(self) -> str: ...

    @property
    @abstractmethod
    def permissions(self) -> tuple[Permission, ...]: ...

    @abstractmethod
    def resource(self, *parts: str) -> Path: ...

    @abstractmethod
    def open_surface(self, surface_id: str) -> bool: ...

    @abstractmethod
    def text(self, key: str, default: str | None = None, **kwargs: Any) -> str: ...

    @abstractmethod
    def log(self, message: str, level: str = "info") -> None: ...

    @property
    @abstractmethod
    def logger(self) -> logging.Logger: ...

    @abstractmethod
    def event(self, name: str, payload: Mapping[str, Any] | None = None, level: str = "info") -> None: ...

    @abstractmethod
    def timing(self, name: str, payload: Mapping[str, Any] | None = None) -> AbstractContextManager[None]: ...

    @abstractmethod
    def report_error(self, code: str, message: str, detail: str | None = None) -> None: ...

    @abstractmethod
    def parent_window(self) -> QWidget | None: ...


class Plugin(ABC):
    """插件基类。唯一合法入口是模块级 ``PLUGIN`` 实例。"""

    @abstractmethod
    def on_load(self, ctx: GalleryContext) -> None:
        """Surface 构建前调用一次。"""

    @abstractmethod
    def surfaces(self) -> Mapping[str, Callable[[GalleryContext], QWidget]]:
        """返回 ``{surface_id: factory}``。"""

    def on_locale_changed(self, locale: str) -> None:  # noqa: B027 - 可选钩子
        """语言切换后调用；默认不处理。"""

    def on_unload(self) -> None:  # noqa: B027 - 可选钩子
        """Gallery 重载/退出前调用；必须幂等。"""


__all__ = ["GalleryContext", "Permission", "Plugin"]
