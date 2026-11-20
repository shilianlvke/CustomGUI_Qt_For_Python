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

    from ..appcore.settings import SettingsPage


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


class TrayGroup(StrEnum):
    """托盘槽：基座声明次序、预算与展示形态，插件只能引用其中一个。

    - ``QUICK``：内联直达区，每插件至多 1 条，整体预算 5 条；
    - ``TOOLS``：默认槽，按插件分块；槽内出现第二个插件时各块收进子菜单；
    - ``STATUS``：只读状态区，恒为禁用态，预算 3 条。

    槽目录是封闭且只增不改的：不认识的槽直接报错，不做静默回落，避免插件
    以为注册成功却出现在别处。
    """

    QUICK = "quick"
    TOOLS = "tools"
    STATUS = "status"


@dataclass(frozen=True)
class TrayEntry:
    """``ctx.tray.entries()`` 的只读条目：声明了什么 + 实际渲染在哪里。"""

    action_id: str
    text: str
    group: str
    order: int
    enabled: bool
    plugin_id: str
    rendered_as: str
    """``inline`` 内联 / ``submenu`` 插件块子菜单 / ``bucket`` 兜底桶。"""

    path: tuple[str, ...] = ()
    """从菜单顶层到该动作的完整文案路径，便于测试与诊断。"""


class GalleryTray(ABC):
    """基座托盘能力：全进程唯一图标，插件只注册动作与通知。

    托盘图标、悬停提示、菜单外壳（显示主窗口/设置/退出）与生命周期全部由基座
    持有并常驻；插件**不得**修改图标或提示，也不得自建 ``QSystemTrayIcon``。
    插件只声明``动作属于哪个槽、排多前``，菜单里长什么样（内联 / 子菜单 /
    兜底桶）由基座按槽预算裁决，见 ``docs/TRAY.md``。
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
        group: str | TrayGroup = TrayGroup.TOOLS,
        submenu: bool | None = None,
        enabled: bool = True,
    ) -> None:
        """注册菜单动作；``action_id`` 在插件内唯一，重名覆盖。

        ``submenu`` 只表达偏好：``None`` 由基座按槽内块数裁决，``True`` 强制
        子菜单，``False`` 仅在独占该槽时生效（否则被忽略以保持形态统一）。
        """

    @abstractmethod
    def set_action_text(self, action_id: str, text: str) -> None:
        """更新动作文案（语言切换时调用）。"""

    @abstractmethod
    def set_action_enabled(self, action_id: str, enabled: bool) -> None:
        """更新动作可用态；``STATUS`` 槽恒为禁用。"""

    @abstractmethod
    def remove_action(self, action_id: str) -> None:
        """移除动作。"""

    @abstractmethod
    def entries(self) -> tuple[TrayEntry, ...]:
        """本插件动作在菜单中的实际落位（声明槽 + 渲染形态 + 路径）。"""

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
        """移除本插件的全部动作（卸载时由加载器调用）。"""


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


class GallerySettings(ABC):
    """插件设置能力：声明页面、读写配置、监听外部修改。

    插件只需在 ``on_load`` 里调用 :meth:`define` 声明一次页面，设置窗口就会
    自动出现对应条目；键统一带 ``plugin.<plugin_id>.`` 前缀，与基座和其它
    插件互不冲突。

    读写方法是**立即生效**的（插件运行时通常马上要用值）；设置窗口里的编辑
    则走统一的「保存 / 放弃」语义，保存后同样通过 :meth:`on_changed` 通知。
    """

    @abstractmethod
    def define(self, page: SettingsPage) -> None:
        """声明（或重新声明）本插件的设置页；重复调用会整体替换。"""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """读取配置值；未声明的键返回 ``default``。"""

    @abstractmethod
    def set(self, key: str, value: Any) -> bool:
        """校验并立即写入；失败返回 ``False``（不抛异常给业务代码）。"""

    @abstractmethod
    def reset(self, key: str) -> bool:
        """恢复声明默认值并立即写入。"""

    @abstractmethod
    def values(self) -> dict[str, Any]:
        """当前全部配置值的快照（短键 -> 值）。"""

    @abstractmethod
    def on_changed(self, callback: Callable[[str, Any], None]) -> Callable[[], None]:
        """订阅配置变更；返回取消订阅函数。"""

    @abstractmethod
    def refresh(self) -> None:
        """请求设置窗口重建本插件页（动作行 / 信息行内容变化后调用）。

        与 :meth:`on_changed` 不同，这里不携带值变化：插件在动作或后台任务
        结束后调用一次，让只读信息与动作状态保持最新。没有打开的设置窗口时
        调用是安全的空操作。
        """


class GalleryStorage(ABC):
    """插件契约化 KV 存储：只能读写清单 ``data:`` 中声明的键。

    值落在插件 ``data_dir/<key>.json``，由基座原子写；卸载保留磁盘数据，
    删除插件（purge）时一并清除。未声明的键抛 ``PLUGIN_STORAGE_KEY_UNDECLARED``。
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def set(self, key: str, value: Any) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def keys(self) -> tuple[str, ...]: ...

    @abstractmethod
    def path(self, key: str) -> Path: ...


