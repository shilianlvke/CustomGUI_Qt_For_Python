"""用户配置持久化：把运行时修改的偏好写入可写数据目录的 YAML 覆盖层。

为什么单独存一份用户配置
------------------------
``resource/sllkgui/settings/*.yaml`` 是随包发布的只读默认值，可能位于
site-packages / Program Files；品牌层又属于应用资产。两者都不应在运行时
被用户偏好改写。因此用户改动写入::

    <data_root>/settings/user.yaml

只记录**改动过的键**（增量覆盖），基座新增字段仍由默认层提供。默认
``data_root()`` 为程序运行根目录（显式 ``data_dir`` / ``SLLKGUI_DATA_DIR``
优先），不再写入 ``%APPDATA%`` 等用户系统目录。

读写时机
--------
- 读：启动装配阶段的 ``SetupMainWindow.restore_ui_state`` 调用一次；
- 写：主题 / 语言 / 菜单模式变更时立即写入；窗口尺寸在正常关闭时写入。

优先级
------
同一字段的取值顺序为 **user.yaml > 品牌覆盖层 > 基座默认值**。user.yaml
中缺失或非法的键会被忽略，继续使用下层配置，因此文件损坏不会阻断启动。

错误策略
--------
文件不存在视为「没有用户偏好」；读取失败、YAML 解析失败、顶层不是字典
或字段类型非法时记录告警并回退默认值；写入失败只记录告警，不影响当前
会话继续使用。写入采用同目录临时文件 + 原子替换，避免半截文件。首次读取
时若 user.yaml 尚不存在，会把旧版 ``ui_state.json`` 中的主题 / 语言 /
窗口尺寸迁移到 user.yaml。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

import yaml

from .sysx.config.paths import data_root
from .sysx.modules.logger_module import Logger

_FILE_NAME = "user.yaml"
_LEGACY_FILE = "ui_state.json"
_SUBDIR = "settings"
#: 用户配置显式版本号；文件缺失该键时按 v1 处理
SCHEMA_VERSION = 3
_SCHEMA_KEY = "schema_version"
#: 允许持久化的字段（与 AppSettings / 外观配置一一对应）
SUPPORTED_FIELDS = (
    "theme_name",
    "language",
    "menu_mode",
    "startup_size",
    "acrylic_transparency",
    "glass_strength",
    "background_image",
    "background_fit",
    "background_recent",
)

#: 背景图的适应模式（与 Windows 个性化设置一致）
BACKGROUND_FIT_MODES = ("fill", "fit", "stretch", "tile", "center")

# FIX-02: v3 新增的背景字段默认值，供 v2→v3 迁移按需补齐。
V3_BACKGROUND_DEFAULTS: dict[str, Any] = {
    "background_image": "",
    "background_fit": BACKGROUND_FIT_MODES[0],
    "background_recent": [],
}

# FIX-02: 显式记录版本跃迁计划：(目标版本, 该版本新增字段默认值, 跃迁说明)。
# 迁移按序跨过每个目标版本，从旧版本一路演进到 SCHEMA_VERSION。
MIGRATION_STEPS: tuple[tuple[int, dict[str, Any], str], ...] = (
    (2, {}, "v1→v2：引入显式 schema_version，字段语义不变"),
    (3, V3_BACKGROUND_DEFAULTS, "v2→v3：新增 background_image / background_fit / background_recent"),
)

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def user_settings_path() -> Path:
    """返回用户覆盖层文件路径（不保证已存在）。"""
    return data_root() / _SUBDIR / _FILE_NAME


def _normalize_field(key: str, value: Any) -> Any | None:
    """校验并归一化单个字段；不合法返回 ``None``。"""
    if key in ("theme_name", "language"):
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None
    if key == "menu_mode":
        return value if value in ("static", "overlay") else None
    if key in ("acrylic_transparency", "glass_strength"):
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if 0 <= value <= 100 else None
    if key == "startup_size":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        if not all(isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in value):
            return None
        return [int(value[0]), int(value[1])]
    if key == "background_image":
        if isinstance(value, str):
            return value.strip()
        return None
    if key == "background_fit":
        return value if value in BACKGROUND_FIT_MODES else None
    if key == "background_recent":
        if not isinstance(value, (list, tuple)):
            return None
        paths = [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]
        return list(dict.fromkeys(paths))[:5]
    return None


def _read_raw() -> dict[str, Any]:
    """读取磁盘上的原始 YAML 字典（不做字段白名单过滤）。

    FIX-02: 供 :func:`save_user_settings` 回写时保留未知键与原版本号；
    文件缺失、读取失败、解析失败或顶层不是字典时一律回退为空字典，
    不记录日志（读取路径的告警仍由 :func:`_read_file` 负责）。
    """
    path = user_settings_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:  # FileNotFoundError 是 OSError 子类，缺失同样视为「无原始内容」
        return {}
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_file() -> dict[str, Any]:
    """读取并校验 YAML；任何异常都回退为空字典。"""
    path = user_settings_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        Logger.warning(f"用户配置读取失败，使用默认值: {path}: {exc}")
        return {}

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        Logger.warning(f"用户配置解析失败，使用默认值: {path}: {exc}")
        return {}

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        Logger.warning(f"用户配置顶层必须是字典，已忽略: {path}")
        return {}

    version = raw.get(_SCHEMA_KEY, 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        Logger.warning(f"用户配置版本号非法，按 v1 处理: {path}")
        version = 1
    if version > SCHEMA_VERSION:
        # 文件由更新版本写入：只读取当前版本认识的字段，不覆盖未知数据
        Logger.warning(f"用户配置版本 {version} 高于当前 {SCHEMA_VERSION}，仅读取已知字段: {path}")

    state: dict[str, Any] = {}
    invalid: list[str] = []
    for key in SUPPORTED_FIELDS:
        if key not in raw:
            continue
        normalized = _normalize_field(key, raw[key])
        if normalized is None:
            invalid.append(key)
            continue
        state[key] = normalized
    if invalid:
        Logger.warning(f"用户配置字段值非法，已忽略: {', '.join(invalid)}（{path}）")
    unknown = sorted(str(key) for key in raw if key not in SUPPORTED_FIELDS and key != _SCHEMA_KEY)
    if unknown:
        # 汇总成一条 warning，避免用户误以为手改的配置已经生效
        Logger.warning(f"用户配置存在未支持字段（已忽略）: {', '.join(unknown)}（{path}）")
    return _migrate_state(state, version)


def _migrate_state(
    state: dict[str, Any],
    version: int,
    *,
    fill_defaults: bool = False,
    transitions: list[str] | None = None,
) -> dict[str, Any]:
    """把旧版本字段按 :data:`MIGRATION_STEPS` 迁移到当前 :data:`SCHEMA_VERSION`。

    FIX-02: 显式记录 v1→v2→v3 的版本跃迁——每跨过一个目标版本就把该步说明
    追加到 ``transitions``（供测试/诊断核对），并在 ``fill_defaults=True`` 时
    为该版新增字段补默认值。迁移只「补」不「删」：已有键一律保留且不被默认值
    覆盖，返回新字典，不修改入参。

    增量覆盖层读取时保持 ``fill_defaults=False``：user.yaml 只记录改动过的键，
    缺失字段继续由下层配置提供，避免把空默认值写回用户文件污染数据。
    """
    migrated = dict(state)
    for target_version, defaults, step in MIGRATION_STEPS:
        if version >= target_version:
            continue
        if transitions is not None:
            transitions.append(step)
        if fill_defaults:
            for key, default in defaults.items():
                migrated.setdefault(key, default)
    return migrated


def _read_legacy_state() -> dict[str, Any]:
    """读取旧版 ``ui_state.json`` 并映射为当前字段（仅迁移一次）。"""
    path = data_root() / _LEGACY_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        Logger.warning(f"旧 UI 状态读取失败，已跳过迁移: {path}: {exc}")
        return {}
    if not isinstance(raw, dict):
        return {}

    candidates = {
        "theme_name": raw.get("theme"),
        # 旧版把窗口尺寸写在 window_size，迁移时映射为 startup_size
        "startup_size": raw.get("window_size"),
        "language": raw.get("language"),
    }
    migrated: dict[str, Any] = {}
    for key, value in candidates.items():
        normalized = _normalize_field(key, value)
        if normalized is not None:
            migrated[key] = normalized
    return migrated


def load_user_settings() -> dict[str, Any]:
    """读取用户覆盖层（首次读取后缓存，返回副本）。"""
    global _CACHE
    with _LOCK:
        if _CACHE is None:
            state = _read_file()
            # user.yaml 尚不存在时，把旧版 ui_state.json 里的偏好迁移过来，
            # 避免升级后用户需要重新手动设置一次。
            if not state and not user_settings_path().is_file():
                legacy = _read_legacy_state()
                if legacy:
                    try:
                        # FIX-02: _write_atomic 现在直接写完整 payload，旧状态迁移需自带版本号。
                        _write_atomic(user_settings_path(), {_SCHEMA_KEY: SCHEMA_VERSION, **legacy})
                    except (OSError, yaml.YAMLError) as exc:
                        Logger.warning(f"旧 UI 状态迁移失败，本次仍按内存值生效: {exc}")
                    state = legacy
            _CACHE = state
        return dict(_CACHE)


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """把完整 payload 写入唯一临时文件、fsync 后原子替换；失败清理并抛原异常。

    FIX-02: 临时文件由 ``tempfile.mkstemp`` 生成，避免固定 ``.<pid>.tmp``
    在并发/多进程下相撞；写入后 ``os.fsync`` 再 ``os.replace``，保证落盘。
    payload 由调用方构造（已含 schema_version 与未知键），本函数不再注入版本，
    因此不会把高版本文件降级、也不会丢弃未知字段。
    """
    body = "# SllkGUI 用户配置（运行时自动维护，可手动编辑）\n"
    body += yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def save_user_settings(**updates: Any) -> bool:
    """合并并写入用户覆盖层；成功返回 ``True``，失败记录告警并返回 ``False``。

    只接受 :data:`SUPPORTED_FIELDS` 中的键；非法键 / 非法值会被忽略。
    写入失败时保留内存值以便后续重试，磁盘上的旧文件保持原样。

    FIX-02: 回写前读取磁盘原始 YAML，payload 以原始内容打底、叠加内存态，
    并沿用原文件的 ``schema_version``；高版本不降级、未知键不丢失。
    """
    global _CACHE
    clean: dict[str, Any] = {}
    rejected: list[str] = []
    for key, value in updates.items():
        if key not in SUPPORTED_FIELDS:
            rejected.append(key)
            continue
        normalized = _normalize_field(key, value)
        if normalized is None:
            rejected.append(key)
            continue
        clean[key] = normalized
    if rejected:
        Logger.warning(f"用户配置忽略不支持的字段或非法值: {', '.join(rejected)}")
    if not clean:
        return False

    with _LOCK:
        previous = dict(_CACHE) if _CACHE is not None else _read_file()
        state = {**previous, **clean}
        # 先入内存：即便本次落盘失败，后续任一成功的保存也会把这次改动带上
        _CACHE = state
        # FIX-02: 以磁盘原始内容打底，叠加内存里已合并的干净已知字段（含本次
        # clean），既保留 raw 的未知键，也不丢历史/重试的已知字段改动。
        raw = _read_raw()
        original_version: int = SCHEMA_VERSION
        candidate = raw.get(_SCHEMA_KEY)
        if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 1:
            original_version = candidate  # 原文件版本（含高版本），绝不降级
        payload: dict[str, Any] = {**raw, **state, _SCHEMA_KEY: original_version}
        try:
            _write_atomic(user_settings_path(), payload)
        except (OSError, yaml.YAMLError) as exc:
            # FIX-02: fsync / replace 的 OSError 仍返回 False，但日志保留异常类型与消息。
            Logger.warning(
                f"用户配置保存失败，将在下次保存时重试: "
                f"{user_settings_path()}: {type(exc).__name__}: {exc}"
            )
            return False
        return True


def reset_user_settings_cache() -> None:
    """丢弃内存缓存（数据目录切换或测试使用）。"""
    global _CACHE
    with _LOCK:
        _CACHE = None


__all__ = [
    "BACKGROUND_FIT_MODES",
    "SCHEMA_VERSION",
    "SUPPORTED_FIELDS",
    "load_user_settings",
    "reset_user_settings_cache",
    "save_user_settings",
    "user_settings_path",
]
