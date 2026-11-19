"""系统级快捷键注册表：作用域、平台修饰键、优先级与冲突检测。

设计要点（协议见 ``docs/SHORTCUTS.md``）：

- **不用 ``QShortcut``**：Qt 对同一序列的多个 ``QShortcut`` 只会抛
  ``activatedAmbiguously``，无法表达优先级，也无法按作用域统一裁决。这里在
  ``QApplication`` 上装一个事件过滤器，在按键送达焦点控件**之前**统一匹配，
  命中即消费，未命中不改变任何现有行为。
- **平台修饰键**：``primary`` 表示「本平台的主修饰键」（macOS 为 ⌘，其余为
  Ctrl）；``ctrl`` / ``meta`` 按物理键语义解析。Qt 在 macOS 上把 ⌘ 映射成
  ``ControlModifier``、把物理 Control 映射成 ``MetaModifier``，解析层统一
  折算成 Qt 规范位，匹配阶段只比较数值。
- **作用域**：``global`` 作用于整个应用（任何窗口）；``local`` 只在宿主控件
  子树内生效。
- **优先级**：命中多条时按 ``(priority, 注册顺序)`` 取最高一条；基座内置项
  使用 :data:`PRIORITY_BASE` 并 ``locked=True``，插件默认
  :data:`PRIORITY_NORMAL` 且冲突策略为「拒绝」，因此插件既插不进来也顶不掉
  内置行为。
- **生命周期**：条目可按宿主控件绑定，宿主 ``destroyed`` 时自动注销；插件
  卸载由加载器调用 ``clear()`` 统一清理。

本模块属于 ``guicore``：只依赖 ``appcore``，不反向依赖 ``guis``。
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QKeySequenceEdit,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from sllkgui.appcore import Logger, record_event

# ----------------------------------------------------------------------
# 错误码
# ----------------------------------------------------------------------
SHORTCUT_INVALID_SEQUENCE = "SHORTCUT_INVALID_SEQUENCE"
SHORTCUT_CONFLICT = "SHORTCUT_CONFLICT"
SHORTCUT_LOCKED = "SHORTCUT_LOCKED"
SHORTCUT_NOT_FOUND = "SHORTCUT_NOT_FOUND"

# ----------------------------------------------------------------------
# 优先级：数值越大越优先
# ----------------------------------------------------------------------
#: 插件可显式降低到该档，用于「仅在没有其他绑定时才生效」的兜底动作
PRIORITY_LOW = 100
#: 插件默认优先级
PRIORITY_NORMAL = 500
#: 基座内置快捷键；插件无法覆盖
PRIORITY_BASE = 900


def _flag(value: Any) -> int:
    """PySide6 的 flag 枚举不能直接 ``int()``，统一走 ``.value``。"""
    return int(getattr(value, "value", value))


_MOD_MASK = (
    _flag(Qt.KeyboardModifier.ShiftModifier)
    | _flag(Qt.KeyboardModifier.ControlModifier)
    | _flag(Qt.KeyboardModifier.AltModifier)
    | _flag(Qt.KeyboardModifier.MetaModifier)
)
#: 「命令类」修饰键：带这些修饰键的绑定即使在文本输入框里也照常生效
_COMMAND_MASK = (
    _flag(Qt.KeyboardModifier.ControlModifier)
    | _flag(Qt.KeyboardModifier.AltModifier)
    | _flag(Qt.KeyboardModifier.MetaModifier)
)
_SHIFT = _flag(Qt.KeyboardModifier.ShiftModifier)
_CONTROL = _flag(Qt.KeyboardModifier.ControlModifier)
_ALT = _flag(Qt.KeyboardModifier.AltModifier)
_META = _flag(Qt.KeyboardModifier.MetaModifier)

#: 单独按下不构成快捷键的键（修饰键、锁定键、未知键）
_IGNORED_KEYS = frozenset(
    {
        _flag(Qt.Key.Key_unknown),
        _flag(Qt.Key.Key_Shift),
        _flag(Qt.Key.Key_Control),
        _flag(Qt.Key.Key_Alt),
        _flag(Qt.Key.Key_Meta),
        _flag(Qt.Key.Key_AltGr),
        _flag(Qt.Key.Key_CapsLock),
        _flag(Qt.Key.Key_NumLock),
        _flag(Qt.Key.Key_ScrollLock),
    }
)


class ShortcutError(Exception):
    """快捷键注册失败。``code`` 供上层（插件门面）转成稳定错误码。"""

    def __init__(self, code: str, message: str, detail: str = "") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.detail = detail


class Scope(StrEnum):
    """作用域：``global`` 全应用，``local`` 仅宿主控件子树。"""

    GLOBAL = "global"
    LOCAL = "local"


class ConflictPolicy(StrEnum):
    """同一序列被重复注册时的处理方式。"""

    #: 直接拒绝（默认，插件与内置项都走这条）
    ERROR = "error"
    #: 允许共存，派发时按优先级裁决；低优先级项在高优先级项禁用后生效
    SHADOW = "shadow"
    #: 顶掉冲突项；冲突项 ``locked`` 时拒绝
    REPLACE = "replace"


# ----------------------------------------------------------------------
# 平台修饰键
# ----------------------------------------------------------------------
_MODIFIER_ALIASES: dict[str, str] = {
    "primary": "primary",
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "meta": "meta",
    "cmd": "meta",
    "command": "meta",
    "super": "meta",
    "win": "meta",
    "windows": "meta",
    "os": "meta",
}

#: 语义修饰键 -> Qt 修饰位；``None`` 表示按平台换算
_SEMANTIC_MODIFIERS: dict[str, int] = {
    "alt": _ALT,
    "shift": _SHIFT,
}

#: 单字符标点 -> Qt.Key 名称
_PUNCTUATION: dict[str, str] = {
    ",": "Key_Comma",
    ".": "Key_Period",
    "/": "Key_Slash",
    ";": "Key_Semicolon",
    "'": "Key_Apostrophe",
    "[": "Key_BracketLeft",
    "]": "Key_BracketRight",
    "\\": "Key_Backslash",
    "-": "Key_Minus",
    "=": "Key_Equal",
    "`": "Key_QuoteLeft",
}

#: 具名键 -> Qt.Key 名称
_KEY_ALIASES: dict[str, str] = {
    "escape": "Key_Escape",
    "esc": "Key_Escape",
    "tab": "Key_Tab",
    "backtab": "Key_Backtab",
    "backspace": "Key_Backspace",
    "bksp": "Key_Backspace",
    "return": "Key_Return",
    "enter": "Key_Enter",
    "insert": "Key_Insert",
    "ins": "Key_Insert",
    "delete": "Key_Delete",
    "del": "Key_Delete",
    "home": "Key_Home",
    "end": "Key_End",
    "left": "Key_Left",
    "up": "Key_Up",
    "right": "Key_Right",
    "down": "Key_Down",
    "pageup": "Key_PageUp",
    "pgup": "Key_PageUp",
    "pagedown": "Key_PageDown",
    "pgdn": "Key_PageDown",
    "pgdown": "Key_PageDown",
    "space": "Key_Space",
    "spacebar": "Key_Space",
    "pause": "Key_Pause",
    "print": "Key_Print",
    "sysreq": "Key_SysReq",
    "menu": "Key_Menu",
    "contextmenu": "Key_Menu",
    "capslock": "Key_CapsLock",
    "numlock": "Key_NumLock",
    "scrolllock": "Key_ScrollLock",
    "plus": "Key_Plus",
    "minus": "Key_Minus",
    "equal": "Key_Equal",
    "equals": "Key_Equal",
    "comma": "Key_Comma",
    "period": "Key_Period",
    "dot": "Key_Period",
    "slash": "Key_Slash",
    "backslash": "Key_Backslash",
    "semicolon": "Key_Semicolon",
    "colon": "Key_Colon",
    "apostrophe": "Key_Apostrophe",
    "quote": "Key_Apostrophe",
    "quoteleft": "Key_QuoteLeft",
    "grave": "Key_QuoteLeft",
    "backtick": "Key_QuoteLeft",
    "bracketleft": "Key_BracketLeft",
    "bracketright": "Key_BracketRight",
}

#: 具名键的展示文本（不依赖 Qt 的本地化）
_KEY_LABELS: dict[str, str] = {
    "Key_Escape": "Esc",
    "Key_Tab": "Tab",
    "Key_Backtab": "Shift+Tab",
    "Key_Backspace": "Backspace",
    "Key_Return": "Enter",
    "Key_Enter": "Enter",
    "Key_Insert": "Insert",
    "Key_Delete": "Delete",
    "Key_Home": "Home",
    "Key_End": "End",
    "Key_Left": "Left",
    "Key_Up": "Up",
    "Key_Right": "Right",
    "Key_Down": "Down",
    "Key_PageUp": "PageUp",
    "Key_PageDown": "PageDown",
    "Key_Space": "Space",
    "Key_Pause": "Pause",
    "Key_Print": "Print",
    "Key_SysReq": "SysRq",
    "Key_Menu": "Menu",
    "Key_Plus": "+",
    "Key_Minus": "-",
    "Key_Equal": "=",
    "Key_Comma": ",",
    "Key_Period": ".",
    "Key_Slash": "/",
    "Key_Backslash": "\\",
    "Key_Semicolon": ";",
    "Key_Colon": ":",
    "Key_Apostrophe": "'",
    "Key_QuoteLeft": "`",
    "Key_BracketLeft": "[",
    "Key_BracketRight": "]",
}

#: Shift 后的字符 -> 未按 Shift 时的物理键（美式布局常用项）。
#: 用于 ``shift+slash`` 这类绑定的匹配：按住 Shift 时 Qt 报的是 ``?``。
_SHIFTED_BASE: dict[int, int] = {
    ord("!"): ord("1"),
    ord("@"): ord("2"),
    ord("#"): ord("3"),
    ord("$"): ord("4"),
    ord("%"): ord("5"),
    ord("^"): ord("6"),
    ord("&"): ord("7"),
    ord("*"): ord("8"),
    ord("("): ord("9"),
    ord(")"): ord("0"),
    ord("_"): ord("-"),
    ord("+"): ord("="),
    ord("{"): ord("["),
    ord("}"): ord("]"),
    ord("|"): ord("\\"),
    ord(":"): ord(";"),
    ord('"'): ord("'"),
    ord("<"): ord(","),
    ord(">"): ord("."),
    ord("?"): ord("/"),
    ord("~"): ord("`"),
}


def _normalize_platform(platform: str | None = None) -> str:
    text = (platform or sys.platform).lower()
    if text.startswith("darwin") or text.startswith("mac"):
        return "darwin"
    if text.startswith("win"):
        return "win32"
    return "linux"


def _resolve_modifier(token: str, platform: str) -> int:
    """把语义修饰键折算成 Qt 修饰位（处理 Qt 在 macOS 上的 Ctrl/Meta 互换）。"""
    layout = {
        "primary": _CONTROL,  # Qt 会把 ControlModifier 显示成 ⌘
        "ctrl": _META if platform == "darwin" else _CONTROL,
        "meta": _CONTROL if platform == "darwin" else _META,
    }
    return layout.get(token) or _SEMANTIC_MODIFIERS[token]


def _resolve_key(token: str) -> int:
    name = _KEY_ALIASES.get(token)
    if name is None and token.startswith("f") and token[1:].isdigit():
        index = int(token[1:])
        if 1 <= index <= 35:
            name = f"Key_F{index}"
    if name is None and len(token) == 1:
        name = _PUNCTUATION.get(token)
        if name is None:
            return ord(token.upper())
    if name is None:
        raise ShortcutError(SHORTCUT_INVALID_SEQUENCE, f"无法识别的按键: {token!r}")
    try:
        return _flag(getattr(Qt.Key, name))
    except AttributeError as exc:  # pragma: no cover - Qt 版本差异
        raise ShortcutError(SHORTCUT_INVALID_SEQUENCE, f"当前 Qt 不支持的按键: {token!r}") from exc


def _key_label(key: int) -> str:
    if _flag(Qt.Key.Key_A) <= key <= _flag(Qt.Key.Key_Z):
        return chr(key)
    if _flag(Qt.Key.Key_0) <= key <= _flag(Qt.Key.Key_9):
        return chr(key)
    if _flag(Qt.Key.Key_F1) <= key <= _flag(Qt.Key.Key_F35):
        return f"F{key - _flag(Qt.Key.Key_F1) + 1}"
    for name, text in _KEY_LABELS.items():
        if _flag(getattr(Qt.Key, name)) == key:
            return text
    text = QKeySequence(key).toString(QKeySequence.SequenceFormat.NativeText)
    return text or "?"


@dataclass(frozen=True)
class KeyBinding:
    """解析后的按键绑定。

    ``sequence`` 保留**可移植文本**（``primary+shift+p``），跨平台存储同一份
    字符串即可；``key`` / ``modifiers`` 是换算到当前平台的 Qt 规范值，匹配时
    只比较这两个字段。
    """

    sequence: str
    key: int
    modifiers: int
    platform: str = "linux"

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, sequence: str | KeyBinding, *, platform: str | None = None) -> KeyBinding:
        if isinstance(sequence, KeyBinding):
            return sequence
        text = str(sequence or "").strip()
        if not text:
            raise ShortcutError(SHORTCUT_INVALID_SEQUENCE, "快捷键序列不能为空")
        current = _normalize_platform(platform)
        tokens = [item.strip().lower() for item in text.split("+")]
        tokens = [item for item in tokens if item]
        if not tokens:
            raise ShortcutError(SHORTCUT_INVALID_SEQUENCE, f"快捷键序列非法: {sequence!r}")
        modifiers = 0
        aliases: list[str] = []
        key_tokens: list[str] = []
        for token in tokens:
            alias = _MODIFIER_ALIASES.get(token)
            if alias is not None:
                modifiers |= _resolve_modifier(alias, current)
                aliases.append(alias)
            else:
                key_tokens.append(token)
        if len(key_tokens) != 1:
            raise ShortcutError(
                SHORTCUT_INVALID_SEQUENCE,
                f"快捷键必须且只能包含一个主键: {sequence!r}",
                "形如 primary+shift+p / f5 / escape",
            )
        key = _resolve_key(key_tokens[0])
        return cls(
            sequence=_portable_text(aliases, key_tokens[0]),
            key=key,
            modifiers=modifiers & _MOD_MASK,
            platform=current,
        )

    # ------------------------------------------------------------------
    # 展示与匹配
    # ------------------------------------------------------------------
    def display(self) -> str:
        """面向用户的文本：macOS 用 ⌃⌥⇧⌘ 符号，其余平台用 Ctrl/Alt/Shift。"""
        parts: list[str] = []
        if self.platform == "darwin":
            if self.modifiers & _META:
                parts.append("⌃")
            if self.modifiers & _ALT:
                parts.append("⌥")
            if self.modifiers & _SHIFT:
                parts.append("⇧")
            if self.modifiers & _CONTROL:
                parts.append("⌘")
            return "".join(parts) + _key_label(self.key)
        if self.modifiers & _CONTROL:
            parts.append("Ctrl")
        if self.modifiers & _ALT:
            parts.append("Alt")
        if self.modifiers & _SHIFT:
            parts.append("Shift")
        if self.modifiers & _META:
            parts.append("Meta")
        parts.append(_key_label(self.key))
        return "+".join(parts)

    def matches(self, key: int, modifiers: int) -> bool:
        if self.modifiers != (modifiers & _MOD_MASK):
            return False
        if key == self.key:
            return True
        # Shift 组合下 Qt 报的是上档字符（? : { 等），按物理键回退比较一次
        base = _SHIFTED_BASE.get(key)
        return base is not None and base == self.key

    def __str__(self) -> str:  # pragma: no cover - 纯展示
        return self.sequence


def _portable_text(aliases: Iterable[str], key_token: str) -> str:
    order = ("primary", "ctrl", "alt", "shift", "meta")
    unique = list(dict.fromkeys(aliases))
    ordered = [item for item in order if item in unique]
    return "+".join([*ordered, key_token])


@dataclass
class ShortcutEntry:
    """注册表内部条目。"""

    shortcut_id: str
    owner: str
    binding: KeyBinding
    callback: Callable[[], None]
    scope: Scope = Scope.GLOBAL
    priority: int = PRIORITY_NORMAL
    description: str = ""
    enabled: bool = True
    locked: bool = False
    allow_in_modal: bool = False
    policy: ConflictPolicy = ConflictPolicy.ERROR
    host: QWidget | None = None
    order: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def sequence(self) -> str:
        return self.binding.sequence


@dataclass(frozen=True)
class ShortcutConflict:
    """序列冲突：同一按键在多条可同时生效的绑定之间重复。"""

    sequence: str
    shortcut_ids: tuple[str, ...]
    owners: tuple[str, ...]
    winner: str = ""
    resolved: bool = True

    def describe(self) -> str:
        return f"{self.sequence}: {', '.join(self.shortcut_ids)}"


@dataclass(frozen=True)
class ShortcutInfo:
    """对外只读视图（插件 ``bindings()`` 与调试面板共用）。"""

    shortcut_id: str
    owner: str
    sequence: str
    display: str
    scope: str
    priority: int
    enabled: bool
    description: str = ""
    locked: bool = False


# ----------------------------------------------------------------------
# 匹配辅助
# ----------------------------------------------------------------------
def _is_within(target: QWidget | None, host: QWidget | None) -> bool:
    if target is None or host is None:
        return False
    widget: QWidget | None = target
    while widget is not None:
        if widget is host:
            return True
        widget = widget.parentWidget()
    return False


def _is_text_input(widget: QWidget | None) -> bool:
    """焦点控件是否在编辑文本（此时纯字符快捷键不应抢键）。"""
    if widget is None:
        return False
    return isinstance(
        widget,
        (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QKeySequenceEdit),
    )


def _hosts_overlap(left: ShortcutEntry, right: ShortcutEntry) -> bool:
    """两条绑定是否可能在同一按键事件上同时命中。"""
    if left.scope is Scope.GLOBAL or right.scope is Scope.GLOBAL:
        return True
    return _is_within(left.host, right.host) or _is_within(right.host, left.host)


def _chord(binding: KeyBinding) -> tuple[int, int]:
    """归一化到「物理按键 + Qt 修饰位」。

    冲突必须按这个签名判断：``primary+k`` 与 ``ctrl+k`` 在 Windows 上是同一个
    组合，``primary+k`` 与 ``meta+k`` 在 macOS 上也是同一个组合；只比文本会漏判。
    """
    return binding.key, binding.modifiers


# ----------------------------------------------------------------------
# 注册表
# ----------------------------------------------------------------------
class ShortcutRegistry(QObject):
    """全进程唯一的快捷键表：注册、更新、注销、派发与冲突检测。"""

    def __init__(self, parent: QObject | None = None, *, platform: str | None = None) -> None:
        super().__init__(parent)
        self._entries: dict[str, ShortcutEntry] = {}
        #: shortcut_id -> (宿主, destroyed 槽)；重注册/注销时先断开，避免误删新条目
        self._guards: dict[str, tuple[QObject, Any]] = {}
        self._order = 0
        self._active = True
        self._installed = False
        self._app: QApplication | None = None
        #: 平台只在构造时确定；测试可显式传入 ``darwin`` / ``win32`` 复算修饰键
        self._platform = _normalize_platform(platform)

    # ------------------------------------------------------------------
    # 装配
    # ------------------------------------------------------------------
    @property
    def platform(self) -> str:
        """当前平台标识（``darwin`` / ``win32`` / ``linux``）。"""
        return self._platform

    def install(self, app: QApplication | None = None) -> bool:
        """在 ``QApplication`` 上装事件过滤器；无 Qt 应用时安全降级。"""
        if self._installed:
            return True
        target = app or QApplication.instance()
        if target is None:
            Logger.debug("快捷键注册表暂不可用：QApplication 尚未创建")
            return False
        target.installEventFilter(self)
        self._app = target
        self._installed = True
        Logger.debug(f"快捷键注册表已装配（平台 {self._platform}）")
        return True

    def uninstall(self) -> None:
        """只摘掉事件过滤器，保留已注册条目（重载场景）。"""
        if not self._installed or self._app is None:
            self._installed = False
            self._app = None
            return
        try:
            self._app.removeEventFilter(self)
        except RuntimeError:  # pragma: no cover - 应用对象已销毁
            pass
        self._installed = False
        self._app = None

    def shutdown(self) -> None:
        """应用退出：摘过滤器并清空全部条目。"""
        self.uninstall()
        for shortcut_id in list(self._guards):
            self._release_guard(shortcut_id)
        self._entries.clear()
        self._guards.clear()
        self._active = True

    def is_installed(self) -> bool:
        return self._installed

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        """全局开关：关闭后所有快捷键静默（用于「快捷键总开关」）。"""
        self._active = bool(active)

    # ------------------------------------------------------------------
    # 注册 / 更新 / 注销
    # ------------------------------------------------------------------
    def register(
        self,
        shortcut_id: str,
        sequence: str | KeyBinding,
        callback: Callable[[], None],
        *,
        owner: str = "base",
        scope: Scope | str = Scope.GLOBAL,
        priority: int = PRIORITY_NORMAL,
        description: str = "",
        host: QWidget | None = None,
        locked: bool = False,
        allow_in_modal: bool = False,
        policy: ConflictPolicy | str = ConflictPolicy.ERROR,
        meta: Mapping[str, Any] | None = None,
    ) -> ShortcutHandle:
        """注册（或同 id 覆盖）一条快捷键，冲突时按 ``policy`` 处理。"""
        shortcut_id = str(shortcut_id or "").strip()
        if not shortcut_id:
            raise ShortcutError(SHORTCUT_INVALID_SEQUENCE, "快捷键 id 不能为空")
        if not callable(callback):
            raise ShortcutError(SHORTCUT_INVALID_SEQUENCE, "快捷键回调必须可调用")
        binding = KeyBinding.parse(sequence, platform=self._platform)
        scope_value = Scope(str(scope))
        policy_value = ConflictPolicy(str(policy))
        if scope_value is Scope.LOCAL and host is None:
            raise ShortcutError(
                SHORTCUT_INVALID_SEQUENCE,
                "局部作用域的快捷键必须绑定宿主控件",
                "scope='local' 需要 host=父控件",
            )

        incoming = ShortcutEntry(
            shortcut_id=shortcut_id,
            owner=str(owner or "base"),
            binding=binding,
            callback=callback,
            scope=scope_value,
            priority=int(priority),
            description=str(description or ""),
            locked=bool(locked),
            allow_in_modal=bool(allow_in_modal),
            policy=policy_value,
            host=host,
            meta=dict(meta or {}),
        )
        conflicts = [
            entry
            for entry in self._entries.values()
            if entry.shortcut_id != shortcut_id
            and _chord(entry.binding) == _chord(binding)
            and _hosts_overlap(incoming, entry)
        ]
        self._resolve_conflicts(incoming, conflicts)
        self._store(incoming)
        return ShortcutHandle(self, shortcut_id)

    def update(
        self,
        shortcut_id: str,
        *,
        sequence: str | KeyBinding | None = None,
        description: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
        policy: ConflictPolicy | str | None = None,
    ) -> bool:
        """更新已注册条目；改序列时重新做冲突检测。"""
        entry = self._entries.get(str(shortcut_id))
        if entry is None:
            return False
        if sequence is not None:
            binding = KeyBinding.parse(sequence, platform=self._platform)
            candidate = ShortcutEntry(
                shortcut_id=entry.shortcut_id,
                owner=entry.owner,
                binding=binding,
                callback=entry.callback,
                scope=entry.scope,
                priority=entry.priority if priority is None else int(priority),
                description=entry.description,
                enabled=entry.enabled,
                locked=entry.locked,
                allow_in_modal=entry.allow_in_modal,
                policy=ConflictPolicy(str(policy)) if policy is not None else entry.policy,
                host=entry.host,
                meta=entry.meta,
            )
            conflicts = [
                other
                for other in self._entries.values()
                if other is not entry and _chord(other.binding) == _chord(binding) and _hosts_overlap(candidate, other)
            ]
            self._resolve_conflicts(candidate, conflicts)
            entry.binding = binding
        if description is not None:
            entry.description = str(description)
        if priority is not None:
            entry.priority = int(priority)
        if enabled is not None:
            entry.enabled = bool(enabled)
        if policy is not None:
            entry.policy = ConflictPolicy(str(policy))
        return True

    def unregister(self, shortcut_id: str) -> bool:
        entry = self._entries.pop(str(shortcut_id), None)
        if entry is None:
            return False
        self._release_guard(entry.shortcut_id)
        Logger.debug(f"快捷键已注销: {entry.shortcut_id} ({entry.sequence})")
        return True

    def unregister_owner(self, owner: str) -> int:
        """注销某个归属（插件 / 基座）的全部快捷键。"""
        removed = [key for key, entry in self._entries.items() if entry.owner == owner]
        for key in removed:
            self._entries.pop(key, None)
            self._release_guard(key)
        return len(removed)

    def set_enabled(self, shortcut_id: str, enabled: bool) -> bool:
        entry = self._entries.get(str(shortcut_id))
        if entry is None:
            return False
        entry.enabled = bool(enabled)
        return True

    def get(self, shortcut_id: str) -> ShortcutEntry | None:
        return self._entries.get(str(shortcut_id))

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def describe(self, *, owner: str | None = None) -> tuple[ShortcutInfo, ...]:
        items = sorted(
            (entry for entry in self._entries.values() if owner is None or entry.owner == owner),
            key=lambda entry: (entry.sequence, -entry.priority, entry.order),
        )
        return tuple(
            ShortcutInfo(
                shortcut_id=entry.shortcut_id,
                owner=entry.owner,
                sequence=entry.sequence,
                display=entry.binding.display(),
                scope=str(entry.scope),
                priority=entry.priority,
                enabled=entry.enabled,
                description=entry.description,
                locked=entry.locked,
            )
            for entry in items
        )

    def conflicts(self) -> tuple[ShortcutConflict, ...]:
        """当前仍存在按键重叠的绑定（已注册即视为可裁决）。"""
        grouped: dict[tuple[int, int], list[ShortcutEntry]] = {}
        for entry in self._entries.values():
            grouped.setdefault(_chord(entry.binding), []).append(entry)
        result: list[ShortcutConflict] = []
        for entries in grouped.values():
            if len(entries) < 2:
                continue
            # 只保留真正会互相抢键的组合（不同窗口的 local 不算）
            overlapping = [entries[0]]
            for candidate in entries[1:]:
                if any(_hosts_overlap(candidate, item) for item in overlapping):
                    overlapping.append(candidate)
            if len(overlapping) < 2:
                continue
            winner = self._winner(overlapping)
            result.append(
                ShortcutConflict(
                    sequence=winner.sequence if winner is not None else overlapping[0].sequence,
                    shortcut_ids=tuple(item.shortcut_id for item in overlapping),
                    owners=tuple(item.owner for item in overlapping),
                    winner=winner.shortcut_id if winner is not None else "",
                    resolved=True,
                )
            )
        return tuple(result)

    def count(self, owner: str | None = None) -> int:
        if owner is None:
            return len(self._entries)
        return sum(1 for entry in self._entries.values() if entry.owner == owner)

    # ------------------------------------------------------------------
    # 派发
    # ------------------------------------------------------------------
    def activate(self, key: int, modifiers: int = 0, target: QWidget | None = None) -> str | None:
        """按当前状态解析并执行一条绑定，返回命中的 ``shortcut_id``。

        事件过滤器与测试/程序化触发共用这条路径，保证语义一致。
        """
        entry = self.resolve(key, modifiers, target)
        if entry is None:
            return None
        self._invoke(entry)
        return entry.shortcut_id

    def resolve(self, key: int, modifiers: int, target: QWidget | None = None) -> ShortcutEntry | None:
        if not self._active or not self._entries:
            return None
        key = _flag(key)
        if key in _IGNORED_KEYS:
            return None
        modifiers = _flag(modifiers) & _MOD_MASK
        modal = QApplication.activeModalWidget() is not None
        text_input = _is_text_input(target)
        candidates: list[ShortcutEntry] = []
        for entry in self._entries.values():
            if not entry.enabled:
                continue
            if modal and not entry.allow_in_modal:
                continue
            if not entry.binding.matches(key, modifiers):
                continue
            if entry.scope is Scope.LOCAL and not _is_within(target, entry.host):
                continue
            if text_input and not (modifiers & _COMMAND_MASK):
                # 编辑文本时纯字符键交给输入框，避免打断输入法/快捷键之外的输入
                continue
            candidates.append(entry)
        if not candidates:
            return None
        return self._winner(candidates)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - 覆写 Qt 命名
        """应用级过滤器：在按键送达焦点控件前统一裁决。"""
        if event.type() != QEvent.Type.KeyPress:
            return False
        if not self._active or not self._entries:
            return False
        if event.isAutoRepeat():
            return False
        target = obj if isinstance(obj, QWidget) else None
        shortcut_id = self.activate(_flag(event.key()), _flag(event.modifiers()), target)
        if shortcut_id is None:
            return False
        event.accept()
        return True

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    @staticmethod
    def _winner(entries: Iterable[ShortcutEntry]) -> ShortcutEntry | None:
        best: ShortcutEntry | None = None
        for entry in entries:
            if best is None or (entry.priority, -entry.order) > (best.priority, -best.order):
                best = entry
        return best

    def _store(self, entry: ShortcutEntry) -> ShortcutEntry:
        self._order += 1
        entry.order = self._order
        # 同 id 重注册：先断开旧宿主的 destroyed 槽，否则旧宿主销毁会误删新条目
        self._release_guard(entry.shortcut_id)
        self._entries[entry.shortcut_id] = entry
        self._bind_lifecycle(entry)
        if not self._installed:
            self.install()
        Logger.debug(
            f"快捷键已注册: {entry.shortcut_id} ({entry.sequence}) "
            f"owner={entry.owner} scope={entry.scope} priority={entry.priority}"
        )
        return entry

    def _bind_lifecycle(self, entry: ShortcutEntry) -> None:
        """宿主销毁即自动注销：局部绑定与「随窗口生灭」的全局绑定都不会残留。"""
        host = entry.host
        if not isinstance(host, QObject):
            return
        shortcut_id = entry.shortcut_id

        def release(*_args: Any, _sid: str = shortcut_id) -> None:
            self.unregister(_sid)

        host.destroyed.connect(release)
        self._guards[shortcut_id] = (host, release)

    def _release_guard(self, shortcut_id: str) -> None:
        item = self._guards.pop(shortcut_id, None)
        if item is None:
            return
        host, release = item
        try:
            host.destroyed.disconnect(release)
        except (RuntimeError, TypeError):  # pragma: no cover - 宿主已析构或未连接
            pass

    def _resolve_conflicts(self, incoming: ShortcutEntry, conflicts: list[ShortcutEntry]) -> None:
        if not conflicts:
            return
        sequence = incoming.binding.sequence
        ids = ", ".join(item.shortcut_id for item in conflicts)
        detail = f"{sequence} 已被占用: {ids}"
        if incoming.policy is ConflictPolicy.REPLACE:
            locked = [item for item in conflicts if item.locked]
            if locked:
                names = ", ".join(item.shortcut_id for item in locked)
                raise ShortcutError(
                    SHORTCUT_LOCKED,
                    f"快捷键 {sequence} 被基座内置项占用，无法覆盖",
                    names,
                )
            for item in conflicts:
                self._entries.pop(item.shortcut_id, None)
            record_event(
                "shortcut.replaced",
                category="ui",
                payload={"sequence": sequence, "by": incoming.shortcut_id, "replaced": ids},
            )
            return
        if incoming.policy is ConflictPolicy.SHADOW:
            record_event(
                "shortcut.shadowed",
                category="ui",
                payload={
                    "sequence": sequence,
                    "by": incoming.shortcut_id,
                    "priority": incoming.priority,
                    "occupied_by": ids,
                },
            )
            return
        record_event(
            "shortcut.conflict",
            category="ui",
            level="warning",
            payload={"sequence": sequence, "incoming": incoming.shortcut_id, "occupied_by": ids},
        )
        raise ShortcutError(SHORTCUT_CONFLICT, f"快捷键冲突: {detail}", detail)

    def _invoke(self, entry: ShortcutEntry) -> None:
        """执行回调并隔离异常：单个插件失败不得打断 Qt 事件循环。"""
        try:
            entry.callback()
        except Exception as exc:  # noqa: BLE001 - 插件回调错误不得影响基座
            Logger.exception(f"快捷键回调失败 {entry.owner}:{entry.shortcut_id}: {exc}")


class ShortcutHandle:
    """单条绑定的句柄：启用/禁用、改序列、注销。"""

    def __init__(self, registry: ShortcutRegistry, shortcut_id: str) -> None:
        self._registry = registry
        self._shortcut_id = shortcut_id

    @property
    def shortcut_id(self) -> str:
        return self._shortcut_id

    @property
    def owner(self) -> str:
        entry = self._registry.get(self._shortcut_id)
        return entry.owner if entry is not None else ""

    @property
    def sequence(self) -> str:
        entry = self._registry.get(self._shortcut_id)
        return entry.sequence if entry is not None else ""

    @property
    def display(self) -> str:
        entry = self._registry.get(self._shortcut_id)
        return entry.binding.display() if entry is not None else ""

    @property
    def enabled(self) -> bool:
        entry = self._registry.get(self._shortcut_id)
        return bool(entry.enabled) if entry is not None else False

    def registered(self) -> bool:
        return self._registry.get(self._shortcut_id) is not None

    def set_enabled(self, enabled: bool) -> None:
        self._registry.set_enabled(self._shortcut_id, enabled)

    def update(
        self,
        *,
        sequence: str | KeyBinding | None = None,
        description: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> bool:
        return self._registry.update(
            self._shortcut_id,
            sequence=sequence,
            description=description,
            priority=priority,
            enabled=enabled,
        )

    def unregister(self) -> None:
        self._registry.unregister(self._shortcut_id)


_REGISTRY: ShortcutRegistry | None = None


def shortcut_registry() -> ShortcutRegistry:
    """返回全进程唯一的快捷键注册表（惰性创建）。"""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ShortcutRegistry()
    return _REGISTRY


def reset_shortcut_registry() -> ShortcutRegistry:
    """丢弃当前注册表并重建（测试与「恢复默认」用）。"""
    global _REGISTRY
    if _REGISTRY is not None:
        _REGISTRY.shutdown()
        _REGISTRY.deleteLater()
    _REGISTRY = ShortcutRegistry()
    return _REGISTRY


__all__ = [
    "PRIORITY_BASE",
    "PRIORITY_LOW",
    "PRIORITY_NORMAL",
    "SHORTCUT_CONFLICT",
    "SHORTCUT_INVALID_SEQUENCE",
    "SHORTCUT_LOCKED",
    "SHORTCUT_NOT_FOUND",
    "ConflictPolicy",
    "KeyBinding",
    "Scope",
    "ShortcutConflict",
    "ShortcutEntry",
    "ShortcutError",
    "ShortcutHandle",
    "ShortcutInfo",
    "ShortcutRegistry",
    "reset_shortcut_registry",
    "shortcut_registry",
]
