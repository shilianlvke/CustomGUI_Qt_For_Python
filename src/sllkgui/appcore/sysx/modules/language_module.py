"""语言管理器：语言包容器、切换与变更通知（订阅模式）。

- ``Language`` 单例同时是「文本容器」与「切换协调器」；
- ``apply``：重装基座语言包 -> 注入 App 语言（通过注册的 provider）
  -> 通知订阅者（菜单/标题/页面等组件自刷新）；
- App 语言提供者由 ``sllkgui.gallery.loader`` 注册（sllkgui.appcore 不依赖表现层）；
- 订阅使用弱引用，组件销毁后自动移除。

使用::

    from sllkgui.appcore import Language

    Language.register_app_provider(lambda lang: {...})   # 表现层注册
    Language.apply("en_us")                               # 整体切换并广播
    Language.resolve("app.example.app_text")              # 点路径读取
"""

from __future__ import annotations

import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config.mapping import Attrs, to_attrs
from .logger_module import Logger
from .telemetry_module import record_event


def _fingerprint(data: dict) -> int:
    """给语言包数据算一个稳定的浅指纹（用于判断是否需要重新装载）。"""
    try:
        return hash(tuple(sorted(data.keys())))
    except Exception:
        return id(data)


def _discover_language_options() -> tuple[str, ...]:
    """Discover languages from the active base + overlay resource layers."""
    try:
        from ..config.paths import iter_files

        names = tuple(sorted(path.stem for path in iter_files("resource/sllkgui/languages", ".yaml")))
        if names:
            return names
    except Exception:
        pass
    return ("zh_cn", "en_us")


class LanguageOptions:
    """惰性、可缓存的可用语言序列。

    为什么必须是惰性的
    ------------------
    历史上这里是模块级一次性求值 ``LANGUAGE_OPTIONS = _discover()``，而
    模块导入发生在 ``sllkgui.configure()`` **之前**：那一刻资源根还没被
    配置，扫描只看到基座包内的语言文件。结果就是应用后来叠加上来的语言
    （PyCL2 的日语、繁体中文等）永远发现不了，应用只能把资源塞进项目根的
    ``resource/`` 里靠环境变量抢跑——这正是「应用根目录被迫保留 ``resource/``」
    的唯一技术原因。

    改为惰性视图后，每次读取都按**当前**资源根解析，调用方语义完全不变
    （``in`` / 迭代 / ``len`` / ``index`` / 下标都能用）。解析结果按资源根
    元组缓存，资源根不变就不会重复扫盘。
    """

    __slots__ = ("_cache_key", "_cache")

    def __init__(self) -> None:
        self._cache_key: tuple[str, ...] | None = None
        self._cache: tuple[str, ...] = ()

    # -- 解析与缓存 ----------------------------------------------------
    def _resolve(self) -> tuple[str, ...]:
        try:
            from ..config.paths import resource_roots

            key = tuple(str(path) for path in resource_roots())
        except Exception:
            return _discover_language_options()
        if key != self._cache_key:
            self._cache = _discover_language_options()
            self._cache_key = key
        return self._cache

    def invalidate(self) -> None:
        """丢弃缓存，下次读取重新扫描（``configure`` 后可由调用方触发）。"""
        self._cache_key = None
        self._cache = ()

    # -- 序列协议 ------------------------------------------------------
    def __iter__(self):
        return iter(self._resolve())

    def __contains__(self, item: object) -> bool:
        return item in self._resolve()

    def __len__(self) -> int:
        return len(self._resolve())

    def __getitem__(self, index):
        return self._resolve()[index]

    def index(self, value: str, *args) -> int:
        """``list.index`` 兼容——``LanguageHandler.cycle()`` 依赖它。"""
        return self._resolve().index(value, *args)

    def count(self, value: str) -> int:
        return self._resolve().count(value)

    def __repr__(self) -> str:
        return repr(self._resolve())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LanguageOptions):
            return self._resolve() == other._resolve()
        if isinstance(other, (tuple, list)):
            return list(self._resolve()) == list(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._resolve())


LANGUAGE_OPTIONS = LanguageOptions()


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
    _app_providers: list = field(default_factory=list)
    _signature: tuple | None = None
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
        """注册 App 语言提供者：``fn(lang) -> {app_name: {key: text}}``。

        支持注册多个提供者；切换语言时按注册顺序逐个调用并**深度合并**，
        后注册的提供者覆盖同名应用的键（历史单槽实现会直接覆盖先注册的
        提供者，导致多来源注入时丢数据）。
        """
        with self._lock:
            if provider not in self._app_providers:
                self._app_providers.append(provider)

    def _collect_app_languages(self, language: str) -> dict:
        """合并全部 App 语言提供者的结果（后注册者覆盖同名键）。"""
        merged: dict = {}
        for provider in list(self._app_providers):
            try:
                chunk = provider(language) or {}
            except Exception as exc:  # noqa: BLE001 - 单个提供者失败不影响其余
                Logger.warning(f"App 语言提供者执行失败: {exc}")
                continue
            if not isinstance(chunk, dict):
                Logger.warning(f"App 语言提供者返回非 dict，已忽略: {type(chunk).__name__}")
                continue
            merged.update(chunk)
        return merged

    def current(self) -> str:
        """当前语言（首次访问时取 AppSettings.language）。"""
        with self._lock:
            if self._current is None:
                from ..config import AppSettings

                self._current = AppSettings.language
            return self._current

    def apply(self, language: str) -> str:
        """整体切换语言并通知订阅者，返回新语言名。

        幂等性按**内容签名**判断而不是仅比较语言名：语言文件在运行期被
        追加/修改（例如换主题时顺带补翻译）也能重新装载，避免"同名语言
        永远读的是首次加载的内容"。
        """
        if language not in LANGUAGE_OPTIONS:
            raise ValueError(f"不支持的语言: {language}（可选: {LANGUAGE_OPTIONS}）")

        from ..config import AppLanguages

        data = AppLanguages[language].data
        signature = (language, len(data), _fingerprint(data))
        if self._current == language and self._signature == signature:
            return language

        self.replace(data)
        if self._app_providers:
            self.app = to_attrs(self._collect_app_languages(language))
        self._current = language
        self._signature = signature
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
        """退订（按等价回调移除，含绑定方法）。"""

        def _same(entry) -> bool:
            target = entry() if isinstance(entry, weakref.WeakMethod) else entry
            return target == callback

        with self._lock:
            self._listeners = [entry for entry in self._listeners if not _same(entry)]

    def _remove_listener(self, ref) -> None:
        with self._lock:
            if ref in self._listeners:
                self._listeners.remove(ref)

    def _bind_destroyed_cleanup(self, obj, ref) -> None:
        """鸭子类型连接 QObject.destroyed 信号（sllkgui.appcore 不依赖 PySide6）。"""
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


__all__ = ["Language", "LanguageHandler", "LanguageOptions", "LANGUAGE_OPTIONS"]
