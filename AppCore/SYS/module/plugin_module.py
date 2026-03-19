from dataclasses import dataclass, replace
import importlib
from pathlib import Path
from typing import Any, Callable

from .error_module import DomainErrorBoundary


SUPPORTED_PLUGIN_PROTOCOL_VERSIONS = {"1"}


@dataclass(frozen=True)
class PagePlugin:
    plugin_id: str
    button_id: str
    page_object: str
    title_getter: Callable[[Any], str]
    loader: Callable[[Any], None] | None = None
    default: bool = False
    enabled: bool = True
    protocol_version: str = "1"


@dataclass(frozen=True)
class MenuPlugin:
    plugin_id: str
    target: str
    item: dict
    enabled: bool = True
    protocol_version: str = "1"


@dataclass(frozen=True)
class CommandPlugin:
    plugin_id: str
    command_id: str
    handler: Callable[..., Any]
    enabled: bool = True
    protocol_version: str = "1"


class PluginRegistry:
    def __init__(self):
        self._pages: dict[str, PagePlugin] = {}
        self._menus: dict[str, MenuPlugin] = {}
        self._commands: dict[str, CommandPlugin] = {}
        self._load_errors: list[str] = []
        self._protocol_adapters: dict[str, Callable[[Any], Any]] = {}

    @staticmethod
    def _validate_protocol(plugin):
        version = getattr(plugin, "protocol_version", "1")
        if version not in SUPPORTED_PLUGIN_PROTOCOL_VERSIONS:
            raise DomainErrorBoundary(
                code="PLUGIN_PROTOCOL_UNSUPPORTED",
                message="插件协议版本不兼容",
                details=f"{getattr(plugin, 'plugin_id', 'unknown')}:{version}",
            )

    def register_protocol_adapter(self, from_version: str, adapter: Callable[[Any], Any]):
        self._protocol_adapters[str(from_version)] = adapter

    def _adapt_plugin_protocol_if_needed(self, plugin):
        version = str(getattr(plugin, "protocol_version", "1"))
        if version in SUPPORTED_PLUGIN_PROTOCOL_VERSIONS:
            return plugin

        adapter = self._protocol_adapters.get(version)
        if adapter is None:
            self._validate_protocol(plugin)
            return plugin

        try:
            adapted = adapter(plugin)
        except Exception as exc:
            raise DomainErrorBoundary(
                code="PLUGIN_PROTOCOL_ADAPT_FAILED",
                message="插件协议迁移失败",
                details=f"{getattr(plugin, 'plugin_id', 'unknown')}:{version}: {exc}",
            ) from exc

        self._validate_protocol(adapted)
        return adapted

    @property
    def load_errors(self) -> list[str]:
        return list(self._load_errors)

    @property
    def supported_protocol_versions(self) -> set[str]:
        return set(SUPPORTED_PLUGIN_PROTOCOL_VERSIONS)

    def is_protocol_supported(self, version: str) -> bool:
        return str(version) in SUPPORTED_PLUGIN_PROTOCOL_VERSIONS

    def clear_load_errors(self):
        self._load_errors.clear()

    def register_page(self, plugin: PagePlugin):
        plugin = self._adapt_plugin_protocol_if_needed(plugin)
        self._validate_protocol(plugin)
        if plugin.plugin_id in self._pages:
            raise DomainErrorBoundary(
                code="PLUGIN_DUPLICATE_PAGE",
                message="页面插件重复注册",
                details=plugin.plugin_id,
            )
        self._pages[plugin.plugin_id] = plugin

    def register_menu(self, plugin: MenuPlugin):
        plugin = self._adapt_plugin_protocol_if_needed(plugin)
        self._validate_protocol(plugin)
        if plugin.plugin_id in self._menus:
            raise DomainErrorBoundary(
                code="PLUGIN_DUPLICATE_MENU",
                message="菜单插件重复注册",
                details=plugin.plugin_id,
            )
        self._menus[plugin.plugin_id] = plugin

    def register_command(self, plugin: CommandPlugin):
        plugin = self._adapt_plugin_protocol_if_needed(plugin)
        self._validate_protocol(plugin)
        if plugin.plugin_id in self._commands:
            raise DomainErrorBoundary(
                code="PLUGIN_DUPLICATE_COMMAND",
                message="命令插件重复注册",
                details=plugin.plugin_id,
            )
        self._commands[plugin.plugin_id] = plugin

    def unregister_plugin(self, plugin_id: str) -> bool:
        removed = False
        if plugin_id in self._pages:
            del self._pages[plugin_id]
            removed = True
        if plugin_id in self._menus:
            del self._menus[plugin_id]
            removed = True
        if plugin_id in self._commands:
            del self._commands[plugin_id]
            removed = True
        return removed

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> bool:
        if plugin_id in self._pages:
            self._pages[plugin_id] = replace(self._pages[plugin_id], enabled=enabled)
            return True
        if plugin_id in self._menus:
            self._menus[plugin_id] = replace(self._menus[plugin_id], enabled=enabled)
            return True
        if plugin_id in self._commands:
            self._commands[plugin_id] = replace(self._commands[plugin_id], enabled=enabled)
            return True
        return False

    def enable_plugin(self, plugin_id: str) -> bool:
        return self.set_plugin_enabled(plugin_id, True)

    def disable_plugin(self, plugin_id: str) -> bool:
        return self.set_plugin_enabled(plugin_id, False)

    def register_plugin(self, plugin):
        if isinstance(plugin, PagePlugin):
            self.register_page(plugin)
            return
        if isinstance(plugin, MenuPlugin):
            self.register_menu(plugin)
            return
        if isinstance(plugin, CommandPlugin):
            self.register_command(plugin)
            return
        raise DomainErrorBoundary(
            code="PLUGIN_TYPE_UNSUPPORTED",
            message="不支持的插件类型",
            details=type(plugin).__name__,
        )

    def load_plugins(self, plugins: list, strict: bool = False) -> dict:
        report = {"loaded": 0, "failed": 0}
        for plugin in plugins:
            try:
                self.register_plugin(plugin)
                report["loaded"] += 1
            except Exception as exc:
                report["failed"] += 1
                self._load_errors.append(f"{getattr(plugin, 'plugin_id', 'unknown')}: {exc}")
                if strict:
                    raise
        return report

    @staticmethod
    def _default_manifest_path() -> str:
        root = Path(__file__).resolve().parents[4]
        return str(root / "resource" / "CustomUI" / "settings" / "plugins.yml")

    @staticmethod
    def _normalize_manifest_modules(raw_data) -> list[str]:
        modules: list[str] = []

        direct = getattr(raw_data, "plugin_modules", None)
        if isinstance(direct, list):
            modules.extend(str(item).strip() for item in direct if str(item).strip())

        plugins_node = getattr(raw_data, "plugins", None)
        if plugins_node is not None:
            nested = getattr(plugins_node, "modules", None)
            if isinstance(nested, list):
                modules.extend(str(item).strip() for item in nested if str(item).strip())

        # Keep original order while removing duplicates.
        deduped = list(dict.fromkeys(modules))
        return deduped

    def discover_plugin_modules(self, manifest_path: str | None = None) -> list[str]:
        path = manifest_path or self._default_manifest_path()
        if not Path(path).exists():
            return []
        from ..handler import YamlHandler
        data = YamlHandler(path).data
        return self._normalize_manifest_modules(data)

    def load_plugins_from_modules(self, module_paths: list[str], strict: bool = False) -> dict:
        report = {"modules_loaded": 0, "modules_failed": 0, "plugins_loaded": 0, "plugins_failed": 0}

        for module_path in module_paths:
            try:
                module = importlib.import_module(module_path)
                report["modules_loaded"] += 1
            except Exception as exc:
                report["modules_failed"] += 1
                self._load_errors.append(f"module:{module_path}: {exc}")
                if strict:
                    raise
                continue

            try:
                if hasattr(module, "register_plugins") and callable(module.register_plugins):
                    module.register_plugins(self)
                    continue

                module_plugins = getattr(module, "PLUGINS", None)
                if module_plugins is None:
                    raise DomainErrorBoundary(
                        code="PLUGIN_MODULE_ENTRY_MISSING",
                        message="插件模块缺少入口",
                        details=f"{module_path}: register_plugins/PLUGINS",
                    )

                load_report = self.load_plugins(list(module_plugins), strict=strict)
                report["plugins_loaded"] += int(load_report.get("loaded", 0))
                report["plugins_failed"] += int(load_report.get("failed", 0))
            except Exception as exc:
                report["modules_failed"] += 1
                self._load_errors.append(f"module:{module_path}: {exc}")
                if strict:
                    raise

        return report

    def discover_and_load_plugins(self, manifest_path: str | None = None, strict: bool = False) -> dict:
        modules = self.discover_plugin_modules(manifest_path=manifest_path)
        return self.load_plugins_from_modules(modules, strict=strict)

    def has_page(self, plugin_id: str) -> bool:
        return plugin_id in self._pages

    def page_plugins(self):
        return [plugin for plugin in self._pages.values() if plugin.enabled]

    def menu_plugins(self, target: str):
        return [plugin for plugin in self._menus.values() if plugin.enabled and plugin.target == target]

    def command_plugins(self):
        return [plugin for plugin in self._commands.values() if plugin.enabled]

    def load_page_plugins(self, window, on_error: Callable[[PagePlugin, Exception], None] | None = None):
        for plugin in self.page_plugins():
            if plugin.loader:
                try:
                    plugin.loader(window)
                except Exception as exc:
                    self._load_errors.append(f"{plugin.plugin_id}: {exc}")
                    if on_error:
                        on_error(plugin, exc)

    def build_page_routes(self, language, title_fallback: Callable[[str], str]):
        routes = {}
        for plugin in self.page_plugins():
            try:
                title = plugin.title_getter(language)
            except Exception:
                title = title_fallback(plugin.button_id)
            routes[plugin.button_id] = (plugin.page_object, title)
        return routes

    def get_default_page_object(self):
        pages = self.page_plugins()
        for plugin in pages:
            if plugin.default:
                return plugin.page_object
        if not pages:
            return ""
        return pages[0].page_object

    def apply_menu_plugins(self, base_items: list, target: str):
        result = list(base_items)
        for plugin in self.menu_plugins(target):
            result.append(plugin.item)
        return result

    def execute_command(self, command_id: str, *args, **kwargs):
        for plugin in self.command_plugins():
            if plugin.command_id == command_id:
                try:
                    return plugin.handler(*args, **kwargs)
                except Exception as exc:
                    self._load_errors.append(f"{plugin.plugin_id}: {exc}")
                    return None
        return None


_PLUGIN_REGISTRY = PluginRegistry()


def get_plugin_registry(reset: bool = False) -> PluginRegistry:
    global _PLUGIN_REGISTRY
    if reset:
        _PLUGIN_REGISTRY = PluginRegistry()
    return _PLUGIN_REGISTRY
