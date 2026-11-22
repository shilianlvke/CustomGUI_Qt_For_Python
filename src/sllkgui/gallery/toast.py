"""插件侧 Toast 门面：作用域、遥测、卸载清理与回调隔离。

设计要点：

1. **不 import PySide6**。Qt 侧由组合根把 ``ToastBus`` 注入进来（鸭子类型），
   这样 CLI / 无 GUI 环境仍能 import 本模块，协议层也可以脱离事件循环单测。
2. 作用域固定为 ``plugin_id``：去重、限流、清理都以插件为边界，插件之间互不影响。
3. 回调在插件卸载后一律静默丢弃，避免热重载后闭包访问已销毁的控件。
"""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable, Mapping
from typing import Any

from sllkgui.appcore import Logger, record_event
from sllkgui.appcore.feedback import (
    DedupePolicy,
    ToastAction,
    ToastAnchor,
    ToastCode,
    ToastDismiss,
    ToastDismissReason,
    ToastLevel,
    ToastMode,
    ToastRequest,
    ToastResult,
    ToastState,
    normalize_anchor,
    normalize_dedupe,
    normalize_level,
    normalize_mode,
)

from .api import GalleryToast, ToastHandle

#: 当前实现支持的协议能力
_CAPABILITIES = frozenset(
    {"stack", "replace", "coalesce", "dedupe", "channels", "progress", "actions", "update"}
)


class _Handle(ToastHandle):
    """``ToastHandle`` 的通道实现：所有动作都回收敛到路由。"""

    def __init__(self, router: ToastRouter, plugin_id: str, result: ToastResult, request: ToastRequest) -> None:
        self._router = router
        self._plugin_id = plugin_id
        self._result = result
        self._request = request

    @property
    def toast_id(self) -> str:
        return self._result.toast_id

    @property
    def state(self) -> ToastState:
        if not self._result.ok:
            return ToastState.CLOSED
        return self._router.state_of(self.toast_id)

    @property
    def result(self) -> ToastResult:
        return self._result

    def update(
        self,
        *,
        text: str | None = None,
        title: str | None = None,
        level: ToastLevel | str | None = None,
        progress: float | None = None,
        life: int | None = None,
        persist: bool | None = None,
        actions: tuple[ToastAction, ...] | None = None,
        payload: Mapping[str, Any] | None = None,
        code: str | None = None,
        detail: str | None = None,
    ) -> ToastResult:
        patch: dict[str, Any] = {}
        if text is not None:
            patch["text"] = text
        if title is not None:
            patch["title"] = title
        if level is not None:
            patch["level"] = level
        if progress is not None:
            patch["progress"] = progress
        if life is not None:
            patch["life"] = life
        if persist is not None:
            patch["persist"] = persist
        if actions is not None:
            patch["actions"] = actions
        if payload is not None:
            patch["payload"] = payload
        if code is not None:
            patch["code"] = code
        if detail is not None:
            patch["detail"] = detail
        return self._router.update(self._plugin_id, self.toast_id, patch)

    def dismiss(
        self,
        reason: ToastDismissReason | str = ToastDismissReason.MANUAL,
        *,
        immediate: bool = False,
    ) -> bool:
        return self._router.dismiss(self._plugin_id, self.toast_id, reason, immediate=immediate)

    def on_dismiss(self, callback: Callable[[ToastDismiss], None]) -> Callable[[], None]:
        return self._router.add_dismiss_callback(self._plugin_id, self.toast_id, callback)

    def on_action(self, callback: Callable[[str], None]) -> Callable[[], None]:
        return self._router.add_action_callback(self._plugin_id, self.toast_id, callback)


