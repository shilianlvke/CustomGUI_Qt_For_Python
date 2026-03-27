"""模块说明。"""

import importlib
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from easydict import EasyDict

from AppCore.SYS.logger import Logger
from AppCore.SYS.module.error_module import DomainErrorBoundary
from AppCore.SYS.module.settings_module import validate_language_data, validate_settings_data, validate_theme_data
from AppCore.SYS.other.resource_locator import ResourceLocator


class ConfigHandler:
    """配置资源加载器。

    职责:
    - 扫描并加载语言、主题、系统配置等 YAML 资源。
    - 执行分组配置校验并统一抛出领域异常。
    """

    languages = r"resource/CustomUI/languages"
    themes = r"resource/CustomUI/themes/"
    others = r"resource/CustomUI/others/"
    settings = r"resource/CustomUI/settings/"

    @staticmethod
    def _build_named_yaml_map(path_list: list[str]) -> EasyDict:
        """按文件名构建 YAML 数据映射。

        参数:
        - path_list: YAML 文件路径列表。

        返回:
        - EasyDict: ``name -> {path, data}`` 的映射。
        """
        yaml_handler = importlib.import_module("AppCore.SYS.handler.yaml_handler").YamlHandler

        result = EasyDict()
        for path in path_list:
            name = Path(path).stem.lower()
            result[name] = EasyDict(path=path, data=yaml_handler(path))
        return result

    @staticmethod
    def _validate_group(
        group: EasyDict,
        validator: Callable[..., object] | None,
        *,
        error_code: str,
        error_message: str,
        validator_arg_name: str,
    ) -> None:
        """校验分组配置数据。

        参数:
        - group: 分组配置映射。
        - validator: 校验函数。
        - error_code: 失败错误码。
        - error_message: 失败错误消息。
        - validator_arg_name: 传入校验函数的命名参数名。

        返回:
        - None
        """
        if validator is None:
            return
        for name, item in group.items():
            try:
                validator(item.data.data, **{validator_arg_name: name})
            except ValueError as exc:
                raise DomainErrorBoundary(
                    code=error_code,
                    message=error_message,
                    details=str(exc),
                ) from exc

    @dataclass(frozen=True)
    class _ValidationOptions:
        """分组配置校验选项。"""

        validator: Callable[..., object] | None
        error_code: str
        error_message: str
        validator_arg_name: str

    def _load_group(
        self,
        directory: str,
        *,
        log_label: str,
        validation: _ValidationOptions | None = None,
    ) -> EasyDict:
        """按目录加载并可选校验配置分组。

        参数:
        - directory: 资源目录。
        - log_label: 日志标签。
        - validation: 可选校验参数对象。

        返回:
        - EasyDict: 分组配置映射。
        """
        path_list = ResourceLocator.find_files_by_extension(".yml", directory)
        group = self._build_named_yaml_map(path_list)
        if validation and validation.validator:
            self._validate_group(
                group,
                validation.validator,
                error_code=validation.error_code,
                error_message=validation.error_message,
                validator_arg_name=validation.validator_arg_name,
            )
        Logger.debug(f"{log_label}:{group.keys()}")
        return group

    def find_languages(self) -> EasyDict:
        """加载并校验语言配置组。"""
        return self._load_group(
            self.languages,
            log_label="语言",
            validation=self._ValidationOptions(
                validator=validate_language_data,
                error_code="LANGUAGE_CONFIG_INVALID",
                error_message="语言配置校验失败",
                validator_arg_name="language_name",
            ),
        )

    def find_themes(self) -> EasyDict:
        """加载并校验主题配置组。"""
        return self._load_group(
            self.themes,
            log_label="主题色",
            validation=self._ValidationOptions(
                validator=validate_theme_data,
                error_code="THEME_CONFIG_INVALID",
                error_message="主题配置校验失败",
                validator_arg_name="theme_name",
            ),
        )

    def find_others(self) -> EasyDict:
        """加载其他配置组。"""
        return self._load_group(self.others, log_label="其他配置")

    def find_settings(self) -> EasyDict:
        """加载并汇总系统配置。

        返回:
        - EasyDict: 合并后的系统配置对象。
        """
        settings = self._load_group(self.settings, log_label="配置")
        result = EasyDict()
        for value in settings.values():
            result.update(value.data.data)
        try:
            validate_settings_data(result)
        except ValueError as exc:
            raise DomainErrorBoundary(
                code="SETTINGS_CONFIG_INVALID",
                message="系统配置校验失败",
                details=str(exc),
            ) from exc
        return result


