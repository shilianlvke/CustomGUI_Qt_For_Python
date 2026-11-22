"""Toast 总线：通道、去重、溢出裁决、状态机与线程投递。

插件门面（``gallery.toast``）与原生页（``guis``）都走这里，``CToast`` 只负责画。
本模块不 import ``gallery`` / ``guis``：锚点由调用方给，主窗口/设置窗口取景器由
组合根注入（见 ``gallery/window.py``）。
"""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from PySide6.QtCore import QEvent, QMetaObject, QObject, QPoint, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QWidget

from sllkgui.appcore import Logger
from sllkgui.appcore.feedback import (
    MAX_PAYLOAD_BYTES,
    PERSISTENT_WATCHDOG_MS,
    DedupePolicy,
    ToastAnchor,
    ToastCode,
    ToastDismiss,
    ToastDismissReason,
    ToastLevel,
    ToastMode,
    ToastRequest,
    ToastResult,
    ToastState,
    channel_is_valid,
    clamp_actions,
    clamp_progress,
    clamp_text,
    clamp_title,
    compose_text,
    dedupe_key_for,
    normalize_anchor,
    normalize_dedupe,
    normalize_level,
    normalize_mode,
    resolve_life,
)

from ..custom_ui.feedback.toast import CToast

#: 限流窗口（秒）与次数
_RATE_WINDOW = 2.0
_RATE_LIMIT = 20
#: 锚点解析不到时的兜底顶部偏移（无标题栏的宿主）
_DEFAULT_OFFSET = 56


@dataclass
class ToastRecord:
    """一条已受理的 toast（总线的内部事实来源）。"""

    toast_id: str
    request: ToastRequest
    anchor: QWidget
    toast: CToast
    state: ToastState = ToastState.SHOWN
    repeat: int = 1
    shown_at: float = field(default_factory=time.monotonic)
    patches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def level(self) -> ToastLevel:
        return self.request.level

    @property
    def channel(self) -> str:
        return self.request.channel


def _feedback_settings() -> tuple[int, int, int, int]:
    """(base_life, limit, margin, spacing)，配置缺失时回落默认值。"""
    try:
        from sllkgui.appcore import AppSettings

        cfg = AppSettings.feedback
        return (
            int(cfg.toast_life),
            max(1, int(cfg.toast_max)),
            int(cfg.toast_margin),
            int(cfg.toast_spacing),
        )
    except Exception:
        return 3000, 4, 20, 8


