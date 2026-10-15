"""配置注册表：目录级加载、校验与线程安全的惰性单例。

对外入口（保持历史 API）：

- :func:`get_app_context` / :func:`initialize_app_context`：获取全局应用上下文；
- ``AppSettings`` / ``AppThemes`` / ``AppLanguages`` / ``AppOthers``：
  模块级惰性视图，首次访问时自动触发加载，之后直接命中缓存。

使用示例（新增配置文件同样生效，无需改代码）：::

    from AppCore import AppSettings, AppThemes

    theme = AppThemes[AppSettings.theme_name].data   # Attrs：属性/字典双访问
    AppSettings.lef_menu_size.minimum                 # 强类型 SizeRange
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..module.error_module import DomainErrorBoundary
from ..module.logger_module import Logger
from .mapping import Attrs, deep_merge, to_attrs
from .paths import iter_files
from .schema import (
    AppSettingsModel,
    validate_language_data,
    validate_settings_data,
    validate_theme_data,
)
from .yaml_io import load_yaml_file


@dataclass(frozen=True)
class ConfigFile:
    """一份已加载的配置文件。"""

    name: str
    path: Path
    data: Attrs


class ConfigGroup(Attrs):
    """一组配置文件（文件名 -> ConfigFile）。"""


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
    for path in iter_files(directory, ".yaml"):
        name = path.stem.lower()
        data = to_attrs(load_yaml_file(path))
        if validator is not None:
            try:
                validator(data, **{validator_arg: name})
            except ValueError as exc:
                raise DomainErrorBoundary(
                    code=error_code,
                    message=error_message,
                    details=str(exc),
                ) from exc
        group[name] = ConfigFile(name=name, path=path, data=data)

    Logger.debug(f"{log_label}: {sorted(group.keys())}")
    return group


class ConfigRegistry:
    """按目录加载并校验配置组。

    目录常量既可被子类覆盖，也可通过构造函数注入（测试中常用临时目录）。
    """

    SETTINGS_DIR = "resource/customui/settings"
    THEMES_DIR = "resource/customui/themes"
    LANGUAGES_DIR = "resource/customui/languages"
    OTHERS_DIR = "resource/customui/others"

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
        """加载并合并 settings 目录下全部 YAML，返回强类型模型。"""
        merged: dict = {}
        for path in iter_files(self.SETTINGS_DIR, ".yaml"):
            deep_merge(merged, load_yaml_file(path))

        try:
            model = validate_settings_data(merged)
        except ValueError as exc:
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


class AppContext:
    """已加载的应用配置上下文（settings / themes / languages / others）。"""

    def __init__(self, registry: ConfigRegistry):
        self._registry = registry
        self._loaded = False
        self._load_lock = threading.Lock()
        self.settings: AppSettingsModel | None = None
        self.themes: ConfigGroup | None = None
        self.languages: ConfigGroup | None = None
        self.others: ConfigGroup | None = None

    def load(self, force_reload: bool = False) -> "AppContext":
        with self._load_lock:
            if self._loaded and not force_reload:
                return self

            self.settings = self._registry.load_settings()
            self.themes = self._registry.load_themes()
            self.languages = self._registry.load_languages()
            self.others = self._registry.load_others()
            self._loaded = True
        return self


class _AppContextProvider:
    """全局单例提供者：双重检查锁定，保证线程安全的惰性初始化。"""

    def __init__(self, registry: ConfigRegistry):
        self._registry = registry
        self._context: AppContext | None = None
        self._lock = threading.Lock()

    def get(self, force_reload: bool = False) -> AppContext:
        context = self._context
        if context is not None and not force_reload:
            return context.load(force_reload=False)

        with self._lock:
            if self._context is None:
                self._context = AppContext(self._registry)
            return self._context.load(force_reload=force_reload)


_REGISTRY = ConfigRegistry()
_PROVIDER = _AppContextProvider(_REGISTRY)


def get_app_context(force_reload: bool = False) -> AppContext:
    """获取全局应用配置上下文（首次调用时惰性加载）。"""
    return _PROVIDER.get(force_reload=force_reload)


def initialize_app_context(force_reload: bool = False) -> AppContext:
    """显式初始化（等价于 get_app_context，保留历史入口）。"""
    return get_app_context(force_reload=force_reload)


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
    "AppContext",
    "get_app_context",
    "initialize_app_context",
    "AppSettings",
    "AppThemes",
    "AppLanguages",
    "AppOthers",
]
