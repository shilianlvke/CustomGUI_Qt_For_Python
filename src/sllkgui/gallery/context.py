"""``GalleryContext`` 实现：把插件能力收敛到基座统一入口。

日志、遥测、计时、错误上报都带 ``[plugin:<id>@<version>]`` 前缀与插件元数据；
i18n 只查内存表（``resource/lang/*.yml`` 在 on_load 前加载完毕）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sllkgui.appcore import Language, Logger, get_theme_manager, record_event, track_timing

from .api import GalleryContext, Permission
from .defaults import MAX_EVENT_BYTES
from .manifest import PluginManifest, ensure_within
from .store import GalleryStore

_LEVELS = {
    "debug": Logger.debug,
    "info": Logger.info,
    "warning": Logger.warning,
    "error": Logger.error,
    "critical": Logger.critical,
}
_TITLE_KEYS = ("zh_cn", "zh_tw", "en_us", "ja_jp")


def _flatten(data: Any, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(value, child))
    elif isinstance(data, (str, int, float, bool)):
        result[prefix] = str(data)
    return result


class _BridgeHandler(logging.Handler):
    """把标准库 logging 记录桥接到基座 Logger（不创建任何文件 handler）。"""

    def __init__(self, prefix: str) -> None:
        super().__init__()
        self._prefix = prefix

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = f"{self._prefix} {record.getMessage()}"
            if record.exc_info:
                Logger.exception(message)
            else:
                _LEVELS.get(record.levelname.lower(), Logger.info)(message)
        except Exception:  # noqa: BLE001 - 日志桥自身不能影响业务
            pass


class GalleryContextImpl(GalleryContext):
    def __init__(
        self,
        manifest: PluginManifest,
        store: GalleryStore,
        *,
        language_data: dict[str, dict[str, str]] | None = None,
        open_surface: Callable[[str, str], bool] | None = None,
        parent_window: Callable[[], Any] | None = None,
        error_reporter: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self._manifest = manifest
        self._store = store
        self._language = language_data or {}
        self._open_surface_cb = open_surface
        self._parent_window_cb = parent_window
        self._error_reporter = error_reporter
        self._record = None
        self._prefix = f"[plugin:{manifest.plugin_id}@{manifest.version}]"
        self._logger_name = f"sllkgui.plugin.{manifest.plugin_id}"
        self._logger = logging.getLogger(self._logger_name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        if not getattr(self._logger, "_sllkgui_bridged", False):
            self._logger.addHandler(_BridgeHandler(self._prefix))
            self._logger._sllkgui_bridged = True  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # 元数据
    # ------------------------------------------------------------------
    @property
    def plugin_id(self) -> str:
        return self._manifest.plugin_id

    @property
    def plugin_version(self) -> str:
        return self._manifest.version

    @property
    def data_dir(self) -> Path:
        data, _cache = self._store.ensure_plugin_data(self.plugin_id)
        return data

    @property
    def cache_dir(self) -> Path:
        _data, cache = self._store.ensure_plugin_data(self.plugin_id)
        return cache

    @property
    def locale(self) -> str:
        return Language.current()

    @property
    def theme(self) -> str:
        return get_theme_manager().current()

    @property
    def permissions(self) -> tuple[Permission, ...]:
        return tuple(self._manifest.permissions)

    # ------------------------------------------------------------------
    # 资源与导航
    # ------------------------------------------------------------------
    def resource(self, *parts: str) -> Path:
        relative = "/".join(["resource", *[str(item) for item in parts]])
        return ensure_within(self._manifest.root, relative)

    def open_surface(self, surface_id: str) -> bool:
        if self._open_surface_cb is None:
            return False
        return bool(self._open_surface_cb(self.plugin_id, surface_id))

    def parent_window(self) -> Any:
        return self._parent_window_cb() if self._parent_window_cb else None

    # ------------------------------------------------------------------
    # 语言
    # ------------------------------------------------------------------
    def text(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        locale = self.locale
        table = self._language.get(locale) or self._language.get("en_us") or {}
        template = table.get(str(key))
        if template is None:
            return default if default is not None else key
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return template

    # ------------------------------------------------------------------
    # 日志 / 遥测
    # ------------------------------------------------------------------
    def log(self, message: str, level: str = "info") -> None:
        _LEVELS.get(str(level).lower(), Logger.info)(f"{self._prefix} {message}")

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def event(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        if self._record is not None:
            self._record.telemetry_seen = True
        merged = {"plugin_id": self.plugin_id, "plugin_version": self.plugin_version}
        if payload:
            merged.update({str(key): value for key, value in payload.items()})
        try:
            size = len(str(merged).encode("utf-8"))
            if size > MAX_EVENT_BYTES:
                Logger.warning(f"{self._prefix} 遥测事件过大（{size} 字节），已截断 payload")
                merged = {"plugin_id": self.plugin_id, "plugin_version": self.plugin_version, "truncated": True}
            record_event(str(name), category="plugin", level=str(level), payload=merged)
        except Exception as exc:  # noqa: BLE001 - 遥测不得影响业务
            Logger.debug(f"{self._prefix} 遥测写入失败: {exc}")

    @contextmanager
    def timing(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Iterator[None]:
        merged = {"plugin_id": self.plugin_id, "plugin_version": self.plugin_version}
        if payload:
            merged.update(dict(payload))
        with track_timing(str(name), category="plugin", payload=merged):
            yield

    def report_error(self, code: str, message: str, detail: str | None = None) -> None:
        self.log(f"{code}: {message}", "error")
        if detail:
            Logger.debug(f"{self._prefix} {code} detail: {detail}")
        self.event("plugin.error", {"code": code, "message": message}, level="error")
        if self._error_reporter is not None:
            try:
                self._error_reporter(code, message, detail or "")
            except Exception:  # noqa: BLE001 - 提示失败不影响业务
                pass

    # ------------------------------------------------------------------
    # 语言表（由 loader 注入）
    # ------------------------------------------------------------------
    def language_data(self) -> dict[str, dict[str, str]]:
        return self._language

    def set_language_data(self, data: dict[str, dict[str, str]]) -> None:
        self._language = data


__all__ = ["GalleryContextImpl", "_flatten"]