class ToastBus(QObject):
    """按锚点窗口管理 toast 的生命周期。

    对外只暴露 5 个动作：``show`` / ``update`` / ``dismiss`` / ``clear`` / ``active``。
    """

    #: 新条已显示（payload: ToastRecord）
    shown = Signal(object)
    #: 条已关闭（payload: ToastDismiss）
    dismissed = Signal(object)
    #: 动作按钮被点击（payload: tuple[toast_id, action_id]）
    action = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._records: dict[str, ToastRecord] = {}
        #: 锚点 id → 该锚点上的 toast id（最新在前）
        self._order: dict[int, list[str]] = {}
        #: (scope, channel, key) → toast id
        self._by_key: dict[tuple[str, str, str], str] = {}
        #: (锚点 id, 通道) → toast id（replace/coalesce 用）
        self._by_channel: dict[tuple[int, str], str] = {}
        #: 锚点强引用：有 toast 时不允许窗口被回收导致位置计算失败
        self._anchors: dict[int, QWidget] = {}
        self._filtered: set[int] = set()
        self._main_getter: Callable[[], QWidget | None] | None = None
        self._settings_getter: Callable[[], QWidget | None] | None = None
        self._observers: list[Callable[[str, dict[str, Any]], None]] = []
        self._seq = itertools.count(1)
        self._rate: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._pending: list[tuple[ToastAnchor | str, ToastRequest]] = []
        self._pending_patches: dict[str, list[dict[str, Any]]] = {}
        self._watchdogs: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 依赖注入 / 观察
    # ------------------------------------------------------------------
    def set_sources(
        self,
        *,
        main: Callable[[], QWidget | None] | None = None,
        settings: Callable[[], QWidget | None] | None = None,
    ) -> None:
        """注入主窗口与设置窗口取景器（组合根调用）。"""
        if main is not None:
            self._main_getter = main
        if settings is not None:
            self._settings_getter = settings

    def observe(self, callback: Callable[[str, dict[str, Any]], None]) -> Callable[[], None]:
        """订阅总线事件（测试与诊断用）；返回退订函数。"""
        self._observers.append(callback)

        def unsubscribe() -> None:
            if callback in self._observers:
                self._observers.remove(callback)

        return unsubscribe

    def _notify(self, topic: str, payload: dict[str, Any]) -> None:
        for callback in list(self._observers):
            try:
                callback(topic, payload)
            except Exception as exc:  # noqa: BLE001 - 观察者失败不影响提示
                Logger.debug(f"toast observer 失败 {topic}: {exc}")

    # ------------------------------------------------------------------
    # 锚点
    # ------------------------------------------------------------------
    def resolve_anchor(self, anchor: ToastAnchor | str) -> QWidget | None:
        """按 ``auto/main/settings`` 解析锚点窗口。"""
        hint = normalize_anchor(anchor)
        if hint is ToastAnchor.SETTINGS:
            window = self._settings_getter() if self._settings_getter else None
            if window is not None:
                return self._top_level(window)
        main = self._main_getter() if self._main_getter else None
        if hint is ToastAnchor.MAIN:
            return self._top_level(main) if main is not None else self._fallback_window()
        # AUTO：活动模态窗口优先，其次活动窗口，最后主窗口
        app = QApplication.instance()
        if app is not None:
            modal = app.activeModalWidget()
            if modal is not None:
                return self._top_level(modal)
            active = app.activeWindow()
            if active is not None:
                return self._top_level(active)
        if main is not None:
            return self._top_level(main)
        return self._fallback_window()

    @staticmethod
    def _top_level(widget: QWidget) -> QWidget:
        try:
            return widget.window()
        except RuntimeError:  # 已销毁
            return widget

    @staticmethod
    def _fallback_window() -> QWidget | None:
        app = QApplication.instance()
        if app is None:
            return None
        for widget in app.topLevelWidgets():
            try:
                if widget.isVisible():
                    return widget.window()
            except RuntimeError:
                continue
        return None

    def _offset_for(self, anchor: QWidget) -> int:
        """标题栏避让：读 ``ui.title_bar`` 或设置窗口的 ``_title_bar``。"""
        bar = getattr(getattr(anchor, "ui", None), "title_bar", None)
        if bar is None:
            bar = getattr(anchor, "_title_bar", None)
        if bar is not None:
            try:
                height = int(bar.height())
            except RuntimeError:
                height = 0
            if height > 0:
                return height + 8
            return 0
        return _DEFAULT_OFFSET if self._main_getter is not None else 0

    # ------------------------------------------------------------------
    # 显示
    # ------------------------------------------------------------------
    def show(self, anchor: ToastAnchor | str = ToastAnchor.AUTO, request: ToastRequest | None = None) -> ToastResult:
        """受理一条提示；任何失败都折算成 ``ToastResult``，不抛异常。"""
        if request is None:
            return ToastResult(ok=False, code=str(ToastCode.EMPTY_TEXT))
        if QThread.currentThread() != self.thread():
            return self._show_async(anchor, request)
        return self._show_sync(anchor, request)

    def _show_async(self, anchor: ToastAnchor | str, request: ToastRequest) -> ToastResult:
        toast_id = request.toast_id or self._next_id(request.scope)
        prepared = replace(request, toast_id=toast_id, created_at=time.monotonic())
        with self._lock:
            self._pending.append((anchor, prepared))
        QMetaObject.invokeMethod(self, "_drain_pending", Qt.ConnectionType.QueuedConnection)
        return ToastResult(ok=True, code=str(ToastCode.QUEUED), toast_id=toast_id, state=ToastState.QUEUED)

    @Slot()
    def _drain_pending(self) -> None:
        with self._lock:
            pending, self._pending = self._pending, []
        for anchor, request in pending:
            self._show_sync(anchor, request)

    def _next_id(self, scope: str) -> str:
        safe = "".join(ch if ch.isalnum() else "-" for ch in str(scope or "base"))[:24]
        return f"t-{safe}-{next(self._seq)}"

    def _show_sync(self, anchor: ToastAnchor | str, request: ToastRequest) -> ToastResult:
        text, truncated = clamp_text(request.text)
        if not text:
            return ToastResult(ok=False, code=str(ToastCode.EMPTY_TEXT))
        level, invalid_level = normalize_level(request.level)
        channel = str(request.channel or "").strip()
        channel_ok = channel_is_valid(channel)
        if not channel_ok:
            channel = ""
        progress, progress_bad = clamp_progress(request.progress)
        base_life, limit, margin, spacing = _feedback_settings()
        life, life_clamped = resolve_life(level, request.life, base_life)
        actions = clamp_actions(request.actions)
        payload, payload_dropped = self._sanitize_payload(request.payload)
        toast_id = request.toast_id or self._next_id(request.scope)

        prepared = replace(
            request,
            text=text,
            title=clamp_title(request.title),
            level=level,
            channel=channel,
            progress=progress,
            life=life,
            actions=actions,
            payload=payload,
            toast_id=toast_id,
            created_at=request.created_at or time.monotonic(),
        )

        # 1) 去重（scope + channel + key）
        key = dedupe_key_for(prepared)
        dedupe_key = (prepared.scope, channel, key)
        existing_id = self._by_key.get(dedupe_key)
        if existing_id is not None and prepared.dedupe_window > 0:
            existing = self._records.get(existing_id)
            if existing is not None and not self._expired(existing):
                policy = normalize_dedupe(prepared.dedupe)
                if policy is DedupePolicy.SUPPRESS:
                    return ToastResult(
                        ok=True,
                        code=str(ToastCode.DUPLICATE_SUPPRESSED),
                        toast_id=existing.toast_id,
                        state=existing.state,
                        duplicate_of=existing.toast_id,
                    )
                if policy in (DedupePolicy.RESTART, DedupePolicy.COUNT):
                    existing.repeat += 1
                    self._apply_patch(existing, self._content_patch(prepared))
                    existing.toast.set_life(life)
                    self._watchdog(existing)
                    return ToastResult(
                        ok=True,
                        code=str(ToastCode.DUPLICATE_SUPPRESSED),
                        toast_id=existing.toast_id,
                        state=existing.state,
                        duplicate_of=existing.toast_id,
                    )
                # REPLACE：关掉旧的再走新建
                self.dismiss(existing.toast_id, ToastDismissReason.REPLACED, immediate=True)

        anchor_widget = self.resolve_anchor(anchor)
        if anchor_widget is None:
            return ToastResult(ok=False, code=str(ToastCode.NO_ANCHOR_WINDOW))
        anchor_key = id(anchor_widget)
        order = self._order.setdefault(anchor_key, [])

        # 2) 通道替换 / 合并
        mode = normalize_mode(prepared.mode)
        if channel and mode in (ToastMode.REPLACE, ToastMode.COALESCE):
            current_id = self._by_channel.get((anchor_key, channel))
            current = self._records.get(current_id) if current_id else None
            if current is not None:
                if mode is ToastMode.COALESCE:
                    current.repeat += 1
                    self._apply_patch(current, self._content_patch(prepared))
                    current.toast.set_life(life)
                    self._watchdog(current)
                    return ToastResult(
                        ok=True,
                        code=str(ToastCode.DUPLICATE_SUPPRESSED),
                        toast_id=current.toast_id,
                        state=current.state,
                        duplicate_of=current.toast_id,
                    )
                self.dismiss(current.toast_id, ToastDismissReason.REPLACED, immediate=True)
                order = self._order.setdefault(anchor_key, [])

        # 3) 限流（先于容量裁决：被限流的请求不应挤掉已经在显示的条）
        if not self._allow(prepared.scope):
            return ToastResult(ok=False, code=str(ToastCode.RATE_LIMITED))

        # 4) 容量与溢出
        if not self._make_room(anchor_widget, limit):
            return ToastResult(ok=False, code=str(ToastCode.STACK_FULL))

        code = str(ToastCode.OK)
        if truncated:
            code = str(ToastCode.TEXT_TRUNCATED)
        elif invalid_level:
            code = str(ToastCode.INVALID_LEVEL)
        elif life_clamped:
            code = str(ToastCode.LIFE_CLAMPED)
        elif progress_bad:
            code = str(ToastCode.PROGRESS_INVALID)
        elif not channel_ok:
            code = str(ToastCode.INVALID_CHANNEL)
        elif payload_dropped:
            code = str(ToastCode.PAYLOAD_DROPPED)

        toast = CToast(
            anchor_widget,
            composed_text(prepared, 1),
            prepared.title,
            prepared.level,
            life,
            self._offset_for(anchor_widget),
            progress=prepared.progress,
            actions=prepared.actions,
            closable=prepared.closable,
            detail=prepared.detail,
            toast_id=toast_id,
        )
        record = ToastRecord(
            toast_id=toast_id,
            request=prepared,
            anchor=anchor_widget,
            toast=toast,
            repeat=1,
        )
        self._records[toast_id] = record
        self._anchors[anchor_key] = anchor_widget
        order.insert(0, toast_id)
        if prepared.dedupe_window > 0:
            self._by_key[dedupe_key] = toast_id
        if channel:
            self._by_channel[(anchor_key, channel)] = toast_id
        self._watch_anchor(anchor_widget, anchor_key)
        self._bind(record)

        # 5) 落位 + 入场动画
        toast.adjustSize()
        self._reflow(anchor_widget)
        toast.animate_in(toast.pos())
        self._watchdog(record)

        for patch in self._pending_patches.pop(toast_id, []):
            self._apply_patch(record, patch)

        self._notify(
            "shown",
            {
                "toast_id": toast_id,
                "level": str(prepared.level),
                "channel": channel,
                "code": prepared.code,
                "repeat": 1,
                "persistent": life <= 0,
                "text_key": prepared.text_key,
                "length": len(prepared.text),
                "scope": prepared.scope,
            },
        )
        self.shown.emit(record)
        return ToastResult(ok=True, code=code, toast_id=toast_id, state=ToastState.SHOWN)

    # ------------------------------------------------------------------
    # 更新 / 关闭
    # ------------------------------------------------------------------
    def update(self, toast_id: str, patch: dict[str, Any]) -> ToastResult:
        """更新一条已显示的 toast；``patch`` 只接受协议字段。"""
        if QThread.currentThread() != self.thread():
            with self._lock:
                self._pending_patches.setdefault(toast_id, []).append(dict(patch))
            QMetaObject.invokeMethod(self, "_drain_pending", Qt.ConnectionType.QueuedConnection)
            return ToastResult(ok=True, code=str(ToastCode.QUEUED), toast_id=toast_id, state=ToastState.QUEUED)
        record = self._records.get(toast_id)
        if record is None:
            if toast_id:
                with self._lock:
                    self._pending_patches.setdefault(toast_id, []).append(dict(patch))
            return ToastResult(
                ok=False, code=str(ToastCode.UPDATING_CLOSED), toast_id=toast_id, state=ToastState.CLOSED
            )
        if record.state in (ToastState.DISMISSING, ToastState.CLOSED):
            return ToastResult(ok=False, code=str(ToastCode.UPDATING_CLOSED), toast_id=toast_id, state=record.state)
        self._apply_patch(record, patch)
        self._notify(
            "updated",
            {
                "toast_id": toast_id,
                "level": str(record.level),
                "progress": record.request.progress,
                "scope": record.request.scope,
            },
        )
        return ToastResult(ok=True, code=str(ToastCode.OK), toast_id=toast_id, state=record.state)

    def dismiss(
        self,
        toast_id: str,
        reason: ToastDismissReason | str = ToastDismissReason.MANUAL,
        *,
        immediate: bool = False,
    ) -> bool:
        record = self._records.get(toast_id)
        if record is None or record.state in (ToastState.DISMISSING, ToastState.CLOSED):
            return False
        record.state = ToastState.DISMISSING
        record.toast.dismiss(reason, immediate=immediate)
        return True

    def clear(
        self,
        *,
        scope: str | None = None,
        channel: str | None = None,
        anchor: ToastAnchor | str | None = None,
        reason: ToastDismissReason | str = ToastDismissReason.CLEARED,
    ) -> int:
        anchor_key = None
        if anchor is not None:
            widget = self.resolve_anchor(anchor)
            anchor_key = id(widget) if widget is not None else None
        targets = [
            record
            for record in list(self._records.values())
            if (scope is None or record.request.scope == scope)
            and (channel is None or record.channel == channel)
            and (anchor_key is None or id(record.anchor) == anchor_key)
        ]
        count = 0
        for record in targets:
            if self.dismiss(record.toast_id, reason, immediate=True):
                count += 1
        return count

    def active(self, *, scope: str | None = None, channel: str | None = None) -> tuple[str, ...]:
        return tuple(
            record.toast_id
            for record in self._records.values()
            if (scope is None or record.request.scope == scope) and (channel is None or record.channel == channel)
        )

    def state_of(self, toast_id: str) -> ToastState:
        """查询某条 toast 的当前状态；未知 id 视为已关闭。"""
        record = self._records.get(toast_id)
        return record.state if record is not None else ToastState.CLOSED

    # ------------------------------------------------------------------
    # 内部：绑定 / 关闭 / 重排
    # ------------------------------------------------------------------
    def _bind(self, record: ToastRecord) -> None:
        toast = record.toast
        toast.closed_reason.connect(lambda reason, tid=record.toast_id: self._on_closed(tid, reason))
        toast.action_triggered.connect(lambda action_id, tid=record.toast_id: self._on_action(tid, action_id))
        toast.resized.connect(lambda tid=record.toast_id: self._on_resized(tid))

    def _on_closed(self, toast_id: str, reason: str) -> None:
        record = self._records.pop(toast_id, None)
        if record is None:
            return
        try:
            dismiss_reason = ToastDismissReason(str(reason))
        except ValueError:
            dismiss_reason = ToastDismissReason.MANUAL
        record.state = ToastState.CLOSED
        anchor_key = id(record.anchor)
        order = self._order.get(anchor_key, [])
        if toast_id in order:
            order.remove(toast_id)
        if not order:
            self._order.pop(anchor_key, None)
        elif anchor_key in self._anchors:
            self._reflow(self._anchors[anchor_key])
        for key, value in list(self._by_key.items()):
            if value == toast_id:
                self._by_key.pop(key, None)
        for key, value in list(self._by_channel.items()):
            if value == toast_id:
                self._by_channel.pop(key, None)
        self._clear_watchdog(toast_id)

        dismiss = ToastDismiss(
            toast_id=toast_id,
            reason=dismiss_reason,
            level=record.level,
            channel=record.channel,
            code=record.request.code,
            repeat=record.repeat,
            duration_ms=int(max(0.0, time.monotonic() - record.shown_at) * 1000),
            by_user=dismiss_reason in (ToastDismissReason.MANUAL, ToastDismissReason.ACTION),
        )
        self._notify(
            "dismissed",
            {
                "toast_id": toast_id,
                "reason": str(dismiss.reason),
                "level": str(dismiss.level),
                "channel": dismiss.channel,
                "code": dismiss.code,
                "repeat": dismiss.repeat,
                "duration_ms": dismiss.duration_ms,
                "by_user": dismiss.by_user,
                "scope": record.request.scope,
            },
        )
        self.dismissed.emit(dismiss)
        self._invoke(record.request.on_dismiss, dismiss, label="on_dismiss")

    def _on_action(self, toast_id: str, action_id: str) -> None:
        record = self._records.get(toast_id)
        if record is None:
            return
        self._notify("action", {"toast_id": toast_id, "action_id": action_id, "scope": record.request.scope})
        self.action.emit((toast_id, action_id))
        self._invoke(record.request.on_action, action_id, label="on_action")

    def _on_resized(self, toast_id: str) -> None:
        record = self._records.get(toast_id)
        if record is None:
            return
        self._reflow(record.anchor)

    @staticmethod
    def _invoke(callback: Callable[[Any], None] | None, payload: Any, *, label: str) -> None:
        if callback is None:
            return
        try:
            callback(payload)
        except Exception as exc:  # noqa: BLE001 - 回调失败不得打断总线
            Logger.debug(f"toast {label} 回调失败: {exc}")

    def _watch_anchor(self, anchor: QWidget, anchor_key: int) -> None:
        if anchor_key in self._filtered:
            return
        self._filtered.add(anchor_key)
        anchor.installEventFilter(self)
        anchor.destroyed.connect(lambda *_, key=anchor_key: self._on_anchor_destroyed(key))

    def _on_anchor_destroyed(self, anchor_key: int) -> None:
        self._filtered.discard(anchor_key)
        self._anchors.pop(anchor_key, None)
        order = self._order.pop(anchor_key, [])
        for toast_id in order:
            record = self._records.pop(toast_id, None)
            if record is None:
                continue
            record.state = ToastState.CLOSED
            self._clear_watchdog(toast_id)
            dismiss = ToastDismiss(
                toast_id=toast_id,
                reason=ToastDismissReason.HOST_CLOSED,
                level=record.level,
                channel=record.channel,
                code=record.request.code,
                repeat=record.repeat,
                duration_ms=int(max(0.0, time.monotonic() - record.shown_at) * 1000),
            )
            try:
                self.dismissed.emit(dismiss)
            except RuntimeError:  # 退出路径：总线自身可能已随 QApplication 销毁
                pass
            self._invoke(record.request.on_dismiss, dismiss, label="on_dismiss")
        for key, value in list(self._by_key.items()):
            if value in order:
                self._by_key.pop(key, None)
        for key in list(self._by_channel):
            if key[0] == anchor_key:
                self._by_channel.pop(key, None)

    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if event.type() == QEvent.Type.Resize:
            anchor_key = id(watched)
            if anchor_key in self._order:
                self._reflow(watched)
        return super().eventFilter(watched, event)

    def _reflow(self, anchor: QWidget) -> None:
        """重排某锚点上的全部 toast（最新在最上面）。"""
        _, _, margin, spacing = _feedback_settings()
        order = self._order.get(id(anchor), [])
        y = margin + self._offset_for(anchor)
        for toast_id in order:
            record = self._records.get(toast_id)
            if record is None:
                continue
            toast = record.toast
            try:
                toast.move(anchor.width() - toast.width() - margin, y)
                y += toast.height() + spacing
            except RuntimeError:
                continue

    def _target_pos(self, anchor: QWidget, toast: CToast, order: list[str]) -> QPoint:
        """（保留）计算某条 toast 的目标位置；总线当前直接用 ``_reflow`` + ``toast.pos()``。"""
        _, _, margin, spacing = _feedback_settings()
        y = margin + self._offset_for(anchor)
        for toast_id in order:
            if toast_id == toast.toast_id():
                break
            record = self._records.get(toast_id)
            if record is not None:
                y += record.toast.height() + spacing
        return QPoint(anchor.width() - toast.width() - margin, y)

    # ------------------------------------------------------------------
    # 内部：容量 / 限流 / 补丁
    # ------------------------------------------------------------------
    def _make_room(self, anchor: QWidget, limit: int) -> bool:
        order = self._order.setdefault(id(anchor), [])
        while len(order) >= limit:
            victim = self._pick_victim(anchor, order)
            if victim is None:
                return False
            self.dismiss(victim.toast_id, ToastDismissReason.SUPERSEDED, immediate=True)
            order = self._order.setdefault(id(anchor), [])
        return True

    def _pick_victim(self, anchor: QWidget, order: list[str]) -> ToastRecord | None:
        """溢出裁决：同通道最旧 → 级别最低 → 最旧；error/带 action 永不挤出。"""
        oldest_first = list(reversed(order))
        candidates = [
            self._records[tid]
            for tid in oldest_first
            if tid in self._records
            and self._records[tid].level is not ToastLevel.ERROR
            and not self._records[tid].request.actions
        ]
        if not candidates:
            return None
        anchor_key = id(anchor)
        same_channel = [
            record for record in candidates if self._by_channel.get((anchor_key, record.channel)) == record.toast_id
        ]
        if same_channel:
            return same_channel[0]
        rank = {
            ToastLevel.NEUTRAL: 0,
            ToastLevel.INFO: 1,
            ToastLevel.SUCCESS: 2,
            ToastLevel.WARN: 3,
            ToastLevel.PROGRESS: 4,
            ToastLevel.LOADING: 4,
            ToastLevel.ERROR: 9,
        }
        return min(candidates, key=lambda record: (rank.get(record.level, 5), oldest_first.index(record.toast_id)))

    def _allow(self, scope: str) -> bool:
        now = time.monotonic()
        with self._lock:
            stamps = [stamp for stamp in self._rate.get(scope, []) if now - stamp <= _RATE_WINDOW]
            if len(stamps) >= _RATE_LIMIT:
                self._rate[scope] = stamps
                return False
            stamps.append(now)
            self._rate[scope] = stamps
            return True

    @staticmethod
    def _expired(record: ToastRecord) -> bool:
        window = record.request.dedupe_window / 1000.0
        return window > 0 and (time.monotonic() - record.shown_at) > window

    @staticmethod
    def _sanitize_payload(payload: Any) -> tuple[dict[str, Any], bool]:
        """清洗 payload；返回 ``(数据, 是否被丢弃)``。"""
        if not payload:
            return {}, False
        try:
            data = dict(payload)
        except (TypeError, ValueError):
            return {}, True
        text = str(data)
        if len(text.encode("utf-8", errors="ignore")) > MAX_PAYLOAD_BYTES:
            return {}, True
        try:
            import json

            json.dumps(data)
        except (TypeError, ValueError):
            return {}, True
        return data, False

    def _content_patch(self, request: ToastRequest) -> dict[str, Any]:
        return {
            "text": request.text,
            "title": request.title,
            "level": request.level,
            "progress": request.progress,
            "detail": request.detail,
            "actions": request.actions,
            "code": request.code,
            "payload": request.payload,
        }

    def _apply_patch(self, record: ToastRecord, patch: dict[str, Any]) -> None:
        """把协议字段补丁应用到记录与渲染器。"""
        changes: dict[str, Any] = {}
        if "text" in patch and patch["text"] is not None:
            text, _ = clamp_text(patch["text"])
            changes["text"] = text
        if "title" in patch and patch["title"] is not None:
            changes["title"] = clamp_title(patch["title"])
        if "detail" in patch and patch["detail"] is not None:
            changes["detail"] = str(patch["detail"])
        if "code" in patch and patch["code"] is not None:
            changes["code"] = str(patch["code"])
        if "payload" in patch and patch["payload"] is not None:
            changes["payload"] = self._sanitize_payload(patch["payload"])[0]
        if "level" in patch and patch["level"] is not None:
            level, _ = normalize_level(patch["level"])
            changes["level"] = level
        if "progress" in patch:
            progress, _ = clamp_progress(patch["progress"])
            changes["progress"] = progress
        if "actions" in patch and patch["actions"] is not None:
            changes["actions"] = clamp_actions(tuple(patch["actions"]))
        if "closable" in patch and patch["closable"] is not None:
            changes["closable"] = bool(patch["closable"])
        if "persist" in patch and patch["persist"] is not None:
            persist = bool(patch["persist"])
            changes["life"] = (
                0 if persist else resolve_life(changes.get("level", record.level), None, _feedback_settings()[0])[0]
            )
        if "life" in patch and patch["life"] is not None:
            level = changes.get("level", record.level)
            life, _ = resolve_life(level, int(patch["life"]), _feedback_settings()[0])
            changes["life"] = life

        if not changes:
            return
        request = replace(record.request, **changes)
        record.request = request
        record.state = ToastState.UPDATING
        level = request.level
        text = compose_text(request, record.repeat)
        height_changed = record.toast.set_content(
            text=text,
            title=request.title,
            severity=level,
            progress=request.progress,
            detail=request.detail,
            actions=request.actions,
            closable=request.closable,
        )
        if "life" in changes:
            record.toast.set_life(int(changes["life"]))
            self._watchdog(record)
        record.state = ToastState.SHOWN
        if height_changed:
            self._reflow(record.anchor)

    # ------------------------------------------------------------------
    # 看门狗：持久条未收敛时兜底关闭
    # ------------------------------------------------------------------
    def _watchdog(self, record: ToastRecord) -> None:
        self._clear_watchdog(record.toast_id)
        if record.request.life != 0:
            return
        from PySide6.QtCore import QTimer

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda tid=record.toast_id: self._on_leak(tid))
        timer.start(PERSISTENT_WATCHDOG_MS)
        self._watchdogs[record.toast_id] = timer

    def _clear_watchdog(self, toast_id: str) -> None:
        timer = self._watchdogs.pop(toast_id, None)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass

    def _on_leak(self, toast_id: str) -> None:
        record = self._records.get(toast_id)
        if record is None:
            return
        record.request = replace(record.request, code=str(ToastCode.LEAK_AUTO_CLOSED))
        Logger.warning(f"toast 未收敛，看门狗已关闭: {toast_id} ({record.request.scope})")
        self._notify(
            "leaked",
            {"toast_id": toast_id, "scope": record.request.scope, "channel": record.channel},
        )
        self.dismiss(toast_id, ToastDismissReason.FAILED, immediate=True)

    # ------------------------------------------------------------------
    # 测试/退出清理
    # ------------------------------------------------------------------
    def reset(self) -> int:
        """关闭全部 toast 并清空内部状态（测试与退出用）。"""
        count = 0
        for record in list(self._records.values()):
            if self.dismiss(record.toast_id, ToastDismissReason.CLEARED, immediate=True):
                count += 1
        self._records.clear()
        self._order.clear()
        self._by_key.clear()
        self._by_channel.clear()
        self._anchors.clear()
        self._filtered.clear()
        with self._lock:
            self._pending.clear()
            self._pending_patches.clear()
            self._rate.clear()
        for toast_id in list(self._watchdogs):
            self._clear_watchdog(toast_id)
        return count


_BUS: ToastBus | None = None


def toast_bus() -> ToastBus:
    """进程级 toast 总线（延迟创建，避免导入期要求 QApplication）。"""
    global _BUS
    if _BUS is None:
        _BUS = ToastBus()
    return _BUS


def reset_toast_bus() -> ToastBus:
    """重建总线；返回新实例（测试隔离用）。"""
    global _BUS
    if _BUS is not None:
        try:
            _BUS.reset()
            _BUS.deleteLater()
        except RuntimeError:
            pass
    _BUS = ToastBus()
    return _BUS


def composed_text(request: ToastRequest, repeat: int) -> str:
    """正文合成（供总线与门面共用，避免两处规则漂移）。"""
    return compose_text(request, repeat)


__all__ = [
    "ToastBus",
    "ToastRecord",
    "composed_text",
    "reset_toast_bus",
    "toast_bus",
]
