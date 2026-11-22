"""Toast 协议的中立数据模型（无 Qt、无 UI 依赖）。

这里只放**协议本身**：类型、请求/回执/关闭载荷、级别归一、时长与文案钳制。
渲染在 :mod:`sllkgui.guicore.feedback.toast_bus`，插件门面在
:mod:`sllkgui.gallery.toast`，两者都依赖本模块，避免 guicore 反向 import gallery。

设计约束：

1. 所有校验函数**不抛异常**，把"非法输入"折算成协议码 + 兜底值。toast 是反馈
   通道，任何非法参数都不应该打断调用方的业务逻辑。
2. 模型是 ``frozen dataclass``，可安全跨线程传递；回调只作为字段携带，
   实际执行线程由渲染层保证（GUI 线程）。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

#: 协议版本；插件可用 ``ctx.toast.protocol_version`` 探测
TOAST_PROTOCOL_VERSION = 1

#: 正文硬上限（字符）。超过即截断，并回传 ``TOAST_TEXT_TRUNCATED``
MAX_TEXT_CHARS = 500
#: 标题上限
MAX_TITLE_CHARS = 64
#: 单条 toast 的动作按钮上限
MAX_ACTIONS = 2
#: 非持久 toast 的时长上限（毫秒）
MAX_LIFE_MS = 15_000
#: 持久 toast 的看门狗（毫秒）：未收敛的 loading/progress 会被强制关闭
PERSISTENT_WATCHDOG_MS = 120_000
#: payload 序列化后的字节上限（超出丢弃）
MAX_PAYLOAD_BYTES = 1024


class ToastLevel(StrEnum):
    """提示级别。语义与默认时长见 ``docs/TOAST.md`` §4.1。"""

    SUCCESS = "success"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    NEUTRAL = "neutral"
    LOADING = "loading"
    PROGRESS = "progress"


class ToastMode(StrEnum):
    """通道内的并发模式。"""

    STACK = "stack"
    REPLACE = "replace"
    COALESCE = "coalesce"


class DedupePolicy(StrEnum):
    """同键重复提示的处理策略。"""

    SUPPRESS = "suppress"
    RESTART = "restart"
    COUNT = "count"
    REPLACE = "replace"


class ToastState(StrEnum):
    """句柄生命周期状态。"""

    QUEUED = "queued"
    SHOWN = "shown"
    UPDATING = "updating"
    DISMISSING = "dismissing"
    CLOSED = "closed"


class ToastDismissReason(StrEnum):
    """关闭原因；回调与遥测共用。"""

    TIMEOUT = "timeout"
    MANUAL = "manual"
    REPLACED = "replaced"
    CLEARED = "cleared"
    SUPERSEDED = "superseded"
    ACTION = "action"
    HOST_CLOSED = "host_closed"
    PLUGIN_UNLOADED = "plugin_unloaded"
    FAILED = "failed"


class ToastAnchor(StrEnum):
    """锚点窗口选择。"""

    AUTO = "auto"
    MAIN = "main"
    SETTINGS = "settings"


class ToastCode(StrEnum):
    """协议结果码（稳定字符串，可直接进日志与断言）。"""

    OK = "TOAST_OK"
    QUEUED = "TOAST_QUEUED"
    DUPLICATE_SUPPRESSED = "TOAST_DUPLICATE_SUPPRESSED"
    TEXT_TRUNCATED = "TOAST_TEXT_TRUNCATED"
    LIFE_CLAMPED = "TOAST_LIFE_CLAMPED"
    INVALID_LEVEL = "TOAST_INVALID_LEVEL"
    PROGRESS_INVALID = "TOAST_PROGRESS_INVALID"
    PAYLOAD_DROPPED = "TOAST_PAYLOAD_DROPPED"
    ACTION_UNSUPPORTED = "TOAST_ACTION_UNSUPPORTED"
    INVALID_CHANNEL = "TOAST_INVALID_CHANNEL"
    STACK_FULL = "TOAST_STACK_FULL"
    RATE_LIMITED = "TOAST_RATE_LIMITED"
    EMPTY_TEXT = "TOAST_EMPTY_TEXT"
    NO_ANCHOR_WINDOW = "TOAST_NO_ANCHOR_WINDOW"
    HOST_UNAVAILABLE = "TOAST_HOST_UNAVAILABLE"
    NOOP = "TOAST_NOOP"
    UPDATING_CLOSED = "TOAST_UPDATING_CLOSED"
    PLUGIN_UNLOADED = "TOAST_PLUGIN_UNLOADED"
    LEAK_AUTO_CLOSED = "TOAST_LEAK_AUTO_CLOSED"
    STRICT_VIOLATION = "TOAST_STRICT_VIOLATION"


@dataclass(frozen=True)
class ToastAction:
    """toast 上的一个动作按钮。"""

    action_id: str
    text: str
    style: str = "secondary"  # secondary | primary | danger
    dismiss: bool = True


@dataclass(frozen=True)
class ToastResult:
    """受理结果。``ok=False`` 表示这条提示不会出现在界面上。"""

    ok: bool
    code: str = str(ToastCode.OK)
    toast_id: str = ""
    state: ToastState = ToastState.SHOWN
    duplicate_of: str = ""

    @property
    def shown(self) -> bool:
        """是否已可见（含去重复用）。"""
        return self.ok and bool(self.toast_id) and self.state in (ToastState.SHOWN, ToastState.UPDATING)


@dataclass(frozen=True)
class ToastDismiss:
    """关闭载荷：回调与遥测的唯一事实来源。"""

    toast_id: str
    reason: ToastDismissReason
    level: ToastLevel = ToastLevel.INFO
    channel: str = ""
    code: str = ""
    repeat: int = 1
    duration_ms: int = 0
    by_user: bool = False


@dataclass(frozen=True)
class ToastRequest:
    """一次提示请求（渲染层与插件门面共用）。"""

    text: str
    title: str = ""
    level: ToastLevel = ToastLevel.INFO
    detail: str = ""
    text_key: str = ""
    code: str = ""
    life: int | None = None
    closable: bool = True
    channel: str = ""
    mode: ToastMode = ToastMode.STACK
    dedupe_key: str = ""
    dedupe: DedupePolicy = DedupePolicy.SUPPRESS
    dedupe_window: int = 1200
    anchor: ToastAnchor = ToastAnchor.AUTO
    progress: float | None = None
    actions: tuple[ToastAction, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    scope: str = "base"
    toast_id: str = ""
    created_at: float = 0.0
    on_dismiss: Callable[[ToastDismiss], None] | None = None
    on_action: Callable[[str], None] | None = None


#: 级别 → (默认时长系数, 是否常驻)。系数以 ``feedback.toast_life`` 为基准。
_LIFE_FACTOR: dict[ToastLevel, tuple[float, bool]] = {
    ToastLevel.SUCCESS: (1.0, False),
    ToastLevel.INFO: (1.0, False),
    ToastLevel.WARN: (2.0, False),
    ToastLevel.ERROR: (2.6, False),
    ToastLevel.NEUTRAL: (0.66, False),
    ToastLevel.LOADING: (0.0, True),
    ToastLevel.PROGRESS: (0.0, True),
}

_LEVEL_ALIASES: dict[str, ToastLevel] = {
    "success": ToastLevel.SUCCESS,
    "ok": ToastLevel.SUCCESS,
    "info": ToastLevel.INFO,
    "information": ToastLevel.INFO,
    "primary": ToastLevel.INFO,
    "help": ToastLevel.INFO,
    "warn": ToastLevel.WARN,
    "warning": ToastLevel.WARN,
    "error": ToastLevel.ERROR,
    "danger": ToastLevel.ERROR,
    "critical": ToastLevel.ERROR,
    "fatal": ToastLevel.ERROR,
    "neutral": ToastLevel.NEUTRAL,
    "secondary": ToastLevel.NEUTRAL,
    "contrast": ToastLevel.NEUTRAL,
    "loading": ToastLevel.LOADING,
    "progress": ToastLevel.PROGRESS,
}

_MODE_ALIASES = {item.value: item for item in ToastMode}
_DEDUPE_ALIASES = {item.value: item for item in DedupePolicy}
_ANCHOR_ALIASES = {item.value: item for item in ToastAnchor}


def normalize_level(value: str | ToastLevel | None) -> tuple[ToastLevel, bool]:
    """归一提示级别；返回 ``(级别, 是否发生非法回落)``。"""
    if isinstance(value, ToastLevel):
        return value, False
    key = str(value or "").strip().lower()
    level = _LEVEL_ALIASES.get(key)
    if level is None:
        return ToastLevel.INFO, True
    # 别名命中不算非法（error/danger/warning 都是合法写法）
    return level, False


def normalize_mode(value: str | ToastMode | None) -> ToastMode:
    if isinstance(value, ToastMode):
        return value
    return _MODE_ALIASES.get(str(value or "").strip().lower(), ToastMode.STACK)


def normalize_dedupe(value: str | DedupePolicy | None) -> DedupePolicy:
    if isinstance(value, DedupePolicy):
        return value
    return _DEDUPE_ALIASES.get(str(value or "").strip().lower(), DedupePolicy.SUPPRESS)


def normalize_anchor(value: str | ToastAnchor | None) -> ToastAnchor:
    if isinstance(value, ToastAnchor):
        return value
    return _ANCHOR_ALIASES.get(str(value or "").strip().lower(), ToastAnchor.AUTO)


def is_persistent(level: ToastLevel) -> bool:
    """该级别是否必须常驻（loading/progress）。"""
    return _LIFE_FACTOR[level][1]


def default_life(level: ToastLevel, base_life: int) -> int:
    """按级别推导默认时长（毫秒）；常驻级别返回 0。"""
    factor, persistent = _LIFE_FACTOR[level]
    if persistent:
        return 0
    base = max(0, int(base_life))
    if level is ToastLevel.ERROR:
        return min(MAX_LIFE_MS, max(3000, min(8000, int(base * factor))))
    if level is ToastLevel.NEUTRAL:
        return max(1500, int(base * factor))
    return max(800, int(base * factor))


def resolve_life(level: ToastLevel, life: int | None, base_life: int) -> tuple[int, bool]:
    """解析最终时长；返回 ``(毫秒, 是否被钳制)``。

    ``life=0`` 表示常驻；常驻级别（loading/progress）无论传什么都按 0 处理。
    """
    if is_persistent(level):
        return 0, bool(life)
    if life is None:
        return default_life(level, base_life), False
    value = max(0, int(life))
    if value == 0:
        return 0, False
    if value > MAX_LIFE_MS:
        return MAX_LIFE_MS, True
    return value, False


def clamp_text(text: str) -> tuple[str, bool]:
    """裁剪正文；返回 ``(文本, 是否截断)``。"""
    value = str(text or "").strip()
    if len(value) <= MAX_TEXT_CHARS:
        return value, False
    return value[: MAX_TEXT_CHARS - 1] + "…", True


def clamp_title(title: str) -> str:
    value = str(title or "").strip().replace("\n", " ")
    return value if len(value) <= MAX_TITLE_CHARS else value[: MAX_TITLE_CHARS - 1] + "…"


def clamp_progress(value: float | None) -> tuple[float | None, bool]:
    """把进度钳到 [0, 1]；``None`` 表示不确定进度。"""
    if value is None:
        return None, False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, True
    clamped = max(0.0, min(1.0, number))
    return clamped, abs(clamped - number) > 1e-9


def clamp_actions(actions: tuple[ToastAction, ...] | list[ToastAction]) -> tuple[ToastAction, ...]:
    """最多保留 2 个动作，丢弃无文案/无 id 的项。"""
    result: list[ToastAction] = []
    for item in actions or ():
        if not isinstance(item, ToastAction):
            continue
        action_id = str(item.action_id or "").strip()
        text = str(item.text or "").strip()
        if not action_id or not text:
            continue
        result.append(
            ToastAction(
                action_id=action_id,
                text=text,
                style=str(item.style or "secondary"),
                dismiss=bool(item.dismiss),
            )
        )
        if len(result) >= MAX_ACTIONS:
            break
    return tuple(result)


def channel_is_valid(channel: str) -> bool:
    """通道名规范：``^[a-z0-9][a-z0-9._-]{0,47}$``（空串表示默认通道）。"""
    import re

    if not channel:
        return True
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,47}", channel))


def dedupe_key_for(request: ToastRequest) -> str:
    """去重键：显式键优先，否则按级别+标题+正文归一。"""
    key = str(request.dedupe_key or "").strip()
    if key:
        return key
    return f"{request.level}:{request.title}:{request.text}"


def compose_text(request: ToastRequest, repeat: int) -> str:
    """按合并次数合成正文：模板含 ``{count}`` 则插值，否则追加 ``(×N)``。"""
    if repeat <= 1:
        return request.text
    if "{count}" in request.text:
        try:
            return request.text.format(count=repeat)
        except (KeyError, ValueError, IndexError):
            return request.text
    return f"{request.text} (×{repeat})"


__all__ = [
    "MAX_ACTIONS",
    "MAX_LIFE_MS",
    "MAX_PAYLOAD_BYTES",
    "MAX_TEXT_CHARS",
    "MAX_TITLE_CHARS",
    "PERSISTENT_WATCHDOG_MS",
    "TOAST_PROTOCOL_VERSION",
    "DedupePolicy",
    "ToastAction",
    "ToastAnchor",
    "ToastCode",
    "ToastDismiss",
    "ToastDismissReason",
    "ToastLevel",
    "ToastMode",
    "ToastRequest",
    "ToastResult",
    "ToastState",
    "channel_is_valid",
    "clamp_actions",
    "clamp_progress",
    "clamp_text",
    "clamp_title",
    "compose_text",
    "dedupe_key_for",
    "default_life",
    "is_persistent",
    "normalize_anchor",
    "normalize_dedupe",
    "normalize_level",
    "normalize_mode",
    "resolve_life",
]
