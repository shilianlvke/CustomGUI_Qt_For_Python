"""快捷键解析层：序列语法、平台修饰键、优先级与错误类型。

从 :mod:`sllkgui.guicore.shortcuts` 拆出，便于单独测试与阅读；对外符号仍由
`shortcuts.py` 再导出，所有现有 import 路径保持不变。
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

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
