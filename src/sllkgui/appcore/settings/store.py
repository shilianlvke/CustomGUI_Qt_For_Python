"""设置存储：基座写 ``settings/user.yaml``，插件按命名空间分文件。

为什么分文件
------------
- 基座配置沿用历史 ``user.yaml`` 的扁平键（``theme_name`` 等），升级不需要
  迁移旧文件；写入白名单仍由 :mod:`sllkgui.appcore.user_settings` 把关。
- 插件配置写 ``settings/plugins/<plugin_id>.yaml``。一个插件一个文件，卸载、
  备份、排查都只影响自己；即使两个插件声明了同名键也不会互相覆盖。
- 所有写入都是「临时文件 + fsync + 原子替换」，失败只记日志并返回 False，
  不阻断当前会话。

本模块不导入 Qt。
"""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ..sysx.config.paths import data_root
from ..sysx.modules.logger_module import Logger
from ..user_settings import load_user_settings, save_user_settings, user_settings_path
from .schema import is_core_namespace, normalize_namespace

_PLUGIN_DIR = "plugins"
_PLUGIN_SCHEMA_VERSION = 1
_SCHEMA_KEY = "schema_version"
_PLUGIN_ID_KEY = "plugin_id"
_VALUES_KEY = "values"


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except OSError as exc:
        Logger.warning(f"插件配置读取失败，使用默认值: {path}: {exc}")
        return {}
    except yaml.YAMLError as exc:
        Logger.warning(f"插件配置解析失败，使用默认值: {path}: {exc}")
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_atomic(path: Path, payload: Mapping[str, Any], header: str) -> None:
    body = f"# {header}\n"
    body += yaml.safe_dump(dict(payload), allow_unicode=True, default_flow_style=False, sort_keys=True)
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


class CoreSettingsBackend:
    """基座配置后端：委托既有的 user.yaml 增量覆盖层。"""

    def load(self) -> dict[str, Any]:
        return dict(load_user_settings())

    def save(self, updates: Mapping[str, Any]) -> bool:
        return bool(save_user_settings(**dict(updates)))

    def path(self) -> Path:
        return user_settings_path()


class PluginSettingsBackend:
    """插件配置后端：每个插件一份 YAML，未知键在回写时保留。"""

    def __init__(self, root: Path):
        self._root = Path(root)
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def root(self) -> Path:
        return self._root

    def path(self, plugin_id: str) -> Path:
        return self._root / _PLUGIN_DIR / f"{plugin_id}.yaml"

    def load(self, plugin_id: str) -> dict[str, Any]:
        with self._lock:
            cached = self._cache.get(plugin_id)
            if cached is not None:
                return dict(cached)
            raw = _read_yaml(self.path(plugin_id))
            values = raw.get(_VALUES_KEY)
            if isinstance(values, dict):
                state = {str(key): value for key, value in values.items()}
            else:
                # 兼容早期手写的扁平文件：元数据键之外都视为配置值
                state = {str(key): value for key, value in raw.items() if key not in (_SCHEMA_KEY, _PLUGIN_ID_KEY)}
            self._cache[plugin_id] = state
            return dict(state)

    def save(self, plugin_id: str, updates: Mapping[str, Any]) -> bool:
        if not updates:
            return True
        with self._lock:
            current = self.load(plugin_id)
            merged = {**current, **{str(key): value for key, value in updates.items()}}
            payload = {
                _SCHEMA_KEY: _PLUGIN_SCHEMA_VERSION,
                _PLUGIN_ID_KEY: plugin_id,
                _VALUES_KEY: merged,
            }
            path = self.path(plugin_id)
            try:
                _write_atomic(path, payload, f"SllkGUI 插件配置 · {plugin_id}（运行时自动维护，可手动编辑）")
            except (OSError, yaml.YAMLError) as exc:
                Logger.warning(f"插件配置保存失败: {path}: {type(exc).__name__}: {exc}")
                return False
            self._cache[plugin_id] = merged
            return True

    def invalidate(self, plugin_id: str | None = None) -> None:
        with self._lock:
            if plugin_id is None:
                self._cache.clear()
            else:
                self._cache.pop(plugin_id, None)


class SettingsStore:
    """按命名空间路由到对应后端，供会话与插件上下文共用。"""

    def __init__(
        self,
        *,
        settings_dir: Path | str | None = None,
        core: CoreSettingsBackend | None = None,
        plugins: PluginSettingsBackend | None = None,
    ):
        # 目录只保存原始配置，真正的插件后端在首次使用时解析：宿主可能在
        # import 之后才调用 configure(data_dir=...)，过早固定路径会写错目录。
        self._settings_dir = settings_dir
        self._core = core if core is not None else CoreSettingsBackend()
        self._plugins = plugins
        self._lock = threading.RLock()

    def _plugin_backend(self) -> PluginSettingsBackend:
        with self._lock:
            if self._plugins is None:
                base = Path(self._settings_dir) if self._settings_dir is not None else data_root() / "settings"
                self._plugins = PluginSettingsBackend(base)
            return self._plugins

    # ------------------------------------------------------------------
    def load(self, namespace: str) -> dict[str, Any]:
        target = normalize_namespace(namespace)
        if is_core_namespace(target):
            return self._core.load()
        return self._plugin_backend().load(_plugin_id(target))

    def save(self, namespace: str, updates: Mapping[str, Any]) -> bool:
        target = normalize_namespace(namespace)
        clean = {str(key): value for key, value in updates.items()}
        if not clean:
            return True
        if is_core_namespace(target):
            return self._core.save(clean)
        return self._plugin_backend().save(_plugin_id(target), clean)

    def path_for(self, namespace: str) -> Path | None:
        target = normalize_namespace(namespace)
        if is_core_namespace(target):
            return self._core.path()
        return self._plugin_backend().path(_plugin_id(target))

    def invalidate(self, namespace: str | None = None) -> None:
        if self._plugins is None:
            return
        if namespace is None:
            self._plugins.invalidate()
            return
        target = normalize_namespace(namespace)
        if not is_core_namespace(target):
            self._plugins.invalidate(_plugin_id(target))

    @property
    def plugin_root(self) -> Path:
        return self._plugin_backend().root()


def _plugin_id(namespace: str) -> str:
    return namespace.split(".", 1)[1]


_STORE = SettingsStore()


def settings_store() -> SettingsStore:
    """进程级共享存储（插件运行时与设置窗口必须看到同一份缓存）。"""
    return _STORE


__all__ = [
    "CoreSettingsBackend",
    "PluginSettingsBackend",
    "SettingsStore",
    "settings_store",
]