class AppContext:
    """应用上下文对象。

    职责:
    - 持有 settings/themes/languages/others 四类运行时配置。
    - 提供线程安全的懒加载与强制重载能力。
    """

    def __init__(self, config_handler: ConfigHandler) -> None:
        """初始化应用上下文。

        参数:
        - config_handler: 配置加载器。

        返回:
        - None
        """
        self._config_handler = config_handler
        self._loaded = False
        self.settings = None
        self.themes = None
        self.languages = None
        self.others = None
        self._load_lock = threading.Lock()

    def load(self, *, force_reload: bool = False) -> "AppContext":
        """加载应用配置上下文。

        参数:
        - force_reload: 是否强制重载。

        返回:
        - AppContext: 当前上下文实例。
        """
        with self._load_lock:
            if self._loaded and not force_reload:
                return self

            self.settings = self._config_handler.find_settings()
            self.themes = self._config_handler.find_themes()
            self.languages = self._config_handler.find_languages()
            self.others = self._config_handler.find_others()
            self._loaded = True
        return self


class _ContextView:
    """上下文视图代理。

    职责:
    - 延迟读取 AppContext 中的指定分组。
    - 提供字典与属性访问兼容能力。
    """

    def __init__(self, key: str) -> None:
        """初始化上下文视图。

        参数:
        - key: AppContext 中的目标属性名。
        """
        self._key = key

    def _target(self) -> object:
        """获取当前视图对应的真实对象。"""
        return getattr(get_app_context(), self._key)

    def __getattr__(self, item: str) -> object:
        """代理属性读取。"""
        return getattr(self._target(), item)

    def __getitem__(self, item: object) -> object:
        """代理字典下标读取。"""
        return self._target()[item]

    def __iter__(self) -> Iterator[object]:
        """返回迭代器。"""
        return iter(self._target())

    def __contains__(self, item: object) -> bool:
        """判断元素是否存在。"""
        return item in self._target()

    def __len__(self) -> int:
        """返回元素数量。"""
        return len(self._target())

    def get(self, key: object, default: object | None = None) -> object | None:
        """按键获取值并支持默认值。"""
        return self._target().get(key, default)

    def keys(self) -> object:
        """返回键视图。"""
        return self._target().keys()

    def values(self) -> object:
        """返回值视图。"""
        return self._target().values()

    def items(self) -> object:
        """返回键值对视图。"""
        return self._target().items()

    def __repr__(self) -> str:
        """返回调试表示。"""
        return repr(self._target())


class AppContextProvider:
    """应用上下文提供器。

    职责:
    - 管理 AppContext 单例生命周期。
    - 提供线程安全的获取与重载入口。
    """

    def __init__(self, config_handler: ConfigHandler) -> None:
        """初始化上下文提供器。"""
        self._config_handler = config_handler
        self._context: AppContext | None = None
        self._lock = threading.Lock()

    def get(self, *, force_reload: bool = False) -> AppContext:
        """获取应用上下文实例。

        参数:
        - force_reload: 是否强制重载。

        返回:
        - AppContext: 应用上下文对象。
        """
        if force_reload:
            with self._lock:
                if self._context is None:
                    self._context = AppContext(self._config_handler)
                return self._context.load(force_reload=True)

        if self._context is not None:
            return self._context.load(force_reload=False)

        with self._lock:
            if self._context is None:
                self._context = AppContext(self._config_handler)
            return self._context.load(force_reload=False)


_APP_CONTEXT_PROVIDER = AppContextProvider(ConfigHandler())


def get_app_context(*, force_reload: bool = False) -> AppContext:
    """获取全局应用上下文。

    参数:
    - force_reload: 是否强制重载。

    返回:
    - AppContext: 应用上下文对象。
    """
    return _APP_CONTEXT_PROVIDER.get(force_reload=force_reload)


def initialize_app_context(*, force_reload: bool = False) -> AppContext:
    """初始化应用上下文。

    参数:
    - force_reload: 是否强制重载。

    返回:
    - AppContext: 应用上下文对象。
    """
    return get_app_context(force_reload=force_reload)


AppSettings = _ContextView("settings")
AppThemes = _ContextView("themes")
AppLanguages = _ContextView("languages")
AppOthers = _ContextView("others")
