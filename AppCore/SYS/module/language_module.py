"""语言管理器：语言包容器、切换与变更通知（订阅模式）。

- ``Language`` 单例同时是「文本容器」与「切换协调器」；
- ``apply``：重装基座语言包 -> 注入 App 语言（通过注册的 provider）
  -> 通知订阅者（菜单/标题/页面等组件自刷新）；
- App 语言提供者由 ``Guis.app_loader`` 注册（AppCore 不依赖表现层）；
- 订阅使用弱引用，组件销毁后自动移除。

使用::

    from AppCore import Language

    Language.register_app_provider(lambda lang: {...})   # 表现层注册
    Language.apply("en_us")                               # 整体切换并广播
    Language.resolve("app.example.app_text")              # 点路径读取
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config.mapping import Attrs, to_attrs
from .logger_module import Logger
from .telemetry_module import record_event

LANGUAGE_OPTIONS = ("zh_cn", "en_us")


@dataclass
class LanguageHandler:
    """语言包容器 + 切换协调器。

    - ``update``：增量合并（历史兼容）；
    - ``replace``：清空后整体替换（语言切换使用，避免旧语言残留键）；
    - ``resolve`` / ``resolve_key``：按点号路径读取文本，
      支持 ``language.app.example.app_text`` 形式的资源键引用；
    - ``apply``：整体切换语言并通知订阅者。
    """

    _current: str | None = None
    _listeners: list = field(default_factory=list)
    _app_provider: Callable[[str], dict] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # ------------------------------------------------------------------
    # 文本容器
    # ------------------------------------------------------------------
    def update(self, new_str: dict) -> None:
        for key, value in new_str.items():
            setattr(self, key, to_attrs(value))

    def replace(self, new_str: dict) -> None:
        """清空全部动态键并整体替换（实例属性即语言数据）。"""
        for key in list(self.__dict__):
            if key.startswith("_"):
                continue
            delattr(self, key)
        self.update(new_str)

    def resolve(self, path: str, default: Any = None) -> Any:
        """按点号路径读取嵌套文本，如 ``"app.p2ptest_home.app_text"``。"""
        value: Any = self
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, Attrs) and part in value:
                value = value[part]
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
        return value

    def resolve_key(self, key: str, default: Any = None) -> Any:
        """解析 ``language.<path>`` 资源键；非资源键原样返回。"""
        if isinstance(key, str) and key.startswith("language."):
            return self.resolve(key[len("language.") :], default if default is not None else key)
        return key

    # ------------------------------------------------------------------
    # 切换协调
    # ------------------------------------------------------------------
    def register_app_provider(self, provider: Callable[[str], dict]) -> None:
        """注册 App 语言提供者：``fn(lang) -> {app_name: {key: text}}``。"""
        self._app_provider = provider

    def current(self) -> str:
        """当前语言（首次访问时取 AppSettings.language）。"""
        with self._lock:
            if self._current is None:
                from ..config import AppSettings

                self._current = AppSettings.language
            return self._current

    def apply(self, language: str) -> str:
        """整体切换语言并通知订阅者，返回新语言名。

        相同语言重复调用直接返回（幂等，避免重复刷新与日志）。
        """
        if language not in LANGUAGE_OPTIONS:
            raise ValueError(f"不支持的语言: {language}（可选: {LANGUAGE_OPTIONS}）")

        if self._current == language:
            return language

        from ..config import AppLanguages

        self.replace(AppLanguages[language].data)
        if self._app_provider is not None:
            setattr(self, "app", to_attrs(self._app_provider(language) or {}))
        self._current = language
        self._notify()

        Logger.info(f"语言切换为 {language}")
        record_event("ui.language_switch", category="ui", payload={"language": language})
        return language

    def cycle(self) -> str:
        """在可用语言间循环切换。"""
        options = LANGUAGE_OPTIONS
        try:
            index = options.index(self.current())
        except ValueError:
            index = -1
        return self.apply(options[(index + 1) % len(options)])

    def subscribe(self, callback: Callable[[], None]) -> None:
        """订阅语言变更通知。

        绑定方法使用弱引用；若订阅者提供 ``destroyed`` 信号（如 QObject
        组件），自动连接信号在其销毁时退订，避免回调命中已删除的
        C++ 对象。普通函数/闭包使用强引用（需自行保证生命周期）。
        """
        with self._lock:
            import types

            if isinstance(callback, types.MethodType):
                ref = weakref.WeakMethod(callback)
                self._listeners.append(ref)
                self._bind_destroyed_cleanup(callback.__self__, ref)
            else:
                self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """退订（按等价回调移除）。"""
        with self._lock:
            self._listeners = [
                entry
                for entry in self._listeners
                if not (isinstance(entry, weakref.WeakMethod) and entry() is callback) and entry is not callback
            ]

    def _remove_listener(self, ref) -> None:
        with self._lock:
            if ref in self._listeners:
                self._listeners.remove(ref)

    def _bind_destroyed_cleanup(self, obj, ref) -> None:
        """鸭子类型连接 QObject.destroyed 信号（AppCore 不依赖 PySide6）。"""
        destroyed = getattr(obj, "destroyed", None)
        if destroyed is not None and callable(getattr(destroyed, "connect", None)):
            try:
                destroyed.connect(lambda *_args, _ref=ref: self._remove_listener(_ref))
            except Exception:
                pass

    @staticmethod
    def _is_deleted_cpp_error(exc: RuntimeError) -> bool:
        message = str(exc)
        return "Internal C++ object" in message or "has been deleted" in message

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for entry in listeners:
            callback = entry() if isinstance(entry, (weakref.WeakMethod, weakref.ref)) else entry
            if callback is None:
                continue
            try:
                callback()
            except RuntimeError as exc:
                if self._is_deleted_cpp_error(exc):
                    # C++ 对象已销毁：移除失效订阅，不再重试
                    self._remove_listener(entry)
                    Logger.debug(f"移除已销毁组件的语言订阅: {exc}")
                else:
                    Logger.warning(f"语言订阅回调执行失败: {exc}")
            except Exception as exc:
                Logger.warning(f"语言订阅回调执行失败: {exc}")


Language = LanguageHandler()


__all__ = ["Language", "LanguageHandler", "LANGUAGE_OPTIONS"]
