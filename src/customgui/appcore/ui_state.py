"""轻量 UI 状态持久化：主题、语言与窗口尺寸。

这些是用户在使用过程中显式改过的偏好，不能写回基座资源层
（``resource/customui/settings`` 是随包发布的只读配置）。因此单独存一份
JSON 到可写数据目录，启动时由 ``SetupMainWindow`` 读回。

失败策略：文件缺失、损坏或目录不可写时全部静默回退到配置默认值——
状态保存属于体验增强，不允许影响启动。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .sysx.config.paths import data_root
from .sysx.modules.logger_module import Logger

_FILE_NAME = "ui_state.json"
_LOCK = threading.Lock()
_CACHE: dict | None = None


def _state_path() -> Path:
    return data_root() / _FILE_NAME


def _read_file() -> dict:
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_ui_state() -> dict:
    """读取已保存的 UI 状态（首次读取后缓存）。"""
    global _CACHE
    with _LOCK:
        if _CACHE is None:
            _CACHE = _read_file()
        return dict(_CACHE)


def save_ui_state(**updates) -> dict:
    """合并并写入 UI 状态；返回写入后的完整状态。"""
    global _CACHE
    with _LOCK:
        state = dict(_CACHE) if _CACHE is not None else _read_file()
        state.update(updates)
        _CACHE = state
        path = _state_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)
        except OSError as exc:
            Logger.warning(f"UI 状态保存失败: {exc}")
        return dict(state)


def reset_ui_state_cache() -> None:
    """丢弃内存缓存（``configure`` 切换数据目录或测试使用）。"""
    global _CACHE
    with _LOCK:
        _CACHE = None


__all__ = ["load_ui_state", "save_ui_state", "reset_ui_state_cache"]
