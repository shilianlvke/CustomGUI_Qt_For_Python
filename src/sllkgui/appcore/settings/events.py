"""设置变更总线：让插件感知「设置窗口保存」这类外部修改。

插件自己调用 ``ctx.settings.set()`` 时会直接收到通知；而用户在设置窗口里改
完点「保存」时，写入发生在会话层，插件运行时并不知情。总线按命名空间广播
``短键 -> 新值``，插件桥接层再转成自己的回调。

Qt-free、线程安全；回调异常只记日志，不影响保存流程。
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any

from ..sysx.modules.logger_module import Logger
from .schema import normalize_namespace

Listener = Callable[[Mapping[str, Any]], None]


class SettingsChangeBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Listener]] = {}
        self._lock = threading.RLock()

    def subscribe(self, namespace: str, callback: Listener) -> Callable[[], None]:
        target = normalize_namespace(namespace)
        with self._lock:
            self._listeners.setdefault(target, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                items = self._listeners.get(target)
                if not items:
                    return
                try:
                    items.remove(callback)
                except ValueError:
                    return
                if not items:
                    self._listeners.pop(target, None)

        return unsubscribe

    def publish(self, namespace: str, changes: Mapping[str, Any]) -> None:
        if not changes:
            return
        target = normalize_namespace(namespace)
        with self._lock:
            listeners = list(self._listeners.get(target, ()))
        for callback in listeners:
            try:
                callback(dict(changes))
            except Exception as exc:  # noqa: BLE001 - 单个订阅者失败不影响其它人
                Logger.warning(f"设置变更回调失败: {target}: {exc}")

    def clear(self, namespace: str | None = None) -> None:
        with self._lock:
            if namespace is None:
                self._listeners.clear()
            else:
                self._listeners.pop(normalize_namespace(namespace), None)


_BUS = SettingsChangeBus()


def settings_change_bus() -> SettingsChangeBus:
    return _BUS


PageListener = Callable[[str], None]
ScopedPageListener = Callable[[], None]


class SettingsPageBus:
    """页面变更总线：插件请求重建自己的设置页。

    与值变更总线分开：动作行 / 信息行的内容不进入存储，只是「页面该重新
    生成一遍」的信号。订阅可以按命名空间精确订阅，也可以全局订阅（设置
    窗口使用后者，无需预先知道有哪些插件）。
    """

    def __init__(self) -> None:
        self._scoped: dict[str, list[ScopedPageListener]] = {}
        self._global: list[PageListener] = []
        self._lock = threading.RLock()

    def subscribe(self, namespace: str, callback: ScopedPageListener) -> Callable[[], None]:
        target = normalize_namespace(namespace)
        with self._lock:
            self._scoped.setdefault(target, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                items = self._scoped.get(target)
                if not items:
                    return
                try:
                    items.remove(callback)
                except ValueError:
                    return
                if not items:
                    self._scoped.pop(target, None)

        return unsubscribe

    def subscribe_all(self, callback: PageListener) -> Callable[[], None]:
        with self._lock:
            self._global.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                try:
                    self._global.remove(callback)
                except ValueError:
                    return

        return unsubscribe

    def notify(self, namespace: str) -> None:
        target = normalize_namespace(namespace)
        with self._lock:
            scoped = list(self._scoped.get(target, ()))
            listeners = list(self._global)
        for callback in scoped:
            try:
                callback()
            except Exception as exc:  # noqa: BLE001 - 单个订阅者失败不影响其它人
                Logger.warning(f"设置页刷新回调失败: {target}: {exc}")
        for callback in listeners:
            try:
                callback(target)
            except Exception as exc:  # noqa: BLE001 - 单个订阅者失败不影响其它人
                Logger.warning(f"设置页刷新监听失败: {target}: {exc}")

    def clear(self, namespace: str | None = None) -> None:
        with self._lock:
            if namespace is None:
                self._scoped.clear()
                self._global.clear()
            else:
                self._scoped.pop(normalize_namespace(namespace), None)


_PAGE_BUS = SettingsPageBus()


def settings_page_bus() -> SettingsPageBus:
    return _PAGE_BUS


__all__ = ["SettingsChangeBus", "SettingsPageBus", "settings_change_bus", "settings_page_bus"]
