"""插件级事件总线：按 owner 隔离订阅，卸载时只清自己的。

与 ``ctx.event``（单向遥测）不同，这里提供真正的发布/订阅。每个 runtime
持有一个实例，插件经 ``ctx.events`` 拿到绑定自身 ``plugin_id`` 的句柄；
订阅返回退订闭包，卸载时按 owner 批量注销，reload 后不留悬空回调。

实现范式来自 ``appcore/settings/events.py`` 的 SettingsChangeBus（RLock、
锁外快照回调、单订阅者异常隔离），但不复用那个进程级单例——它无 owner 维度、
绑定设置命名空间语义，无法满足插件生命周期需要。
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any

from sllkgui.appcore import Logger

from .api import GalleryEvents

EventListener = Callable[[str, Mapping[str, Any]], None]


class EventHandle(GalleryEvents):
    """绑定到单一 owner（plugin_id）的插件视图。"""

    def __init__(self, bus: PluginEventBus, owner: str) -> None:
        self._bus = bus
        self.owner = owner

    def subscribe(self, topic: str, callback: EventListener) -> Callable[[], None]:
        """订阅主题；返回幂等的退订闭包。"""
        return self._bus._subscribe(self.owner, topic, callback)

    def publish(self, topic: str, payload: Mapping[str, Any] | None = None) -> None:
        """向所有订阅者广播；携带 owner 供接收方识别来源。"""
        self._bus._publish(topic, self.owner, dict(payload or {}))

    def clear(self) -> None:
        """注销本 owner 的全部订阅（幂等）。"""
        self._bus.clear_owner(self.owner)


class PluginEventBus:
    """进程内事件总线（每 runtime 一个实例）。"""

    def __init__(self) -> None:
        self._subs: dict[str, list[tuple[str, EventListener]]] = {}
        self._lock = threading.RLock()

    def handle(self, owner: str) -> EventHandle:
        return EventHandle(self, owner)

    def _subscribe(self, owner: str, topic: str, callback: EventListener) -> Callable[[], None]:
        key = str(topic)
        with self._lock:
            self._subs.setdefault(key, []).append((owner, callback))

        def unsubscribe() -> None:
            with self._lock:
                items = self._subs.get(key)
                if not items:
                    return
                try:
                    items.remove((owner, callback))
                except ValueError:
                    return
                if not items:
                    self._subs.pop(key, None)

        return unsubscribe

    def _publish(self, topic: str, owner: str, payload: dict[str, Any]) -> None:
        with self._lock:
            listeners = list(self._subs.get(str(topic), ()))
        # 锁外回调：订阅者在回调里增删订阅不会死锁
        for sub_owner, callback in listeners:
            try:
                callback(topic, {"from": owner, **payload})
            except Exception as exc:  # noqa: BLE001 - 单订阅者失败不影响其它
                Logger.warning(f"插件事件回调失败 {topic} ({sub_owner}): {exc}")

    def clear_owner(self, owner: str) -> None:
        """只清指定 owner 的订阅，保留其它插件。"""
        with self._lock:
            for key in list(self._subs):
                kept = [(o, cb) for o, cb in self._subs[key] if o != owner]
                if kept:
                    self._subs[key] = kept
                else:
                    self._subs.pop(key, None)

    def clear(self) -> None:
        """整体清空（runtime 真正退出时调用）。"""
        with self._lock:
            self._subs.clear()


__all__ = ["EventHandle", "EventListener", "PluginEventBus"]
