"""插件发现、导入、生命周期与失败隔离。

一个目录 = 一个插件；入口必须导出 ``PLUGIN`` 实例。导入使用唯一模块名，
卸载时按模块名前缀清理 ``sys.modules``，避免重载后仍命中旧模块。

3.0 起插件**不再**把自己的目录插进 ``sys.path``：那等于把插件根放到标准库
之前，插件里一个 ``json.py`` 就能劫持全进程的 ``import json``。插件内部一律
用相对导入（``from .pages.home import HomePage``）；入口模块通过
``submodule_search_locations=[root]`` 被当作包加载，相对导入天然可用。
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from sllkgui.appcore import Language, Logger, record_event

from .api import Plugin
from .context import GalleryContextImpl, _flatten
from .defaults import MANIFEST_NAME
from .dependencies import ensure_python_dependencies
from .errors import PLUGIN_LOAD_FAILED, PLUGIN_SURFACE_IMPL_MISSING, GalleryError
from .events import PluginEventBus
from .manifest import PluginManifest, ensure_within, load_manifest
from .registry import GalleryRegistry, PluginRecord, sanitize_route
from .services import PluginServiceRegistry
from .store import GalleryStore
from .tray import TrayService

#: plugin_id -> locale -> flatten(key -> text)
_LANG: dict[str, dict[str, dict[str, str]]] = {}
_PROVIDER_REGISTERED = False

#: 原生扩展后缀：这些文件在进程内无法安全卸载/替换
_NATIVE_SUFFIXES = frozenset({".pyd", ".so", ".dll", ".dylib"})


def has_native_extensions(root: Path) -> bool:
    """插件目录是否包含原生扩展。

    纯 Python 插件可以在同一进程内重新导入；``.pyd`` / ``.so`` / ``.dll``
    一旦被加载就无法可靠卸载（Windows 上文件还会被锁定），因此更新这类
    插件必须重启进程，而不是热替换。
    """
    try:
        return any(
            path.is_file() and path.suffix.lower() in _NATIVE_SUFFIXES
            for path in Path(root).rglob("*")
        )
    except OSError as exc:
        Logger.debug(f"原生扩展扫描失败 {root}: {exc}")
        return False


def prepare_plugin_reload(root: Path) -> None:
    """热重载前清掉插件目录内的字节码缓存并刷新导入缓存。

    Python 的 ``.pyc`` 只按源文件 mtime + size 判断是否过期；如果插件更新
    恰好保留了这两个值（例如归档工具恢复时间戳），旧字节码会被继续使用。
    删除插件目录内的 ``__pycache__`` 是最小且安全的修复。
    """
    root = Path(root)
    for cache in list(root.rglob("__pycache__")):
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
    importlib.invalidate_caches()



def _relative_import_hint(exc: ModuleNotFoundError, root: Path) -> str:
    """把「插件内绝对导入失败」翻译成可操作的提示。

    插件不再把自己的目录插进 ``sys.path``，因此 ``import mylib`` 这类写法
    会失败。这里指出仓库里是否存在同名目录，并给出相对导入的写法。
    """
    name = exc.name or ""
    top = name.split(".")[0]
    if not top:
        return ""
    if (root / top).exists():
        return f"插件内请用相对导入：把 `import {top}` 改为 `from . import {top}`（或 `from .{name} import ...`）"
    return "插件内请用相对导入（`from . import ...`），基座不会把插件目录加入 sys.path"


def _language_provider(language: str) -> dict[str, Any]:
    return {plugin_id: dict(table.get(language) or table.get("en_us") or {}) for plugin_id, table in _LANG.items()}


def _ensure_provider() -> None:
    global _PROVIDER_REGISTERED
    if _PROVIDER_REGISTERED:
        return
    Language.register_app_provider(_language_provider)
    _PROVIDER_REGISTERED = True


def load_language_data(root: Path, plugin_id: str) -> dict[str, dict[str, str]]:
    """读取 ``resource/lang/<locale>.yml`` 并扁平化成 ``key -> text``。"""
    folder = Path(root) / "resource" / "lang"
    data: dict[str, dict[str, str]] = {}
    if not folder.is_dir():
        return data
    for locale in ("zh_cn", "zh_tw", "en_us", "ja_jp"):
        path = folder / f"{locale}.yml"
        if not path.is_file():
            path = folder / f"{locale}.yaml"
        if not path.is_file():
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            Logger.warning(f"插件语言文件解析失败 {plugin_id}/{path.name}: {exc}")
            continue
        if isinstance(raw, dict):
            data[locale] = _flatten(raw)
    if data:
        _LANG[plugin_id] = data
    return data


def refresh_language_namespace(*, force: bool = False) -> None:
    """把所有插件语言表注入 ``Language.app.<plugin_id>``（在窗口创建前调用）。

    ``force=True`` 用于选择性重载：插件语言文件或 Surface 标题变化时，
    基座语言包本身没有变化，``Language.apply`` 会按签名早退，必须强制
    重新收集 App 语言提供者。
    """
    _ensure_provider()
    if not _LANG:
        return
    try:
        current = Language.current()
        Language.apply(current, force=force)
    except Exception as exc:  # noqa: BLE001 - 语言注入失败不应阻断启动
        Logger.debug(f"插件语言命名空间刷新失败: {exc}")


def discover_plugin_dirs(roots: Iterable[Path]) -> list[Path]:
    """展开插件根目录：根本身是插件则返回它，否则返回含清单的子目录。"""
    result: list[Path] = []
    for root in roots:
        path = Path(root)
        if not path.exists():
            continue
        if (path / MANIFEST_NAME).is_file():
            result.append(path)
            continue
        try:
            children = sorted(path.iterdir())
        except OSError as exc:
            Logger.debug(f"插件目录枚举失败 {path}: {exc}")
            continue
        for child in children:
            if child.is_dir() and (child / MANIFEST_NAME).is_file():
                result.append(child)
    return result


def _canonical_module_name(root: Path, entry_path: Path) -> str | None:
    """内置预览插件（``sllkgui/showcase/*``）的规范模块名，否则 ``None``。

    内置预览插件若以随机别名导入，``page.py`` 会同时存在别名与规范名两份
    ``sys.modules`` 条目，覆盖率归到别名下、全仓报告显示 0%（RV-11）。
    只对随包分发的 showcase 用规范名，避免影响用户安装在任意路径的插件。
    """
    parts = root.parts
    if "sllkgui" not in parts:
        return None
    base = parts[parts.index("sllkgui") :]
    if len(base) < 2 or base[0] != "sllkgui" or base[1] != "showcase":
        return None
    package = ".".join(base)
    return f"{package}.{entry_path.stem}"


def _import_entry(root: Path, entry: str, plugin_id: str) -> tuple[ModuleType, list[str]]:
    entry_path = ensure_within(root, entry)
    canonical = _canonical_module_name(root, entry_path)
    module_name = canonical or f"sllkgui_plugin_{sanitize_route(plugin_id)}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        entry_path,
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise GalleryError(PLUGIN_LOAD_FAILED, f"无法创建模块规格: {entry}", str(entry_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    before = set(sys.modules)
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    loaded = [name for name in sys.modules if name.startswith(f"{module_name}.")]
    if module_name not in loaded:
        loaded.insert(0, module_name)
    # 记录导入前不存在的模块，卸载时只清理本轮新增项
    created = [name for name in loaded if name not in before]
    if module_name not in created:
        created.insert(0, module_name)
    return module, created


def _modules_under(root: Path) -> list[str]:
    """返回所有从插件根目录加载的模块名（含惰性导入的子模块）。

    相对导入的子模块带唯一入口前缀（如 ``sllkgui_plugin_x.pages.home``），
    按前缀即可清理；但插件若用 ``importlib.import_module("surfaces.x")``
    这类不带前缀的写法加载自己的模块，只按前缀清理会让更新后的插件
    继续命中旧代码。这里按模块文件的归属目录兜底判断。
    """
    prefix = os.path.normcase(str(Path(root).resolve())) + os.sep
    names: list[str] = []
    for name, module in list(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        try:
            path = os.path.normcase(os.path.abspath(origin))
        except (OSError, TypeError):
            continue
        if path.startswith(prefix):
            names.append(name)
    return names


def _verify_surface_impls(manifest: PluginManifest, root: Path) -> None:
    """校验清单声明的 Surface 实现文件确实存在。

    在 ``on_load`` 之前失败：否则托盘 / 快捷键 / 设置页已经注册，
    回滚代价高，而且用户只能在点击菜单时才发现页面是空的。
    """
    missing: list[str] = []
    for spec in manifest.surfaces:
        if not spec.impl:
            continue
        if not ensure_within(root, spec.impl).is_file():
            missing.append(f"{spec.surface_id} -> {spec.impl}")
    if missing:
        raise GalleryError(
            PLUGIN_SURFACE_IMPL_MISSING,
            "Surface 实现文件缺失: " + ", ".join(missing),
            manifest.plugin_id,
        )


def preflight_plugin(path: Path, *, check_dependencies: bool = True) -> PluginManifest:
    """不执行插件代码的加载前检查：清单 + Surface 实现 + Python 依赖存在性。

    选择性重载在卸载旧实例之前调用它；坏清单/缺失实现/缺失依赖直接返回
    错误，旧实例继续运行，避免“先卸再发现新版本根本装不起来”。
    """
    root = Path(path).resolve()
    manifest = load_manifest(root)
    _verify_surface_impls(manifest, root)
    if check_dependencies and manifest.python_dependencies:
        from .dependencies import missing_packages
        from .errors import PYTHON_DEPENDENCY_MISSING

        missing = missing_packages(manifest.python_dependencies)
        if missing:
            raise GalleryError(
                PYTHON_DEPENDENCY_MISSING,
                f"缺少 Python 依赖: {', '.join(missing)}",
                manifest.plugin_id,
            )
    return manifest


def load_plugin(
    path: Path,
    store: GalleryStore,
    registry: GalleryRegistry,
    *,
    is_core: bool = False,
    replace: bool = False,
    compliance: int = 1,
    install_missing_deps: bool = False,
    interactive: bool = False,
    index_url: str = "",
    open_surface: Callable[[str, str], bool] | None = None,
    parent_window: Callable[[], Any] | None = None,
    error_reporter: Callable[[str, str, str], None] | None = None,
    tray: TrayService | None = None,
    shortcuts: Any | None = None,
    events: PluginEventBus | None = None,
    services: PluginServiceRegistry | None = None,
) -> PluginRecord | None:
    """加载单个插件；失败只记录，不影响调用方。

    ``replace=True`` 用于热重载：允许同 id 记录存在（调用方通常已先移除
    旧记录），并清理插件目录内的字节码缓存，确保更新后的源码真正生效。
    """
    root = Path(path).resolve()
    if replace:
        prepare_plugin_reload(root)
    try:
        manifest = load_manifest(root)
    except GalleryError as exc:
        registry._errors.append({"plugin_id": root.name, "code": exc.code, "detail": str(exc)})
        Logger.warning(f"插件清单无效，已跳过: {root.name}: {exc}")
        return None

    if not replace and any(item.plugin_id == manifest.plugin_id for item in registry.plugins()):
        registry._errors.append({"plugin_id": manifest.plugin_id, "code": "PLUGIN_ALREADY_INSTALLED"})
        Logger.warning(f"插件重复，已跳过: {manifest.plugin_id}")
        return None

    # 声明式实现校验先于依赖安装：坏清单不值得触发一次 pip 安装
    try:
        _verify_surface_impls(manifest, root)
    except GalleryError as exc:
        registry._errors.append({"plugin_id": manifest.plugin_id, "code": exc.code, "detail": str(exc)})
        Logger.warning(f"Surface 实现缺失，已跳过: {manifest.plugin_id}: {exc.message}")
        return None

    # 第三方依赖必须先就绪：插件模块本身就会在顶层 import 它们
    try:
        ensure_python_dependencies(
            manifest.python_dependencies,
            plugin_id=manifest.plugin_id,
            interactive=interactive,
            install=install_missing_deps,
            index_url=index_url,
            parent=parent_window() if parent_window is not None else None,
        )
    except GalleryError as exc:
        registry._errors.append({"plugin_id": manifest.plugin_id, "code": exc.code, "detail": str(exc)})
        Logger.warning(f"插件依赖未就绪，已跳过: {manifest.plugin_id}: {exc.message}")
        record_event(
            "plugin.dependencies_blocked",
            category="plugin",
            payload={"plugin_id": manifest.plugin_id, "code": exc.code},
        )
        return None

    language = load_language_data(root, manifest.plugin_id)
    # 清单里的 Surface 标题也进语言表：菜单按钮用 language.app.<id>.surface.<sid>.title
    # 作为键，切换语言时由 CLeftMenu.apply_language 统一刷新。
    for spec in manifest.surfaces:
        for locale in ("zh_cn", "zh_tw", "en_us", "ja_jp"):
            table = language.setdefault(locale, {})
            table[f"surface.{spec.surface_id}.title"] = (
                spec.title.get(locale) or spec.title.get("en_us") or spec.surface_id
            )
    context = GalleryContextImpl(
        manifest,
        store,
        language_data=language,
        open_surface=open_surface,
        parent_window=parent_window,
        error_reporter=error_reporter,
        tray=tray,
        shortcuts=shortcuts,
        events=events,
        services=services,
    )
    record = PluginRecord(
        manifest=manifest,
        plugin=None,  # type: ignore[arg-type]
        path=root,
        context=context,
        compliance=compliance,
        is_core=is_core,
    )
    context._record = record
    module_names: list[str] = []
    try:
        module, module_names = _import_entry(root, manifest.entry, manifest.plugin_id)
        plugin = getattr(module, "PLUGIN", None)
        if not isinstance(plugin, Plugin):
            raise GalleryError(
                PLUGIN_LOAD_FAILED,
                "入口必须导出 PLUGIN 实例",
                f"{manifest.entry}: {type(plugin).__name__}",
            )
        record.plugin = plugin
        plugin.on_load(context)
        registry.add(record)
        _ensure_provider()
        context.event("plugin.loaded", {"name": manifest.name})
        Logger.info(f"插件已加载: {manifest.plugin_id} {manifest.version}（{len(record.surfaces)} 个 Surface）")
        record._module_names = module_names  # type: ignore[attr-defined]
        return record
    except ModuleNotFoundError as exc:
        # 插件内绝对导入：给出相对导入的明确指引，而不是裸露的 ModuleNotFoundError
        hint = _relative_import_hint(exc, root)
        detail = f"{exc}: {hint}" if hint else str(exc)
        for name in {*module_names, *_modules_under(root)}:
            sys.modules.pop(name, None)
        context.clear_events()
        context.clear_services()
        context.clear_tray()
        context.clear_shortcuts()
        context.clear_settings()
        context.clear_logger()
        registry._errors.append({"plugin_id": manifest.plugin_id, "code": PLUGIN_LOAD_FAILED, "detail": detail})
        Logger.error(f"插件加载失败: {manifest.plugin_id}: {detail}")
        return None
    except Exception as exc:  # noqa: BLE001 - 单个插件失败必须隔离
        for name in {*module_names, *_modules_under(root)}:
            sys.modules.pop(name, None)
        context.clear_events()
        context.clear_services()
        context.clear_tray()
        context.clear_shortcuts()
        context.clear_settings()
        context.clear_logger()
        registry._errors.append({"plugin_id": manifest.plugin_id, "code": PLUGIN_LOAD_FAILED, "detail": str(exc)})
        Logger.exception(f"插件加载失败: {manifest.plugin_id}: {exc}")
        return None


def unload_plugin(record: PluginRecord) -> None:
    try:
        record.plugin.on_unload()
    except Exception as exc:  # noqa: BLE001 - 卸载失败也要继续清理
        Logger.warning(f"插件卸载钩子失败: {record.plugin_id}: {exc}")
    if record.context is not None:
        record.context.clear_events()
        record.context.clear_services()
        record.context.clear_tray()
        # 快捷键先于模块清理：回调对象随条目一起释放，避免留下悬空引用
        record.context.clear_shortcuts()
        # 设置页与磁盘配置分离：只撤注册，用户改过的值保留
        record.context.clear_settings()
        # 日志 handler 绑定旧版本前缀；清掉后下次加载会重新挂新的
        record.context.clear_logger()
    for name in {*(getattr(record, "_module_names", []) or []), *_modules_under(record.path)}:
        sys.modules.pop(name, None)
    _LANG.pop(record.plugin_id, None)
    Logger.debug(f"插件已卸载: {record.plugin_id}")


def unload_all(records: Iterable[PluginRecord]) -> None:
    for record in reversed(list(records)):
        unload_plugin(record)


__all__ = [
    "discover_plugin_dirs",
    "has_native_extensions",
    "load_language_data",
    "load_plugin",
    "preflight_plugin",
    "prepare_plugin_reload",
    "refresh_language_namespace",
    "unload_all",
    "unload_plugin",
]
