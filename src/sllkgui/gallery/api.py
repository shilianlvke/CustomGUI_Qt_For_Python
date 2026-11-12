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
    TRAY = "tray"
    AUTOSTART = "autostart"
    SYSTEM_INFO = "system.info"


class GalleryTray(ABC):
    """基座托盘能力：全进程唯一图标，插件只注册动作与通知。

    由基座负责图标、菜单外壳（显示主窗口/退出）、生命周期与语言切换；
    插件不得自建 ``QSystemTrayIcon``。动作回调在 Qt 主线程执行。
    """

    @abstractmethod
    def available(self) -> bool:
        """当前环境是否支持系统托盘。"""

    @abstractmethod
    def set_icon(self, path: str | Path | None = None) -> bool:
        """设置托盘图标；传 ``None`` 恢复基座默认图标。路径必须在插件目录内。"""

    @abstractmethod
    def set_tooltip(self, text: str) -> None:
        """设置托盘悬停提示。"""

    @abstractmethod
    def add_action(
        self,
        action_id: str,
        text: str,
        callback: Callable[[], None],
        *,
        order: int = 100,
    ) -> None:
        """注册菜单动作；``action_id`` 在插件内唯一，重名覆盖。"""

    @abstractmethod
    def set_action_text(self, action_id: str, text: str) -> None:
        """更新动作文案（语言切换时调用）。"""

    @abstractmethod
    def remove_action(self, action_id: str) -> None:
        """移除动作。"""

    @abstractmethod
    def show_message(
        self,
        title: str,
        message: str,
        *,
        level: str = "info",
        timeout_ms: int = 4000,
    ) -> bool:
        """弹出系统通知；需要 ``notifications`` 权限。"""

    @abstractmethod
    def clear(self) -> None:
        """移除本插件的全部动作与图标设置（卸载时由加载器调用）。"""


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

    @property
    @abstractmethod
    def tray(self) -> GalleryTray:
        """基座托盘；需要在清单声明 ``tray`` 权限。"""


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


__all__ = ["GalleryContext", "GalleryTray", "PLUGIN_API_VERSION", "Permission", "Plugin"]
