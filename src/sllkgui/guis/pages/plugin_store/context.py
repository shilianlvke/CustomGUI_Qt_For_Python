"""原生页面上下文：与插件 ctx 同名方法，页面无需感知自己已脱离插件协议。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QWidget

from sllkgui.appcore import Language, Logger, record_event, track_timing

#: 原生页面的语言命名空间（语言文件里的 ``plugin_store`` 顶层节点）
_TEXT_NAMESPACE = "language.plugin_store"


class PageContext:
    """原生页面上下文：只覆盖插件管理页用到的基座能力。

    与插件上下文保持同名方法，页面代码无需感知自己已经脱离插件协议。
    """

    def __init__(self, parent_provider: Callable[[], QWidget | None]) -> None:
        self._parent_provider = parent_provider

    def text(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        value = str(Language.resolve_key(f"{_TEXT_NAMESPACE}.{key}", default if default is not None else key))
        if not kwargs:
            return value
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return value

    def log(self, message: str, level: str = "info") -> None:
        writer = {
            "debug": Logger.debug,
            "warning": Logger.warning,
            "warn": Logger.warning,
            "error": Logger.error,
            "critical": Logger.critical,
        }.get(str(level).lower(), Logger.info)
        writer(f"[plugin-store] {message}")

    def event(self, name: str, payload: Any = None, level: str = "info") -> None:
        record_event(str(name), category="ui", level=str(level), payload=dict(payload or {}))

    def timing(self, name: str, payload: Any = None):
        return track_timing(str(name), category="ui", payload=dict(payload or {}))

    def report_error(self, code: str, message: str, detail: str | None = None) -> None:
        self.log(f"{code}: {message}", "error")
        if detail:
            Logger.debug(f"[plugin-store] {code} detail: {detail}")
        try:
            runtime = self.runtime()
            if runtime is not None:
                runtime.last_error = {"code": code, "message": message, "detail": detail or ""}
        except Exception:  # noqa: BLE001 - 错误记录失败不影响页面
            pass
        self.event("plugin_store.error", {"code": code, "message": message}, level="error")

    def runtime(self):
        """窗口持有的插件运行时。

        原生页面归装配层管，这里按鸭子类型从窗口取，``guis`` 不 import ``gallery``；
        未接入 Gallery 的宿主返回 ``None``（页面照常可用，只是没有插件动作）。
        """
        return getattr(self.parent_window(), "runtime", None)

    def parent_window(self) -> QWidget | None:
        return self._parent_provider()