class GalleryEvents(ABC):
    """插件级事件总线：按主题订阅 / 广播，订阅绑定 owner。

    ``publish`` 携带 ``from`` 字段标记发布者 plugin_id。与 :meth:`GalleryContext.event`
    的单向遥测不同，这里会真正分发给订阅者。
    """

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable[[str, Mapping[str, Any]], None]) -> Callable[[], None]:
        """订阅主题；返回幂等退订闭包。"""

    @abstractmethod
    def publish(self, topic: str, payload: Mapping[str, Any] | None = None) -> None:
        """广播主题事件。"""


class GalleryServices(ABC):
    """插件服务注册表：按 name 注册/解析本进程内的服务对象。

    服务名默认是提供者的 plugin_id；冒名（用别的 name 注册）被拒。消费关系
    用清单 ``dependencies`` 表达。仅本进程内可见，无跨进程协议。
    """

    @abstractmethod
    def register(self, service: Any, *, name: str | None = None) -> bool:
        """注册服务；名称缺省为 owner，重名异主返回 False。"""

    @abstractmethod
    def get(self, name: str) -> Any | None:
        """解析服务；未注册返回 None。"""

    @abstractmethod
    def has(self, name: str) -> bool:
        """服务是否已注册。"""

    @abstractmethod
    def unregister(self, name: str) -> None:
        """注销自己注册的服务（非 owner 的调用无效）。"""


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

    @property
    @abstractmethod
    def settings(self) -> GallerySettings:
        """统一设置能力：声明页面、读取 / 写入本插件配置。"""

    @property
    @abstractmethod
    def storage(self) -> GalleryStorage:
        """契约化 KV 存储：只能读写清单 ``data:`` 声明的键。"""

    @property
    @abstractmethod
    def events(self) -> GalleryEvents:
        """插件级事件总线：订阅主题与广播（与单向遥测 ``event`` 不同）。"""

    @property
    @abstractmethod
    def services(self) -> GalleryServices:
        """进程内服务注册表：按 name 注册/解析服务对象。"""


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

    def on_surface_enter(self, surface_id: str) -> None:  # noqa: B027 - 可选钩子
        """导航进入本插件 Surface 后调用；默认不处理。

        同一页重复打开不会重复触发；切走其它 Surface 或原生页时先调用
        :meth:`on_surface_leave`，再对新页调用本方法。
        """

    def on_surface_leave(self, surface_id: str) -> None:  # noqa: B027 - 可选钩子
        """离开 Surface（切走、切原生页或页面销毁）时调用；必须幂等。"""

    def on_unload(self) -> None:  # noqa: B027 - 可选钩子
        """Gallery 重载/退出前调用；必须幂等。"""


__all__ = [
    "GalleryContext",
    "GalleryEvents",
    "GalleryServices",
    "GallerySettings",
    "GalleryStorage",
    "GalleryShortcut",
    "GalleryShortcuts",
    "GalleryTray",
    "PLUGIN_API_VERSION",
    "Permission",
    "Plugin",
    "ShortcutBinding",
    "ShortcutConflict",
]
