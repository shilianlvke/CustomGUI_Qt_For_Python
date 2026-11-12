"""插件发现、导入、生命周期与失败隔离。

一个目录 = 一个插件；入口必须导出 ``PLUGIN`` 实例。导入使用唯一模块名，
卸载时按模块名前缀清理 ``sys.modules``，避免重载后仍命中旧模块。
"""

from __future__ import annotations

import importlib.util
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
from .errors import PLUGIN_LOAD_FAILED, GalleryError
from .manifest import ensure_within, load_manifest
from .registry import GalleryRegistry, PluginRecord, sanitize_route
from .store import GalleryStore
from .tray import TrayService

#: plugin_id -> locale -> flatten(key -> text)
_LANG: dict[str, dict[str, dict[str, str]]] = {}
_PROVIDER_REGISTERED = False
#: 插件根目录 -> 引用计数；卸载时只为最后一个使用者移除 sys.path
_SYS_PATH_REFS: dict[str, int] = {}


def _add_sys_path(root: Path) -> list[str]:
    text = str(root.resolve())
    _SYS_PATH_REFS[text] = _SYS_PATH_REFS.get(text, 0) + 1
    if text not in sys.path:
        # 插件仓库根作为顶层包搜索路径：允许 ``import pyrm`` 这类仓库内包
        sys.path.insert(0, text)
        return [text]
    return []


def _remove_sys_path(paths: list[str]) -> None:
    for text in paths:
        count = _SYS_PATH_REFS.get(text, 0) - 1
        if count > 0:
            _SYS_PATH_REFS[text] = count
            continue
        _SYS_PATH_REFS.pop(text, None)
        while text in sys.path:
            sys.path.remove(text)


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


def refresh_language_namespace() -> None:
    """把所有插件语言表注入 ``Language.app.<plugin_id>``（在窗口创建前调用）。"""
    _ensure_provider()
    if not _LANG:
        return
    try:
        current = Language.current()
        Language.apply(current)
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


def _import_entry(root: Path, entry: str, plugin_id: str) -> tuple[ModuleType, list[str]]:
    entry_path = ensure_within(root, entry)
    module_name = f"sllkgui_plugin_{sanitize_route(plugin_id)}_{uuid.uuid4().hex[:8]}"
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


def load_plugin(
    path: Path,
    store: GalleryStore,
    registry: GalleryRegistry,
    *,
    is_core: bool = False,
    compliance: int = 1,
    install_missing_deps: bool = False,
    interactive: bool = False,
    index_url: str = "",
    open_surface: Callable[[str, str], bool] | None = None,
    parent_window: Callable[[], Any] | None = None,
    error_reporter: Callable[[str, str, str], None] | None = None,
    tray: TrayService | None = None,
) -> PluginRecord | None:
    """加载单个插件；失败只记录，不影响调用方。"""
    root = Path(path).resolve()
    try:
        manifest = load_manifest(root)
    except GalleryError as exc:
        registry._errors.append({"plugin_id": root.name, "code": exc.code, "detail": str(exc)})
        Logger.warning(f"插件清单无效，已跳过: {root.name}: {exc}")
        return None

    if any(item.plugin_id == manifest.plugin_id for item in registry.plugins()):
        registry._errors.append(
            {"plugin_id": manifest.plugin_id, "code": "PLUGIN_ALREADY_INSTALLED"}
        )
        Logger.warning(f"插件重复，已跳过: {manifest.plugin_id}")
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
        registry._errors.append(
            {"plugin_id": manifest.plugin_id, "code": exc.code, "detail": str(exc)}
        )
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
    sys_path_added: list[str] = []
    try:
        sys_path_added = _add_sys_path(root)
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
        record._sys_path_added = sys_path_added  # type: ignore[attr-defined]
        return record
    except Exception as exc:  # noqa: BLE001 - 单个插件失败必须隔离
        for name in module_names or []:
            sys.modules.pop(name, None)
        _remove_sys_path(sys_path_added)
        context.clear_tray()
        registry._errors.append(
            {"plugin_id": manifest.plugin_id, "code": PLUGIN_LOAD_FAILED, "detail": str(exc)}
        )
        Logger.exception(f"插件加载失败: {manifest.plugin_id}: {exc}")
        return None


def unload_plugin(record: PluginRecord) -> None:
    try:
        record.plugin.on_unload()
    except Exception as exc:  # noqa: BLE001 - 卸载失败也要继续清理
        Logger.warning(f"插件卸载钩子失败: {record.plugin_id}: {exc}")
    if record.context is not None:
        record.context.clear_tray()
    for name in list(getattr(record, "_module_names", []) or []):
        sys.modules.pop(name, None)
    _remove_sys_path(list(getattr(record, "_sys_path_added", []) or []))
    _LANG.pop(record.plugin_id, None)
    Logger.debug(f"插件已卸载: {record.plugin_id}")


def unload_all(records: Iterable[PluginRecord]) -> None:
    for record in reversed(list(records)):
        unload_plugin(record)


__all__ = [
    "discover_plugin_dirs",
    "load_language_data",
    "load_plugin",
    "refresh_language_namespace",
    "unload_all",
    "unload_plugin",
]