class PluginToast(GalleryToast):
    """绑定到单个插件的提示通道。"""

    def __init__(self, router: ToastRouter, plugin_id: str) -> None:
        self._router = router
        self._plugin_id = plugin_id

    @property
    def protocol_version(self) -> int:
        return self._router.protocol_version

    def capabilities(self) -> frozenset[str]:
        return _CAPABILITIES if self._router.available() else frozenset()

    def show(
        self,
        text: str,
        *,
        title: str = "",
        level: ToastLevel | str = ToastLevel.INFO,
        detail: str = "",
        text_key: str = "",
        code: str = "",
        life: int | None = None,
        closable: bool = True,
        channel: str = "",
        mode: ToastMode | str = ToastMode.STACK,
        dedupe_key: str = "",
        dedupe: DedupePolicy | str = DedupePolicy.SUPPRESS,
        dedupe_window: int = 1200,
        anchor: ToastAnchor | str = ToastAnchor.AUTO,
        progress: float | None = None,
        actions: tuple[ToastAction, ...] = (),
        payload: Mapping[str, Any] | None = None,
        on_dismiss: Callable[[ToastDismiss], None] | None = None,
        on_action: Callable[[str], None] | None = None,
    ) -> ToastHandle:
        if not self._router.available():
            return _Handle(
                self._router,
                self._plugin_id,
                ToastResult(ok=False, code=str(ToastCode.HOST_UNAVAILABLE), state=ToastState.CLOSED),
                ToastRequest(text=str(text or "")),
            )
        toast_id = self._router.next_id(self._plugin_id)
        request = ToastRequest(
            text=str(text or ""),
            title=str(title or ""),
            level=normalize_level(level)[0],
            detail=str(detail or ""),
            text_key=str(text_key or ""),
            code=str(code or ""),
            life=life,
            closable=bool(closable),
            channel=str(channel or ""),
            mode=normalize_mode(mode),
            dedupe_key=str(dedupe_key or ""),
            dedupe=normalize_dedupe(dedupe),
            dedupe_window=int(dedupe_window),
            anchor=normalize_anchor(anchor),
            progress=progress,
            actions=tuple(actions or ()),
            payload=dict(payload or {}),
            scope=self._plugin_id,
            toast_id=toast_id,
            on_dismiss=self._router.dispatch_dismiss,
            on_action=lambda action_id, tid=toast_id: self._router.dispatch_action(tid, action_id),
        )
        if on_dismiss is not None:
            self._router.add_dismiss_callback(self._plugin_id, toast_id, on_dismiss)
        if on_action is not None:
            self._router.add_action_callback(self._plugin_id, toast_id, on_action)
        result = self._router.show(request)
        return _Handle(self._router, self._plugin_id, result, request)

    def dismiss(
        self,
        toast_id: str,
        reason: ToastDismissReason | str = ToastDismissReason.MANUAL,
        *,
        immediate: bool = False,
    ) -> bool:
        return self._router.dismiss(self._plugin_id, toast_id, reason, immediate=immediate)

    def clear(self, channel: str | None = None) -> int:
        return self._router.clear(self._plugin_id, channel)

    def active(self, channel: str | None = None) -> tuple[ToastHandle, ...]:
        return tuple(
            _Handle(
                self._router,
                self._plugin_id,
                ToastResult(ok=True, toast_id=toast_id, state=self._router.state_of(toast_id)),
                ToastRequest(text="", scope=self._plugin_id, toast_id=toast_id),
            )
            for toast_id in self._router.active(self._plugin_id, channel)
        )


