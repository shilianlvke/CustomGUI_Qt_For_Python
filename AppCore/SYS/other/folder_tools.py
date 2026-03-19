import os
import threading
from easydict import EasyDict
from ..handler import YamlHandler
from ..logger import Logger
from .resource_locator import ResourceLocator
from ..module.settings_module import (
    validate_language_data,
    validate_settings_data,
    validate_theme_data,
)
from ..module.error_module import DomainErrorBoundary


class ConfigHandler:

    languages = r"resource/CustomUI/languages"
    themes = r"resource/CustomUI/themes/"
    others = r"resource/CustomUI/others/"
    settings = r"resource/CustomUI/settings/"

    @staticmethod
    def _build_named_yaml_map(path_list: list[str]) -> EasyDict:
        result = EasyDict()
        for path in path_list:
            name = os.path.splitext(os.path.basename(path))[0].lower()
            result[name] = EasyDict(path=path, data=YamlHandler(path))
        return result

    @staticmethod
    def _validate_group(
        group: EasyDict,
        validator,
        *,
        error_code: str,
        error_message: str,
        validator_arg_name: str,
    ):
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

    def _load_group(
        self,
        directory: str,
        *,
        validator=None,
        error_code: str | None = None,
        error_message: str | None = None,
        validator_arg_name: str | None = None,
        log_label: str,
    ) -> EasyDict:
        path_list = ResourceLocator.find_files_by_extension(".yml", directory)
        group = self._build_named_yaml_map(path_list)
        if validator:
            self._validate_group(
                group,
                validator,
                error_code=error_code or "GROUP_CONFIG_INVALID",
                error_message=error_message or "配置校验失败",
                validator_arg_name=validator_arg_name or "name",
            )
        Logger.debug(f"{log_label}:{group.keys()}")
        return group

    def find_languages(self):
        return self._load_group(
            self.languages,
            validator=validate_language_data,
            error_code="LANGUAGE_CONFIG_INVALID",
            error_message="语言配置校验失败",
            validator_arg_name="language_name",
            log_label="语言",
        )

    def find_themes(self):
        return self._load_group(
            self.themes,
            validator=validate_theme_data,
            error_code="THEME_CONFIG_INVALID",
            error_message="主题配置校验失败",
            validator_arg_name="theme_name",
            log_label="主题色",
        )

    def find_others(self):
        return self._load_group(self.others, log_label="其他配置")

    def find_settings(self):
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
    def __init__(self, config_handler: ConfigHandler):
        self._config_handler = config_handler
        self._loaded = False
        self.settings = None
        self.themes = None
        self.languages = None
        self.others = None
        self._load_lock = threading.Lock()

    def load(self, force_reload: bool = False):
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
        return self._target().get(key, default)

    def keys(self):
        return self._target().keys()

    def values(self):
        return self._target().values()

    def items(self):
        return self._target().items()

    def __repr__(self):
        return repr(self._target())


class AppContextProvider:
    def __init__(self, config_handler: ConfigHandler):
        self._config_handler = config_handler
        self._context: AppContext | None = None
        self._lock = threading.Lock()

    def get(self, force_reload: bool = False) -> AppContext:
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


def get_app_context(force_reload: bool = False) -> AppContext:
    return _APP_CONTEXT_PROVIDER.get(force_reload=force_reload)


def initialize_app_context(force_reload: bool = False) -> AppContext:
    return get_app_context(force_reload=force_reload)


AppSettings = _ContextView("settings")
AppThemes = _ContextView("themes")
AppLanguages = _ContextView("languages")
AppOthers = _ContextView("others")
