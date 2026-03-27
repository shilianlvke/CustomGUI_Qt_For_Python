"""模块说明。"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NoReturn

from .error_module import DomainErrorBoundary

SUPPORTED_PLUGIN_PROTOCOL_VERSIONS = {"1"}
PLUGIN_ADAPTER_EXCEPTIONS = (RuntimeError, TypeError, ValueError, AttributeError)
PLUGIN_RUNTIME_EXCEPTIONS = (
    DomainErrorBoundary,
    ImportError,
    RuntimeError,
    TypeError,
    ValueError,
    AttributeError,
)


@dataclass(frozen=True)
class PagePlugin:
    """页面插件描述对象。"""

    plugin_id: str
    button_id: str
    page_object: str
    title_getter: Callable[[object], str]
    loader: Callable[[object], None] | None = None
    default: bool = False
    enabled: bool = True
    protocol_version: str = "1"


@dataclass(frozen=True)
class MenuPlugin:
    """菜单插件描述对象。"""

    plugin_id: str
    target: str
    item: dict
    enabled: bool = True
    protocol_version: str = "1"


@dataclass(frozen=True)
class CommandPlugin:
    """命令插件描述对象。"""

    plugin_id: str
    command_id: str
    handler: Callable[..., object]
    enabled: bool = True
    protocol_version: str = "1"


class PluginRegistry:
    """插件注册中心。

    职责:
    - 管理页面、菜单、命令插件的注册与查询。
    - 处理插件协议兼容、发现与加载。
    - 记录插件加载与执行过程中的错误信息。
    """

    def __init__(self) -> None:
        """初始化插件注册中心实例。

        返回:
        - None
        """
        self._pages: dict[str, PagePlugin] = {}
        self._menus: dict[str, MenuPlugin] = {}
        self._commands: dict[str, CommandPlugin] = {}
        self._load_errors: list[str] = []
        self._protocol_adapters: dict[str, Callable[[object], object]] = {}

    @staticmethod
    def _validate_protocol(plugin: object) -> None:
        """校验插件协议版本是否受支持。

        参数:
        - plugin: 任意插件对象。

        返回:
        - None
        """
        version = getattr(plugin, "protocol_version", "1")
        if version not in SUPPORTED_PLUGIN_PROTOCOL_VERSIONS:
            raise DomainErrorBoundary(
                code="PLUGIN_PROTOCOL_UNSUPPORTED",
                message="插件协议版本不兼容",
                details=f"{getattr(plugin, 'plugin_id', 'unknown')}:{version}",
            )

    def register_protocol_adapter(self, from_version: str, adapter: Callable[[object], object]) -> None:
        """注册协议迁移适配器。

        参数:
        - from_version: 旧协议版本号。
        - adapter: 将旧插件对象转换为受支持版本的函数。

        返回:
        - None
        """
        self._protocol_adapters[str(from_version)] = adapter

    def _adapt_plugin_protocol_if_needed(self, plugin: object) -> object:
        """按需执行插件协议迁移。

        参数:
        - plugin: 待适配插件对象。

        返回:
        - Any: 适配后的插件对象。
        """
        version = str(getattr(plugin, "protocol_version", "1"))
        if version in SUPPORTED_PLUGIN_PROTOCOL_VERSIONS:
            return plugin

        adapter = self._protocol_adapters.get(version)
        if adapter is None:
            self._validate_protocol(plugin)
            return plugin

        try:
            adapted = adapter(plugin)
        except PLUGIN_ADAPTER_EXCEPTIONS as exc:
            raise DomainErrorBoundary(
                code="PLUGIN_PROTOCOL_ADAPT_FAILED",
                message="插件协议迁移失败",
                details=f"{getattr(plugin, 'plugin_id', 'unknown')}:{version}: {exc}",
            ) from exc

        self._validate_protocol(adapted)
        return adapted

    @property
    def load_errors(self) -> list[str]:
        """获取加载与执行错误列表快照。

        返回:
        - list[str]: 当前错误信息副本。
        """
        return list(self._load_errors)

    @property
    def supported_protocol_versions(self) -> set[str]:
        """获取受支持的插件协议版本集合。

        返回:
        - set[str]: 支持的协议版本集合。
        """
        return set(SUPPORTED_PLUGIN_PROTOCOL_VERSIONS)

    def is_protocol_supported(self, version: str) -> bool:
        """判断指定协议版本是否受支持。

        参数:
        - version: 协议版本号。

        返回:
        - bool: 是否受支持。
        """
        return str(version) in SUPPORTED_PLUGIN_PROTOCOL_VERSIONS

    def clear_load_errors(self) -> None:
        """清空错误记录。

        返回:
        - None
        """
        self._load_errors.clear()

    def register_page(self, plugin: PagePlugin) -> None:
        """注册页面插件。

        参数:
        - plugin: 页面插件对象。

        返回:
        - None
        """
        plugin = self._adapt_plugin_protocol_if_needed(plugin)
        self._validate_protocol(plugin)
        if plugin.plugin_id in self._pages:
            raise DomainErrorBoundary(
                code="PLUGIN_DUPLICATE_PAGE",
                message="页面插件重复注册",
                details=plugin.plugin_id,
            )
        self._pages[plugin.plugin_id] = plugin

    def register_menu(self, plugin: MenuPlugin) -> None:
        """注册菜单插件。

        参数:
        - plugin: 菜单插件对象。

        返回:
        - None
        """
        plugin = self._adapt_plugin_protocol_if_needed(plugin)
        self._validate_protocol(plugin)
        if plugin.plugin_id in self._menus:
            raise DomainErrorBoundary(
                code="PLUGIN_DUPLICATE_MENU",
                message="菜单插件重复注册",
                details=plugin.plugin_id,
            )
        self._menus[plugin.plugin_id] = plugin

    def register_command(self, plugin: CommandPlugin) -> None:
        """注册命令插件。

        参数:
        - plugin: 命令插件对象。

        返回:
        - None
        """
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
        """注销插件。

        参数:
        - plugin_id: 插件唯一标识。

        返回:
        - bool: 至少移除了一个插件实体时为 True。
        """
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

    def set_plugin_enabled(self, plugin_id: str, *, enabled: bool) -> bool:
        """设置插件启用状态。

        参数:
        - plugin_id: 插件唯一标识。
        - enabled: 目标启用状态。

        返回:
        - bool: 更新成功时为 True。
        """
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
        """启用指定插件。

        参数:
        - plugin_id: 插件唯一标识。

        返回:
        - bool: 操作是否成功。
        """
        return self.set_plugin_enabled(plugin_id, enabled=True)

    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用指定插件。

        参数:
        - plugin_id: 插件唯一标识。

        返回:
        - bool: 操作是否成功。
        """
        return self.set_plugin_enabled(plugin_id, enabled=False)

    def register_plugin(self, plugin: object) -> None:
        """按插件类型分发注册。

        参数:
        - plugin: 插件对象，支持 PagePlugin/MenuPlugin/CommandPlugin。

        返回:
        - None
        """
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

    @staticmethod
    def _raise_if_strict(*, strict: bool, exc: Exception) -> None:
        """严格模式下重抛捕获的异常。"""
        if strict:
            raise exc

    @staticmethod
    def _raise_module_entry_missing(module_path: str) -> NoReturn:
        """抛出缺少插件入口异常。"""
        raise DomainErrorBoundary(
            code="PLUGIN_MODULE_ENTRY_MISSING",
            message="插件模块缺少入口",
            details=f"{module_path}: register_plugins/PLUGINS",
        )

    def load_plugins(self, plugins: list[object], *, strict: bool = False) -> dict[str, int]:
        """批量加载插件对象列表。

        参数:
        - plugins: 插件对象列表。
        - strict: 严格模式；True 时首次失败即抛出异常。

        返回:
        - dict: 加载报告，包含 loaded/failed 计数。
        """
        report = {"loaded": 0, "failed": 0}
        for plugin in plugins:
            try:
                self.register_plugin(plugin)
                report["loaded"] += 1
            except PLUGIN_RUNTIME_EXCEPTIONS as exc:
                report["failed"] += 1
                self._load_errors.append(f"{getattr(plugin, 'plugin_id', 'unknown')}: {exc}")
                self._raise_if_strict(strict=strict, exc=exc)
        return report

    @staticmethod
    def _default_manifest_path() -> str:
        """获取默认插件清单路径。

        返回:
        - str: 默认 ``plugins.yml`` 文件路径字符串。
        """
        root = Path(__file__).resolve().parents[4]
        return str(root / "resource" / "CustomUI" / "settings" / "plugins.yml")

    @staticmethod
    def _yaml_handler_type() -> type:
        """延迟解析 YamlHandler 类型以规避导入环。"""
        module = importlib.import_module("AppCore.SYS.handler.yaml_handler")
        return module.YamlHandler

    @staticmethod
    def _normalize_manifest_modules(raw_data: object) -> list[str]:
        """标准化清单中的插件模块列表。

        参数:
        - raw_data: 清单解析后的对象。

        返回:
        - list[str]: 去重并保序的模块路径列表。
        """
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
        return list(dict.fromkeys(modules))

    def discover_plugin_modules(self, manifest_path: str | None = None) -> list[str]:
        """从清单文件发现插件模块路径。

        参数:
        - manifest_path: 清单文件路径；为空时使用默认路径。

        返回:
        - list[str]: 发现到的模块路径列表。
        """
        path = manifest_path or self._default_manifest_path()
        if not Path(path).exists():
            return []

        data = self._yaml_handler_type()(path).data
        return self._normalize_manifest_modules(data)

    def load_plugins_from_modules(self, module_paths: list[str], *, strict: bool = False) -> dict[str, int]:
        """按模块路径加载插件。

        参数:
        - module_paths: Python 模块路径列表。
        - strict: 严格模式；True 时失败立即抛出异常。

        返回:
        - dict: 模块与插件加载统计报告。
        """
        report = {"modules_loaded": 0, "modules_failed": 0, "plugins_loaded": 0, "plugins_failed": 0}

        for module_path in module_paths:
            try:
                module = importlib.import_module(module_path)
                report["modules_loaded"] += 1
            except PLUGIN_RUNTIME_EXCEPTIONS as exc:
                report["modules_failed"] += 1
                self._load_errors.append(f"module:{module_path}: {exc}")
                self._raise_if_strict(strict=strict, exc=exc)
                continue

            try:
                if hasattr(module, "register_plugins") and callable(module.register_plugins):
                    module.register_plugins(self)
                    continue

                module_plugins = getattr(module, "PLUGINS", None)
                if module_plugins is None:
                    self._raise_module_entry_missing(module_path)

                load_report = self.load_plugins(list(module_plugins), strict=strict)
                report["plugins_loaded"] += int(load_report.get("loaded", 0))
                report["plugins_failed"] += int(load_report.get("failed", 0))
            except PLUGIN_RUNTIME_EXCEPTIONS as exc:
                report["modules_failed"] += 1
                self._load_errors.append(f"module:{module_path}: {exc}")
                self._raise_if_strict(strict=strict, exc=exc)

        return report

    def discover_and_load_plugins(self, manifest_path: str | None = None, *, strict: bool = False) -> dict[str, int]:
        """发现并加载插件模块。

        参数:
        - manifest_path: 清单文件路径；为空时使用默认路径。
        - strict: 严格模式。

        返回:
        - dict: 插件加载统计报告。
        """
        modules = self.discover_plugin_modules(manifest_path=manifest_path)
        return self.load_plugins_from_modules(modules, strict=strict)

    def has_page(self, plugin_id: str) -> bool:
        """判断页面插件是否已注册。

        参数:
        - plugin_id: 页面插件标识。

        返回:
        - bool: 是否存在对应页面插件。
        """
        return plugin_id in self._pages

    def has_menu(self, plugin_id: str) -> bool:
        """判断菜单插件是否已注册。

        参数:
        - plugin_id: 菜单插件标识。

        返回:
        - bool: 是否存在对应菜单插件。
        """
        return plugin_id in self._menus

    def page_plugins(self) -> list[PagePlugin]:
        """获取启用状态的页面插件列表。

        返回:
        - list[PagePlugin]: 已启用页面插件集合。
        """
        return [plugin for plugin in self._pages.values() if plugin.enabled]

    def menu_plugins(self, target: str) -> list[MenuPlugin]:
        """获取指定目标菜单的启用插件列表。

        参数:
        - target: 菜单目标标识。

        返回:
        - list[MenuPlugin]: 匹配目标的启用菜单插件。
        """
        return [plugin for plugin in self._menus.values() if plugin.enabled and plugin.target == target]

    def command_plugins(self) -> list[CommandPlugin]:
        """获取启用状态的命令插件列表。

        返回:
        - list[CommandPlugin]: 已启用命令插件集合。
        """
        return [plugin for plugin in self._commands.values() if plugin.enabled]

    def load_page_plugins(
        self,
        window: object,
        on_error: Callable[[PagePlugin, Exception], None] | None = None,
    ) -> None:
        """执行页面插件的加载回调。

        参数:
        - window: 主窗口对象。
        - on_error: 可选错误回调，签名为 ``(plugin, exc)``。

        返回:
        - None
        """
        for plugin in self.page_plugins():
            if plugin.loader:
                try:
                    plugin.loader(window)
                except PLUGIN_RUNTIME_EXCEPTIONS as exc:
                    self._load_errors.append(f"{plugin.plugin_id}: {exc}")
                    if on_error:
                        on_error(plugin, exc)

    def build_page_routes(self, language: object, title_fallback: Callable[[str], str]) -> dict[str, tuple[str, str]]:
        """构建按钮到页面路由映射。

        参数:
        - language: 当前语言对象。
        - title_fallback: 获取后备标题的函数。

        返回:
        - dict: ``button_id -> (page_object, title)`` 的映射。
        """
        routes = {}
        for plugin in self.page_plugins():
            try:
                title = plugin.title_getter(language)
            except PLUGIN_RUNTIME_EXCEPTIONS:
                title = title_fallback(plugin.button_id)
            routes[plugin.button_id] = (plugin.page_object, title)
        return routes

    def get_default_page_object(self) -> str:
        """获取默认页面对象名。

        返回:
        - str: 默认页面对象名；不存在页面插件时返回空字符串。
        """
        pages = self.page_plugins()
        for plugin in pages:
            if plugin.default:
                return plugin.page_object
        if not pages:
            return ""
        return pages[0].page_object

    def apply_menu_plugins(self, base_items: list[object], target: str) -> list[object]:
        """将菜单插件项追加到基础菜单列表。

        参数:
        - base_items: 基础菜单项列表。
        - target: 菜单目标标识。

        返回:
        - list: 合并后的菜单项列表。
        """
        result = list(base_items)
        result.extend(plugin.item for plugin in self.menu_plugins(target))
        return result

    def execute_command(self, command_id: str, *args: object, **kwargs: object) -> object | None:
        """执行指定命令插件。

        参数:
        - command_id: 命令标识。
        - *args: 透传给命令处理器的位置参数。
        - **kwargs: 透传给命令处理器的关键字参数。

        返回:
        - Any | None: 命令执行结果；未命中或执行失败时返回 None。
        """
        for plugin in self.command_plugins():
            if plugin.command_id == command_id:
                try:
                    return plugin.handler(*args, **kwargs)
                except PLUGIN_RUNTIME_EXCEPTIONS as exc:
                    self._load_errors.append(f"{plugin.plugin_id}: {exc}")
                    return None
        return None


_PLUGIN_REGISTRY = PluginRegistry()


def get_plugin_registry(*, reset: bool = False) -> PluginRegistry:
    """获取全局插件注册中心实例。

    参数:
    - reset: 为 True 时重建并返回新实例。

    返回:
    - PluginRegistry: 全局注册中心对象。
    """
    state = globals()
    if reset:
        state["_PLUGIN_REGISTRY"] = PluginRegistry()
    return state["_PLUGIN_REGISTRY"]