class ToastRouter:
    """插件作用域 → 渲染总线的薄路由。

    ``host`` 只需提供 ``show(anchor, request)`` / ``update(toast_id, patch)`` /
    ``dismiss(toast_id, reason, immediate=...)`` / ``clear(scope=..., channel=...)`` /
    ``active(scope=..., channel=...)`` / ``state_of(toast_id)``；实现见
    ``guicore.feedback.toast_bus.ToastBus`` 与测试用的 :class:`RecordingHost`。
    """

    def __init__(self, host: Any | None = None) -> None:
        self._host = host
        self._scopes: dict[str, PluginToast] = {}
        self._alive: set[str] = set()
        self._dismiss_callbacks: dict[str, list[Callable[[ToastDismiss], None]]] = {}
        self._action_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._last_dismiss: dict[str, ToastDismiss] = {}
        self._seq = itertools.count(1)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # 装配
    # ------------------------------------------------------------------
    @property
    def protocol_version(self) -> int:
        from .api import TOAST_PROTOCOL_VERSION

        return TOAST_PROTOCOL_VERSION

    def bind(self, host: Any | None) -> None:
        """注入/替换渲染总线（组合根调用；``None`` 表示进入无 UI 模式）。"""
        self._host = host

    def available(self) -> bool:
        return self._host is not None

    def handle(self, plugin_id: str) -> PluginToast:
        """取得（并注册）某插件的提示通道。"""
        with self._lock:
            self._alive.add(plugin_id)
            toast = self._scopes.get(plugin_id)
            if toast is None:
                toast = PluginToast(self, plugin_id)
                self._scopes[plugin_id] = toast
            return toast

    def next_id(self, plugin_id: str) -> str:
        safe = "".join(ch if ch.isalnum() else "-" for ch in str(plugin_id or "base"))[:24]
        return f"t-{safe}-{next(self._seq)}"

    # ------------------------------------------------------------------
    # 转发
    # ------------------------------------------------------------------
    def show(self, request: ToastRequest) -> ToastResult:
        if self._host is None:
            return ToastResult(ok=False, code=str(ToastCode.HOST_UNAVAILABLE), state=ToastState.CLOSED)
        try:
            return self._host.show(request.anchor, request)
        except Exception as exc:  # noqa: BLE001 - 提示失败不得打断插件业务
            Logger.warning(f"toast 显示失败 [{request.scope}]: {exc}")
            return ToastResult(ok=False, code=str(ToastCode.HOST_UNAVAILABLE), state=ToastState.CLOSED)

    def update(self, plugin_id: str, toast_id: str, patch: dict[str, Any]) -> ToastResult:
        if not self._is_alive(plugin_id):
            return ToastResult(ok=False, code=str(ToastCode.PLUGIN_UNLOADED), toast_id=toast_id, state=ToastState.CLOSED)
        if self._host is None:
            return ToastResult(ok=False, code=str(ToastCode.HOST_UNAVAILABLE), toast_id=toast_id, state=ToastState.CLOSED)
        try:
            result = self._host.update(toast_id, patch)
        except Exception as exc:  # noqa: BLE001
            Logger.debug(f"toast 更新失败 [{plugin_id}:{toast_id}]: {exc}")
            return ToastResult(ok=False, code=str(ToastCode.UPDATING_CLOSED), toast_id=toast_id, state=ToastState.CLOSED)
        if result.ok and "progress" in patch:
            record_event(
                "toast.updated",
                category="plugin",
                payload={"plugin_id": plugin_id, "toast_id": toast_id, "progress": patch.get("progress")},
            )
        return result

    def dismiss(
        self,
        plugin_id: str,
        toast_id: str,
        reason: ToastDismissReason | str = ToastDismissReason.MANUAL,
        *,
        immediate: bool = False,
    ) -> bool:
        if not self._is_alive(plugin_id):
            return False
        if self._host is None:
            return False
        try:
            return bool(self._host.dismiss(toast_id, reason, immediate=immediate))
        except Exception as exc:  # noqa: BLE001
            Logger.debug(f"toast 关闭失败 [{plugin_id}:{toast_id}]: {exc}")
            return False

    def clear(self, plugin_id: str, channel: str | None = None) -> int:
        if self._host is None:
            return 0
        try:
            return int(self._host.clear(scope=plugin_id, channel=channel, reason=ToastDismissReason.CLEARED))
        except Exception as exc:  # noqa: BLE001
            Logger.debug(f"toast 清理失败 [{plugin_id}]: {exc}")
            return 0

    def active(self, plugin_id: str, channel: str | None = None) -> tuple[str, ...]:
        if self._host is None:
            return ()
        try:
            return tuple(self._host.active(scope=plugin_id, channel=channel))
        except Exception:  # noqa: BLE001
            return ()

    def state_of(self, toast_id: str) -> ToastState:
        if self._host is None:
            return ToastState.CLOSED
        try:
            return ToastState(str(self._host.state_of(toast_id)))
        except Exception:  # noqa: BLE001
            return ToastState.CLOSED

    # ------------------------------------------------------------------
    # 回调
    # ------------------------------------------------------------------
    def _is_alive(self, plugin_id: str) -> bool:
        return plugin_id in self._alive

    def add_dismiss_callback(
        self, plugin_id: str, toast_id: str, callback: Callable[[ToastDismiss], None]
    ) -> Callable[[], None]:
        with self._lock:
            if plugin_id in self._alive:
                self._dismiss_callbacks.setdefault(toast_id, []).append(callback)
            last = self._last_dismiss.get(toast_id)
        if last is not None:
            self._safe_call(callback, last)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._dismiss_callbacks.get(toast_id, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    def add_action_callback(
        self, plugin_id: str, toast_id: str, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        with self._lock:
            if plugin_id in self._alive:
                self._action_callbacks.setdefault(toast_id, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._action_callbacks.get(toast_id, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    def dispatch_dismiss(self, dismiss: ToastDismiss) -> None:
        """总线关闭回调的统一入口（也负责遥测）。"""
        with self._lock:
            callbacks = self._dismiss_callbacks.pop(dismiss.toast_id, [])
            self._last_dismiss[dismiss.toast_id] = dismiss
            if len(self._last_dismiss) > 64:
                self._last_dismiss.pop(next(iter(self._last_dismiss)))
        record_event(
            "toast.dismissed",
            category="plugin",
            payload={
                "toast_id": dismiss.toast_id,
                "reason": str(dismiss.reason),
                "level": str(dismiss.level),
                "code": dismiss.code,
                "repeat": dismiss.repeat,
                "duration_ms": dismiss.duration_ms,
                "by_user": dismiss.by_user,
            },
        )
        for callback in callbacks:
            self._safe_call(callback, dismiss)

    def dispatch_action(self, toast_id: str, action_id: str) -> None:
        with self._lock:
            callbacks = list(self._action_callbacks.get(toast_id, []))
        record_event(
            "toast.action",
            category="plugin",
            payload={"toast_id": toast_id, "action_id": action_id},
        )
        for callback in callbacks:
            self._safe_call(callback, action_id)

    @staticmethod
    def _safe_call(callback: Callable[[Any], None], payload: Any) -> None:
        try:
            callback(payload)
        except Exception as exc:  # noqa: BLE001 - 插件回调失败不影响基座
            Logger.debug(f"toast 回调失败: {exc}")

    # ------------------------------------------------------------------
    # 卸载 / 退出
    # ------------------------------------------------------------------
    def clear_plugin(self, plugin_id: str, reason: ToastDismissReason = ToastDismissReason.PLUGIN_UNLOADED) -> int:
        """插件卸载：关闭其全部提示并丢弃回调（幂等）。"""
        with self._lock:
            was_alive = plugin_id in self._alive
            self._alive.discard(plugin_id)
            for mapping in (self._dismiss_callbacks, self._action_callbacks):
                for toast_id in [key for key in mapping if key.startswith(self._id_prefix(plugin_id))]:
                    mapping.pop(toast_id, None)
        if not was_alive or self._host is None:
            return 0
        try:
            return int(self._host.clear(scope=plugin_id, channel=None, reason=reason))
        except Exception as exc:  # noqa: BLE001
            Logger.debug(f"卸载清理 toast 失败 [{plugin_id}]: {exc}")
            return 0

    def shutdown(self) -> None:
        """退出：清理全部作用域与回调。"""
        for plugin_id in list(self._scopes):
            self.clear_plugin(plugin_id)
        with self._lock:
            self._scopes.clear()
            self._alive.clear()
            self._dismiss_callbacks.clear()
            self._action_callbacks.clear()
            self._last_dismiss.clear()

    def _id_prefix(self, plugin_id: str) -> str:
        safe = "".join(ch if ch.isalnum() else "-" for ch in str(plugin_id or "base"))[:24]
        return f"t-{safe}-"


class RecordingHost:
    """测试用宿主：记录请求与更新，不创建任何 Qt 对象。

    与 ``ToastBus`` 的 6 个方法同名同义，可直接 ``ToastRouter(host=RecordingHost())``。
    """

    def __init__(self) -> None:
        self.requests: dict[str, ToastRequest] = {}
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.dismissals: list[tuple[str, str]] = []
        self.cleared: list[tuple[str | None, str | None]] = []
        self._seq = itertools.count(1)

    # -- 总线接口 ------------------------------------------------------
    def show(self, anchor: Any, request: ToastRequest) -> ToastResult:
        toast_id = request.toast_id or f"t-rec-{next(self._seq)}"
        self.requests[toast_id] = request
        return ToastResult(ok=True, code=str(ToastCode.OK), toast_id=toast_id)

    def update(self, toast_id: str, patch: dict[str, Any]) -> ToastResult:
        self.updates.append((toast_id, dict(patch)))
        if toast_id not in self.requests:
            return ToastResult(ok=False, code=str(ToastCode.UPDATING_CLOSED), toast_id=toast_id, state=ToastState.CLOSED)
        return ToastResult(ok=True, code=str(ToastCode.OK), toast_id=toast_id)

    def dismiss(self, toast_id: str, reason: Any = "manual", *, immediate: bool = False) -> bool:
        if toast_id not in self.requests:
            return False
        self.dismissals.append((toast_id, str(reason)))
        return True

    def clear(
        self,
        *,
        scope: str | None = None,
        channel: str | None = None,
        anchor: Any = None,
        reason: Any = "cleared",
    ) -> int:
        self.cleared.append((scope, channel))
        targets = [
            toast_id
            for toast_id, request in self.requests.items()
            if (scope is None or request.scope == scope) and (channel is None or request.channel == channel)
        ]
        for toast_id in targets:
            self.dismissals.append((toast_id, str(reason)))
        return len(targets)

    def active(self, *, scope: str | None = None, channel: str | None = None) -> tuple[str, ...]:
        return tuple(
            toast_id
            for toast_id, request in self.requests.items()
            if (scope is None or request.scope == scope) and (channel is None or request.channel == channel)
        )

    def state_of(self, toast_id: str) -> str:
        return str(ToastState.SHOWN if toast_id in self.requests else ToastState.CLOSED)

    # -- 测试辅助 ------------------------------------------------------
    def emit_dismiss(self, toast_id: str, reason: str = "timeout", *, by_user: bool = False) -> None:
        """模拟渲染层关闭，触发路由回调链。"""
        request = self.requests.get(toast_id)
        if request is None or request.on_dismiss is None:
            return
        request.on_dismiss(
            ToastDismiss(
                toast_id=toast_id,
                reason=ToastDismissReason(str(reason)),
                level=request.level,
                channel=request.channel,
                code=request.code,
                by_user=by_user,
            )
        )

    def emit_action(self, toast_id: str, action_id: str) -> None:
        request = self.requests.get(toast_id)
        if request is not None and request.on_action is not None:
            request.on_action(action_id)

    def last(self) -> ToastRequest | None:
        return next(reversed(self.requests.values()), None) if self.requests else None


__all__ = ["PluginToast", "RecordingHost", "ToastRouter"]
