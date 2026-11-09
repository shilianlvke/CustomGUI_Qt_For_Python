"""配置注册表：目录级加载、校验与线程安全的惰性单例。

对外入口：

- :func:`get_app_context`：获取全局配置上下文（首次调用时惰性加载）；
- ``AppSettings`` / ``AppThemes`` / ``AppLanguages`` / ``AppOthers``：
  模块级惰性视图，首次访问时自动触发加载，之后直接命中缓存。

使用示例（新增配置文件同样生效，无需改代码）：::

    from sllkgui.appcore import AppSettings, AppThemes

    theme = AppThemes[AppSettings.theme_name].data   # Attrs：属性/字典双访问
    AppSettings.lef_menu_size.minimum                 # 强类型 SizeRange
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config.mapping import Attrs, deep_merge, to_attrs
from ..config.paths import iter_file_layers
from ..config.schema import (
    AppSettingsModel,
    validate_language_data,
    validate_settings_data,
    validate_theme_data,
)
from ..config.yaml_io import load_yaml_file
from ..modules.error_module import DomainErrorBoundary, IOErrorBoundary
from ..modules.logger_module import Logger


@dataclass(frozen=True)
class ConfigFile:
    """一份已加载的配置（同名的各资源层已合并）。

    ``data`` 是合并后的视图，``path`` 是**最高优先级**那一层（品牌层 / 覆盖层），
    也就是「想改这份配置时该编辑的文件」；``sources`` 列出参与合并的全部层
    （低 -> 高），排查覆盖关系时按它看。
    """

    name: str
    path: Path
    data: Attrs
    sources: tuple[Path, ...] = ()


class ConfigGroup(Attrs):
    """一组配置文件（文件名 -> ConfigFile）。"""


def _merge_layers(paths: tuple[Path, ...]) -> Attrs:
    """把同一文件的多个资源层按「低 -> 高」顺序深合并成一份视图。

    覆盖层的职责是「只写要改的键」，基座后续新增的键继续生效——这正是
    :func:`iter_files` 做不到的部分（同名文件整份替换会把基座那层挤掉，
    基座升级加了必填字段，下游就在启动校验时崩）。
    """
    merged: dict = {}
    for path in paths:
        deep_merge(merged, load_yaml_file(path))
    return to_attrs(merged)


def _load_group(
    directory: str,
    *,
    validator: Callable | None = None,
    validator_arg: str = "name",
    error_code: str = "GROUP_CONFIG_INVALID",
    error_message: str = "配置校验失败",
    log_label: str,
) -> ConfigGroup:
    group = ConfigGroup()
    for key, paths in sorted(iter_file_layers(directory, ".yaml").items()):
        name = Path(key).stem.lower()
        try:
            # FIX-08: load_yaml_file() 会抛 IOErrorBoundary（文件缺失/解析失败），
            # 与校验的 ValueError 一起统一包装为带错误码的 DomainErrorBoundary。
            data = _merge_layers(paths)
            if validator is not None:
                validator(data, **{validator_arg: name})
        except (ValueError, IOErrorBoundary) as exc:
            raise DomainErrorBoundary(
                code=error_code,
                message=error_message,
                details=str(exc),
            ) from exc
        group[name] = ConfigFile(name=name, path=paths[-1], data=data, sources=paths)

    Logger.debug(f"{log_label}: {sorted(group.keys())}")
    return group


class ConfigRegistry:
    """按目录加载并校验配置组。

    目录常量既可被子类覆盖，也可通过构造函数注入（测试中常用临时目录）。
    """

    SETTINGS_DIR = "resource/sllkgui/settings"
    THEMES_DIR = "resource/sllkgui/themes"
    LANGUAGES_DIR = "resource/sllkgui/languages"
    OTHERS_DIR = "resource/sllkgui/others"

    def __init__(
        self,
        *,
        settings_dir: str | None = None,
        themes_dir: str | None = None,
        languages_dir: str | None = None,
        others_dir: str | None = None,
    ) -> None:
        for name, value in (
            ("SETTINGS_DIR", settings_dir),
            ("THEMES_DIR", themes_dir),
            ("LANGUAGES_DIR", languages_dir),
            ("OTHERS_DIR", others_dir),
        ):
            if value is not None:
                setattr(self, name, value)

    def load_settings(self) -> AppSettingsModel:
        """装载 settings 目录下全部 YAML，同名文件按资源层逐层深合并。

        顺序很关键：基座包内的 ``window.yaml`` 先打底，品牌层的同名文件再逐键
        覆盖。这样应用只需要写「想改的那几个键」，基座新增的必填字段仍然能拿到
        ——历史实现按「同名只取高优先级那份」装载，品牌层缺了新字段就直接
        崩在 :class:`DomainErrorBoundary`（``SETTINGS_CONFIG_INVALID``）。
        """
        merged: dict = {}
        try:
            # FIX-08: 逐层 load_yaml_file() 抛出的 IOErrorBoundary 也要包装，
            # 不再裸穿透；与 validate_settings_data 的 ValueError 统一处理。
            for key, paths in sorted(iter_file_layers(self.SETTINGS_DIR, ".yaml").items()):
                for path in paths:
                    deep_merge(merged, load_yaml_file(path))
                Logger.debug(f"系统设置层: {key} <- {[path.name for path in paths]}")
            model = validate_settings_data(merged)
        except (ValueError, IOErrorBoundary) as exc:
            raise DomainErrorBoundary(
                code="SETTINGS_CONFIG_INVALID",
                message="系统配置校验失败",
                details=str(exc),
            ) from exc
        Logger.debug(f"系统设置: {sorted(merged)}")
        return model

    def load_themes(self) -> ConfigGroup:
        return _load_group(
            self.THEMES_DIR,
            validator=validate_theme_data,
            validator_arg="theme_name",
            error_code="THEME_CONFIG_INVALID",
            error_message="主题配置校验失败",
            log_label="主题",
        )

    def load_languages(self) -> ConfigGroup:
        return _load_group(
            self.LANGUAGES_DIR,
            validator=validate_language_data,
            validator_arg="language_name",
            error_code="LANGUAGE_CONFIG_INVALID",
            error_message="语言配置校验失败",
            log_label="语言",
        )

    def load_others(self) -> ConfigGroup:
        return _load_group(self.OTHERS_DIR, log_label="其他配置")


@dataclass(frozen=True)
class _ContextData:
    """一次加载的 4 组配置快照（FIX-07）。

    :meth:`ConfigContext.load` 把 4 组配置先全部装进这个不可变快照，再以**单次
    引用赋值**发布。读侧（:class:`_ContextView`）不持锁，因此永远只能看到
    完整的旧快照或完整的新快照，不会读到 ``None`` 或半初始化状态。
    """

    settings: AppSettingsModel
    themes: ConfigGroup
    languages: ConfigGroup
    others: ConfigGroup


class ConfigContext:
    """已加载的配置上下文（settings / themes / languages / others）。

    注意与 :class:`sllkgui.guis.app_loader.AppContext`（应用插件上下文）区分：
    本类是配置框架内部对象，不对外导出。

    FIX-07: 4 个分组通过 :class:`_ContextData` 快照整体发布，避免
    ``load(force_reload=True)`` 并发时读侧看到逐字段赋值的中间状态。
    """

    def __init__(self, registry: ConfigRegistry):
        self._registry = registry
        self._loaded = False
        self._load_lock = threading.Lock()
        self._data: _ContextData | None = None

    def _snapshot(self) -> _ContextData:
        data = self._data
        if data is None:  # pragma: no cover - get_app_context() 总是先 load()
            raise RuntimeError("配置上下文尚未加载")
        return data

    @property
    def settings(self) -> AppSettingsModel:
        return self._snapshot().settings

    @property
    def themes(self) -> ConfigGroup:
        return self._snapshot().themes

    @property
    def languages(self) -> ConfigGroup:
        return self._snapshot().languages

    @property
    def others(self) -> ConfigGroup:
        return self._snapshot().others

    def load(self, force_reload: bool = False) -> ConfigContext:
        with self._load_lock:
            if self._loaded and not force_reload:
                return self

            # FIX-07: 先把 4 组配置全部加载进局部变量，再一次性覆盖快照；
            # 全过程绝不清空 self._data，加载失败时旧快照继续可用。
            settings = self._registry.load_settings()
            themes = self._registry.load_themes()
            languages = self._registry.load_languages()
            others = self._registry.load_others()
            self._data = _ContextData(
                settings=settings, themes=themes, languages=languages, others=others
            )
            self._loaded = True
        return self


class _ConfigContextProvider:
    """全局单例提供者：双重检查锁定，保证线程安全的惰性初始化。"""

    def __init__(self, registry: ConfigRegistry):
        self._registry = registry
        self._context: ConfigContext | None = None
        self._lock = threading.Lock()

    def get(self, force_reload: bool = False) -> ConfigContext:
        context = self._context
        if context is not None and not force_reload:
            return context.load(force_reload=False)

        with self._lock:
            if self._context is None:
                self._context = ConfigContext(self._registry)
            return self._context.load(force_reload=force_reload)

    def is_loaded(self) -> bool:
        """上下文是否已加载；与写入共享同一把锁，避免读到过期状态。"""
        with self._lock:
            return self._context is not None


_REGISTRY = ConfigRegistry()
_PROVIDER = _ConfigContextProvider(_REGISTRY)


def get_app_context(force_reload: bool = False) -> ConfigContext:
    """获取全局配置上下文（首次调用时惰性加载）。"""
    return _PROVIDER.get(force_reload=force_reload)


def is_context_loaded() -> bool:
    """配置上下文是否已加载（供 ``sllkgui.configure()`` 判断调用时机）。"""
    return _PROVIDER.is_loaded()


def reset_context() -> None:
    """丢弃已加载的上下文（供 ``configure(force_reload=True)`` 与测试使用）。"""
    with _PROVIDER._lock:
        _PROVIDER._context = None


class _ContextView:
    """模块级惰性视图：把 ``get_app_context()`` 的某个分组代理为
    属性/字典访问对象，首次访问时自动触发加载。"""

    def __init__(self, key: str):
        self._key = key

    def _target(self):
        return getattr(get_app_context(), self._key)

    def __getattr__(self, item):
        return getattr(self._target(), item)

    def __getitem__(self, item):
        return self._target()[item]

    def __iter__(self):
        return iter(self._target())

    def __contains__(self, item):
        return item in self._target()

    def __len__(self):
        return len(self._target())

    def get(self, key, default=None):
        target = self._target()
        getter = getattr(target, "get", None)
        if callable(getter):
            return getter(key, default)
        try:
            return getattr(target, key)
        except AttributeError:
            return default

    def keys(self):
        return self._target().keys()

    def values(self):
        return self._target().values()

    def items(self):
        return self._target().items()

    def __repr__(self):
        return repr(self._target())


AppSettings = _ContextView("settings")
AppThemes = _ContextView("themes")
AppLanguages = _ContextView("languages")
AppOthers = _ContextView("others")


__all__ = [
    "Attrs",
    "ConfigFile",
    "ConfigGroup",
    "ConfigRegistry",
    "ConfigContext",
    "get_app_context",
    "AppSettings",
    "AppThemes",
    "AppLanguages",
    "AppOthers",
]
