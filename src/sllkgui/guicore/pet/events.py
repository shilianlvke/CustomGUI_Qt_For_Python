"""桌面宠物事件总线与事件协议。

让基座与插件通过统一的发布/订阅机制控制宠物，而不是直接持有控制器引用。

范式沿用 gallery.events.PluginEventBus（owner 隔离 + RLock + 锁外快照回调 +
单订阅者异常隔离 + 幂等退订），但不 import gallery：guicore 不得反向依赖
上层。进程级单例由 :func:`pet_bus` 惰性提供，测试可 :func:`reset_pet_bus` 隔离。

协议要点：
- topic 形如 pet.<域>.<动作>，只接受 :data:`EVENT_TYPES` 中登记的类型；
- 载荷是 Mapping，总线强制注入 ``from``（发布者 owner）与 ``seq``（单调序号）；
- 未知载荷键原样保留，便于后续扩展而不破坏旧订阅者；
- 订阅返回幂等退订闭包；publish 永不向调用方抛订阅者异常。
"""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable, Mapping
from typing import Any

from sllkgui.appcore import Logger

PetEventListener = Callable[[str, dict[str, Any]], None]

#: 行为命令：发布后由宠物控制器执行（基座与插件都可发布）
CMD_SHOW = "pet.command.show"
CMD_HIDE = "pet.command.hide"
CMD_TOGGLE = "pet.command.toggle"
CMD_SPIN = "pet.command.spin"
CMD_HOP = "pet.command.hop"
CMD_BURST = "pet.command.burst"
CMD_STATE = "pet.command.state"
CMD_SHAPE = "pet.command.shape"
CMD_COLOR = "pet.command.color"
CMD_SETTING = "pet.command.setting"

#: 状态事件：宠物控制器发布，供基座/插件观察
EVT_READY = "pet.event.ready"
EVT_STATE_CHANGED = "pet.event.state_changed"
EVT_SHAPE_CHANGED = "pet.event.shape_changed"
EVT_COLOR_CHANGED = "pet.event.color_changed"
EVT_SETTING_CHANGED = "pet.event.setting_changed"
EVT_VISIBILITY_CHANGED = "pet.event.visibility_changed"

#: 全部合法事件类型。新增事件只需在此登记并（可选）给出载荷校验器。
EVENT_TYPES: frozenset[str] = frozenset(
    {
        CMD_SHOW,
        CMD_HIDE,
        CMD_TOGGLE,
        CMD_SPIN,
        CMD_HOP,
        CMD_BURST,
        CMD_STATE,
        CMD_SHAPE,
        CMD_COLOR,
        CMD_SETTING,
        EVT_READY,
        EVT_STATE_CHANGED,
        EVT_SHAPE_CHANGED,
        EVT_COLOR_CHANGED,
        EVT_SETTING_CHANGED,
        EVT_VISIBILITY_CHANGED,
    }
)

#: 命令事件前缀（控制器据此订阅通配主题）
COMMAND_PREFIX = "pet.command."

#: 各命令要求的载荷键；缺失时事件仍分发，但控制器会忽略无效命令
REQUIRED_PAYLOAD: dict[str, tuple[str, ...]] = {
    CMD_STATE: ("state",),
    CMD_SHAPE: ("shape",),
    CMD_COLOR: ("color",),
    CMD_SETTING: ("key", "value"),
}


def is_valid_topic(topic: str) -> bool:
    """主题是否属于已登记的事件类型。"""
    return str(topic) in EVENT_TYPES


class PetEventBus:
    """进程内宠物事件总线（按 owner 隔离订阅）。"""

    def __init__(self) -> None:
        self._subs: dict[str, list[tuple[str, PetEventListener]]] = {}
        self._lock = threading.RLock()
        self._seq = itertools.count(1)

    def handle(self, owner: str) -> PetEventHandle:
        """返回绑定到 owner 的句柄（插件传 plugin_id，基座传固定名）。"""
        return PetEventHandle(self, str(owner or "unknown"))

    def _subscribe(self, owner: str, topic: str, callback: PetEventListener) -> Callable[[], None]:
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
                    return  # 幂等
                if not items:
                    self._subs.pop(key, None)

        return unsubscribe

    def _publish(self, topic: str, owner: str, payload: Mapping[str, Any] | None) -> None:
        key = str(topic)
        if key not in EVENT_TYPES:
            Logger.warning(f"忽略未登记的宠物事件: {key} (from={owner})")
            return
        with self._lock:
            listeners = list(self._subs.get(key, ()))
            seq = next(self._seq)
        event: dict[str, Any] = {"from": owner, "seq": seq, **dict(payload or {})}
        # 锁外回调：订阅者在回调里增删订阅不会死锁
        for sub_owner, callback in listeners:
            try:
                callback(key, event)
            except Exception as exc:  # noqa: BLE001 - 单订阅者失败不影响其它
                Logger.warning(f"宠物事件回调失败 {key} ({sub_owner}): {exc}")

    def clear_owner(self, owner: str) -> None:
        """只清指定 owner 的订阅（幂等）。"""
        with self._lock:
            for key in list(self._subs):
                kept = [(o, cb) for o, cb in self._subs[key] if o != owner]
                if kept:
                    self._subs[key] = kept
                else:
                    self._subs.pop(key, None)

    def clear(self) -> None:
        """整体清空（测试隔离 / 运行时退出）。"""
        with self._lock:
            self._subs.clear()


class PetEventHandle:
    """绑定到单一 owner 的事件视图；对发布/订阅做协议校验。"""

    def __init__(self, bus: PetEventBus, owner: str) -> None:
        self._bus = bus
        self.owner = owner

    def subscribe(self, topic: str, callback: PetEventListener) -> Callable[[], None]:
        """订阅主题；topic 必须是已登记类型。返回幂等退订闭包。"""
        if not is_valid_topic(topic):
            Logger.warning(f"宠物事件订阅被拒（未登记类型）: {topic}")
            return lambda: None
        if not callable(callback):
            return lambda: None
        return self._bus._subscribe(self.owner, topic, callback)

    def publish(self, topic: str, payload: Mapping[str, Any] | None = None) -> bool:
        """发布事件；未登记类型或缺少必需载荷时返回 False，不抛异常。"""
        if not is_valid_topic(topic):
            Logger.warning(f"宠物事件发布被拒（未登记类型）: {topic}")
            return False
        data = dict(payload or {})
        required = REQUIRED_PAYLOAD.get(topic, ())
        if any(key not in data for key in required):
            Logger.warning(f"宠物事件发布被拒（缺少载荷 {required}）: {topic}")
            return False
        self._bus._publish(topic, self.owner, data)
        return True

    def clear(self) -> None:
        """注销本 owner 的全部订阅（幂等）。"""
        self._bus.clear_owner(self.owner)


_BUS: PetEventBus | None = None


def pet_bus() -> PetEventBus:
    """进程级宠物事件总线（惰性创建，不要求 QApplication）。"""
    global _BUS
    if _BUS is None:
        _BUS = PetEventBus()
    return _BUS


def reset_pet_bus() -> PetEventBus:
    """重建总线（测试隔离用）。"""
    global _BUS
    _BUS = PetEventBus()
    return _BUS


__all__ = [
    "COMMAND_PREFIX",
    "EVENT_TYPES",
    "PetEventBus",
    "PetEventHandle",
    "PetEventListener",
    "REQUIRED_PAYLOAD",
    "is_valid_topic",
    "pet_bus",
    "reset_pet_bus",
] + [name for name in globals() if name.startswith(("CMD_", "EVT_"))]
