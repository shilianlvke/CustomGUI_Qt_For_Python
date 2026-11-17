"""插件作者公开 API：生命周期、上下文与权限枚举。

本模块**不导入 PySide6**，`plugin.py`/`gallery` CLI 在无显示环境也能加载；
Surface 工厂返回值在类型层面只约束为 ``object``，实际必须是 ``QWidget``，
由加载器在运行期校验。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
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
    SHORTCUTS = "shortcuts"
    AUTOSTART = "autostart"
    SYSTEM_INFO = "system.info"


class GalleryTray(ABC):
    """基座托盘能力：全进程唯一图标，插件只注册动作与通知。

    托盘图标、悬停提示、菜单外壳（显示主窗口/退出）与生命周期全部由基座
    持有并常驻；插件**不得**修改图标或提示，也不得自建 ``QSystemTrayIcon``。
    插件只能在菜单里插入文本动作与发送系统通知，动作回调在 Qt 主线程执行。
    """

    @abstractmethod
    def available(self) -> bool:
        """当前环境是否支持系统托盘。"""

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


@dataclass(frozen=True)
class ShortcutBinding:
    """``ctx.shortcuts.bindings()`` 的只读条目（不含回调，可安全展示）。"""

    shortcut_id: str
    sequence: str
    display: str
    scope: str
    priority: int
    enabled: bool
    plugin_id: str = ""
    description: str = ""
    locked: bool = False


@dataclass(frozen=True)
class ShortcutConflict:
    """同一序列上的多条绑定；``winner`` 是派发时实际生效的一条。"""

    sequence: str
    shortcut_ids: tuple[str, ...] = ()
    owners: tuple[str, ...] = ()
    winner: str = ""


class GalleryShortcut(ABC):
    """单条快捷键句柄：启用/禁用、改序列、注销。"""

    @property
    @abstractmethod
    def shortcut_id(self) -> str: ...

    @property
    @abstractmethod
    def sequence(self) -> str: ...

    @property
    @abstractmethod
    def display(self) -> str:
        """面向用户的文本（macOS 为 ⌘K 这类符号，其余平台为 Ctrl+K）。"""

    @property
    @abstractmethod
    def enabled(self) -> bool: ...

    @abstractmethod
    def set_enabled(self, enabled: bool) -> None: ...

    @abstractmethod
    def update(
        self,
        *,
        sequence: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> bool: ...

    @abstractmethod
    def unregister(self) -> None: ...


class GalleryShortcuts(ABC):
    """插件快捷键能力：注册、更新、注销、查询与冲突观测。

    所有条目共用基座同一张注册表，与内置快捷键走同一条派发路径；插件条目
    默认优先级低于内置项，冲突策略为「拒绝」，因此不会覆盖或干扰内置行为。
    """

    @abstractmethod
    def available(self) -> bool:
        """当前环境是否可注册快捷键（无 Qt 应用时为 ``False``）。"""

    @abstractmethod
    def register(
        self,
        shortcut_id: str,
        sequence: str,
        callback: Callable[[], None],
        *,
        scope: str = "global",
        priority: int | None = None,
        description: str = "",
        allow_in_modal: bool = False,
        conflict: str = "error",
    ) -> GalleryShortcut:
        """注册快捷键。

        ``scope``：``global`` 全应用，``local`` 仅本插件 Surface 所在窗口；
        ``conflict``：``error`` 拒绝（默认）/ ``shadow`` 共存按优先级裁决 /
        ``replace`` 顶掉非锁定项。
        """

    @abstractmethod
    def update(
        self,
        shortcut_id: str,
        *,
        sequence: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> bool: ...

    @abstractmethod
    def set_enabled(self, shortcut_id: str, enabled: bool) -> bool: ...

    @abstractmethod
    def unregister(self, shortcut_id: str) -> bool: ...

    @abstractmethod
    def bindings(self) -> tuple[ShortcutBinding, ...]: ...

    @abstractmethod
    def conflicts(self) -> tuple[ShortcutConflict, ...]: ...

    @abstractmethod
    def clear(self) -> None:
        """移除本插件的全部快捷键（卸载时由加载器调用）。"""


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

    @property
    @abstractmethod
    def shortcuts(self) -> GalleryShortcuts:
        """基座快捷键表；需要在清单声明 ``shortcuts`` 权限（见 ``docs/SHORTCUTS.md``）。"""


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


__all__ = [
    "GalleryContext",
    "GalleryShortcut",
    "GalleryShortcuts",
    "GalleryTray",
    "PLUGIN_API_VERSION",
    "Permission",
    "Plugin",
    "ShortcutBinding",
    "ShortcutConflict",
]
