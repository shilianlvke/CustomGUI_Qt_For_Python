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


__all__ = ["SettingsChangeBus", "settings_change_bus"]
