"""Gallery 运行时装配：模式、插件来源、加载与关闭。

``gallery`` 与 ``run`` 共用注册表与窗口外壳，唯一差别是插件来源：

- gallery：只读 ``<package>/showcase``，不读 registry/sources/plugins，不联网；
- run：已启用已安装插件 + ``--plugin-dir`` 开发插件。

插件管理已改为基座原生页面，不再作为 ``core_plugins`` 插件加载。
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import sllkgui
from sllkgui.appcore import Logger, record_event

from .defaults import GALLERY_DIRNAME, SHOWCASE_DIRNAME
from .errors import (
    PLUGIN_RELOAD_FAILED,
    PLUGIN_RELOAD_IN_PROGRESS,
    PLUGIN_RELOAD_TARGET_MISSING,
    PLUGIN_RESTART_REQUIRED,
    GalleryError,
)
from .events import PluginEventBus
from .loader import (
    discover_plugin_dirs,
    has_native_extensions,
    load_plugin,
    preflight_plugin,
    refresh_language_namespace,
    unload_all,
    unload_plugin,
)
from .manager import PluginManager
from .manifest import PluginManifest, load_manifest
from .registry import GalleryRegistry, PluginRecord, set_current_registry
from .services import PluginServiceRegistry
from .source import SourceManager
from .state import RegistryState, SourcesState, load_registry, load_sources
from .store import GalleryStore
from .tray import TrayService

Mode = Literal["gallery", "run"]

_CURRENT_RUNTIME: GalleryRuntime | None = None
#: 保留的最近重载记录条数（诊断页/插件管理页读取）
RELOAD_HISTORY_LIMIT = 20


@dataclass
class ReloadResult:
    """一次选择性重载的结果；窗口层会回填页面销毁/构建数量。"""

    ok: bool
    targets: list[str] = field(default_factory=list)
    affected: list[str] = field(default_factory=list)
    pages_destroyed: int = 0
    pages_built: int = 0
    rollback: str = "none"
    full_reload: bool = False
    code: str = ""
    message: str = ""
    duration_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "targets": list(self.targets),
            "affected": list(self.affected),
            "pages_destroyed": self.pages_destroyed,
            "pages_built": self.pages_built,
            "rollback": self.rollback,
            "full_reload": self.full_reload,
            "code": self.code,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
        }



def set_current_runtime(runtime: GalleryRuntime | None) -> None:
    global _CURRENT_RUNTIME
    _CURRENT_RUNTIME = runtime


def current_runtime() -> GalleryRuntime | None:
    return _CURRENT_RUNTIME


class GalleryRuntime:
    def __init__(
        self,
        mode: Mode,
        *,
        data_dir: Path | None = None,
        gallery_dir: Path | None = None,
        plugin_dirs: list[Path] | None = None,
        safe_mode: bool = False,
        allow_local: bool = False,
        install_missing_deps: bool = True,
        interactive: bool = True,
        index_url: str = "",
        check_tools: bool = False,
        watch: bool = False,
    ) -> None:
        self.mode = mode
        self.data_dir = Path(data_dir).resolve() if data_dir else self._default_data_dir()
        self.gallery_dir = Path(gallery_dir).resolve() if gallery_dir else self.data_dir / GALLERY_DIRNAME
        self.plugin_dirs = [Path(item).resolve() for item in (plugin_dirs or [])]
        self.safe_mode = bool(safe_mode)
        self.allow_local = bool(allow_local)
        self.install_missing_deps = bool(install_missing_deps)
        self.interactive = bool(interactive)
        self.check_tools = bool(check_tools)
        self.watch = bool(watch) and not self.safe_mode
        from sllkgui.config import current_config

        self.index_url = (index_url or current_config().resolved_pip_index_url()).strip()
        self.store = GalleryStore(self.gallery_dir)
        self.registry = GalleryRegistry()
        self.tray = TrayService()
        self.events = PluginEventBus()
        self.services = PluginServiceRegistry()
        self.registry_state: RegistryState = RegistryState(base_version=sllkgui.__version__)
        self.sources_state: SourcesState = SourcesState()
        self.sources: SourceManager | None = None
        self.manager: PluginManager | None = None
        self.records: list[PluginRecord] = []
        self.last_error: dict[str, str] | None = None
        self.tools: Any = None
        self._shortcuts: Any = None
        self._navigate: Callable[[str], bool] | None = None
        self._parent_window: Callable[[], Any] | None = None
        self._reloading = False
        self.reload_history: list[ReloadResult] = []

    @staticmethod
    def _default_data_dir() -> Path:
        from sllkgui.appcore.sysx.config.paths import data_root

        return data_root()

    @property
    def shortcuts(self) -> Any:
        """基座快捷键表（惰性创建：非 GUI 路径不加载 Qt）。"""
        if self._shortcuts is None:
            from sllkgui.guicore.shortcuts import shortcut_registry

            self._shortcuts = shortcut_registry()
        return self._shortcuts

    # ------------------------------------------------------------------
    # 装配
    # ------------------------------------------------------------------
    def bootstrap(self) -> GalleryRegistry:
        set_current_registry(self.registry)
        set_current_runtime(self)
        if self.mode == "run" and self.check_tools:
            # 启动即检测 uv/git：缺失时让用户选自动或手动安装（不影响启动）
            from .dependencies import ensure_tools

            self.tools = ensure_tools(
                interactive=self.interactive,
                parent=self._parent_window_provider(),
            )
        if self.mode == "run":
            self.store.ensure_layout()
            self.registry_state = load_registry(self.store.registry_file, base_version=sllkgui.__version__)
            self.sources_state = load_sources(self.store.sources_file)
            self.sources = SourceManager(self.store, self.sources_state, allow_local=self.allow_local)
            self.sources.ensure_official()
            self.manager = PluginManager(
                self.store,
                self.registry_state,
                self.sources,
                base_version=sllkgui.__version__,
            )
            roots = self._run_roots()
        else:
            roots = [(sllkgui.package_root() / SHOWCASE_DIRNAME, False)]

        for root, is_core in roots:
            for plugin_dir in discover_plugin_dirs([root]):
                record = self._load_root(plugin_dir, is_core=is_core)
                if record is not None:
                    self.records.append(record)
        refresh_language_namespace(force=True)
        # 基座托盘常驻：先于插件动作创建，插件只往菜单里加条目
        self.tray.ensure_visible()
        # 快捷键表由基座常驻装配，插件是否注册都不影响内置快捷键
        self.shortcuts.install()
        Logger.info(
            f"Gallery 启动: mode={self.mode} 插件 {len(self.records)} 个 / Surface {self.registry.surface_count()} 个"
        )
        record_event(
            "gallery.bootstrapped",
            category="gallery",
            payload={
                "mode": self.mode,
                "plugins": len(self.records),
                "surfaces": self.registry.surface_count(),
            },
        )
        return self.registry

    def _load_root(self, root: Path, *, is_core: bool = False, replace: bool = False) -> PluginRecord | None:
        """按统一参数加载一个插件目录；启动与选择性重载共用。"""
        return load_plugin(
            root,
            self.store,
            self.registry,
            is_core=is_core,
            replace=replace,
            install_missing_deps=self.install_missing_deps,
            interactive=self.interactive,
            index_url=self.index_url,
            open_surface=self._open_surface,
            parent_window=self._parent_window_provider,
            error_reporter=self._report_error,
            tray=self.tray,
            shortcuts=self.shortcuts,
            events=self.events,
            services=self.services,
        )

    def _run_roots(self) -> list[tuple[Path, bool]]:
        roots: list[tuple[Path, bool]] = []
        if not self.safe_mode:
            # 开发目录优先级最高：先加载，重复 id 时不会被已安装版本覆盖
            for path in self.plugin_dirs:
                roots.append((path, False))
            for record in self.registry_state.enabled_plugins():
                path = self.store.plugin_path(record.plugin_id)
                if path.is_dir():
                    roots.append((path, False))
                else:
                    Logger.warning(f"已安装插件目录缺失，已跳过: {record.plugin_id}")
        return roots

    def _parent_window_provider(self) -> Any:
        return self._parent_window() if self._parent_window else None

    def _open_surface(self, plugin_id: str, surface_id: str) -> bool:
        route = f"{plugin_id}/{surface_id}"
        if self.registry.get(route) is None:
            return False
        if self._navigate is None:
            return False
        return bool(self._navigate(route))

    def _report_error(self, code: str, message: str, detail: str) -> None:
        self.last_error = {"code": code, "message": message, "detail": detail}

    def set_navigation(self, callback: Callable[[str], bool], parent_window: Callable[[], Any]) -> None:
        self._navigate = callback
        self._parent_window = parent_window

    def attach_window(self, window: Any) -> None:
        """把宿主窗口接入托盘：显示主窗口 / 设置 / 退出。

        「设置…」是基座级菜单项，宿主没有 ``open_settings_window`` 时自动省略，
        插件无法注入到这一段（见 ``docs/TRAY.md`` §2）。
        """
        settings = getattr(getattr(window, "controller", None), "open_settings_window", None)
        self.tray.attach_window(
            window.show_and_raise,
            window.quit_application,
            settings if callable(settings) else None,
        )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def default_route(self) -> str:
        return self.registry.default_route()

    def has_plugins(self) -> bool:
        return bool(self.records)

    def errors(self) -> list[dict[str, str]]:
        return self.registry.errors

    # ------------------------------------------------------------------
    # 选择性重载
    # ------------------------------------------------------------------
    def _record_for(self, plugin_id: str) -> PluginRecord | None:
        return next((item for item in self.records if item.plugin_id == plugin_id), None)

    def is_reloading(self) -> bool:
        """当前是否有选择性重载正在进行。"""
        return self._reloading

    def _plugin_root(self, plugin_id: str) -> Path | None:
        record = self._record_for(plugin_id)
        if record is not None:
            return Path(record.path)
        installed = self.registry_state.plugins.get(plugin_id)
        if installed is not None:
            path = self.store.plugin_path(plugin_id)
            if path.is_dir():
                return path
        for root in self.plugin_dirs:
            for candidate in discover_plugin_dirs([root]):
                try:
                    if load_manifest(candidate).plugin_id == plugin_id:
                        return candidate
                except Exception:  # noqa: BLE001 - 坏目录不参与匹配
                    continue
        return None

    def _manifest_for(self, plugin_id: str) -> PluginManifest | None:
        record = self._record_for(plugin_id)
        if record is not None:
            return record.manifest
        root = self._plugin_root(plugin_id)
        if root is None:
            return None
        try:
            return load_manifest(root)
        except Exception:  # noqa: BLE001 - 由后续 preflight 报具体错误
            return None

    def affected_plugins(self, plugin_ids: Iterable[str]) -> set[str]:
        """返回目标插件及其全部反向依赖者（基于已加载插件）。

        只把“正在运行的依赖者”纳入闭包；已停用的插件不会因为提供者更新
        而被重新加载。卸载顺序由 :meth:`_load_order` 反转得到。
        """
        targets = {str(item) for item in plugin_ids if str(item)}
        reverse: dict[str, set[str]] = {}
        for record in self.records:
            for dependency in record.manifest.dependencies:
                reverse.setdefault(dependency.plugin_id, set()).add(record.plugin_id)
        result = set(targets)
        stack = list(targets)
        while stack:
            current = stack.pop()
            for dependent in reverse.get(current, ()):
                if dependent not in result:
                    result.add(dependent)
                    stack.append(dependent)
        return result

    def _load_order(self, plugin_ids: Iterable[str]) -> list[str]:
        """提供者优先的确定性顺序；循环依赖保持稳定回退。"""
        targets = sorted({str(item) for item in plugin_ids if str(item)})
        manifests = {plugin_id: self._manifest_for(plugin_id) for plugin_id in targets}
        result: list[str] = []
        seen: set[str] = set()
        visiting: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in seen or plugin_id in visiting:
                return
            visiting.add(plugin_id)
            manifest = manifests.get(plugin_id)
            if manifest is not None:
                for dependency in manifest.dependencies:
                    if dependency.plugin_id in manifests:
                        visit(dependency.plugin_id)
            visiting.discard(plugin_id)
            seen.add(plugin_id)
            result.append(plugin_id)

        for plugin_id in targets:
            visit(plugin_id)
        return result

    def _record_reload(self, result: ReloadResult) -> ReloadResult:
        self.reload_history.append(result)
        if len(self.reload_history) > RELOAD_HISTORY_LIMIT:
            del self.reload_history[: len(self.reload_history) - RELOAD_HISTORY_LIMIT]
        if not result.ok:
            self.last_error = {
                "code": result.code or PLUGIN_RELOAD_FAILED,
                "message": result.message,
                "detail": result.message,
            }
        else:
            self.last_error = None
        try:
            record_event("plugin.reload", category="plugin", payload=result.as_dict())
        except Exception as exc:  # noqa: BLE001 - 遥测失败不影响重载
            Logger.debug(f"重载遥测写入失败: {exc}")
        return result

    def recent_reloads(self, limit: int = 5) -> list[ReloadResult]:
        """最近的插件重载记录（新的在后）。"""
        return list(self.reload_history[-max(0, int(limit)) :])

    def reload_plugin(self, plugin_id: str, *, reason: str = "manual") -> ReloadResult:
        return self.reload_plugins([plugin_id], reason=reason)

    def preflight_reload(self, plugin_ids: Iterable[str], *, reason: str = "manual") -> ReloadResult:
        """只做重载前检查，不卸载/加载任何插件。

        窗口层在销毁页面之前调用它：坏清单、缺失实现、缺失依赖或原生扩展
        会直接返回错误，旧页面与旧实例保持不动。
        """
        started = time.perf_counter()
        targets = list(dict.fromkeys(str(item) for item in plugin_ids if str(item)))
        affected = self.affected_plugins(targets)
        result = ReloadResult(
            ok=True,
            targets=targets,
            affected=sorted(affected),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        if not targets:
            result.ok = False
            result.code = PLUGIN_RELOAD_TARGET_MISSING
            result.message = "未指定要重载的插件"
            return result
        if self._reloading:
            result.ok = False
            result.code = PLUGIN_RELOAD_IN_PROGRESS
            result.message = "已有插件重载正在进行"
            return result
        for plugin_id in sorted(affected):
            root = self._plugin_root(plugin_id)
            if root is None:
                result.ok = False
                result.code = PLUGIN_RELOAD_TARGET_MISSING
                result.message = f"未找到插件目录: {plugin_id}"
                return result
            try:
                preflight_plugin(root, check_dependencies=reason in {"update", "rollback", "dev-watch"})
            except GalleryError as exc:
                result.ok = False
                result.code = exc.code
                result.message = exc.message
                return result
            if reason in {"update", "rollback", "dev-watch"} and has_native_extensions(root):
                result.ok = False
                result.code = PLUGIN_RESTART_REQUIRED
                result.message = f"{plugin_id} 含原生扩展，更新/回滚需要重启应用"
                return result
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    def reload_plugins(
        self,
        plugin_ids: Iterable[str],
        *,
        reason: str = "manual",
        force_full: bool = False,
    ) -> ReloadResult:
        """选择性重载目标插件及其反向依赖者。

        - ``force_full=True`` 回退到原有的全量重载；
        - 任何预检失败都不会卸载旧实例；
        - 加载失败时已经加载的插件保留，由窗口层决定是否回滚文件；
        - 原生扩展参与更新/回滚/开发监听时直接返回 ``RESTART_REQUIRED``。
        """
        started = time.perf_counter()
        targets = list(dict.fromkeys(str(item) for item in plugin_ids if str(item)))
        if self._reloading:
            return self._record_reload(
                ReloadResult(
                    ok=False,
                    targets=targets,
                    code=PLUGIN_RELOAD_IN_PROGRESS,
                    message="已有插件重载正在进行",
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        if force_full:
            self.reload()
            result = ReloadResult(
                ok=True,
                targets=targets,
                affected=[record.plugin_id for record in self.records],
                full_reload=True,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return self._record_reload(result)
        if not targets:
            return self._record_reload(
                ReloadResult(
                    ok=False,
                    code=PLUGIN_RELOAD_TARGET_MISSING,
                    message="未指定要重载的插件",
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )

        self._reloading = True
        try:
            affected = self.affected_plugins(targets)
            roots: dict[str, Path] = {}
            for plugin_id in sorted(affected):
                root = self._plugin_root(plugin_id)
                if root is None:
                    return self._record_reload(
                        ReloadResult(
                            ok=False,
                            targets=targets,
                            affected=sorted(affected),
                            code=PLUGIN_RELOAD_TARGET_MISSING,
                            message=f"未找到插件目录: {plugin_id}",
                            duration_ms=(time.perf_counter() - started) * 1000,
                        )
                    )
                roots[plugin_id] = root

            # 预检先于卸载：坏清单/缺失实现不应让旧实例下线
            for plugin_id in sorted(affected):
                try:
                    preflight_plugin(roots[plugin_id], check_dependencies=reason in {"update", "rollback", "dev-watch"})
                except GalleryError as exc:
                    self.registry._errors.append(
                        {"plugin_id": plugin_id, "code": exc.code, "detail": str(exc)}
                    )
                    return self._record_reload(
                        ReloadResult(
                            ok=False,
                            targets=targets,
                            affected=sorted(affected),
                            code=exc.code,
                            message=exc.message,
                            duration_ms=(time.perf_counter() - started) * 1000,
                        )
                    )
                if reason in {"update", "rollback", "dev-watch"} and has_native_extensions(roots[plugin_id]):
                    return self._record_reload(
                        ReloadResult(
                            ok=False,
                            targets=targets,
                            affected=sorted(affected),
                            code=PLUGIN_RESTART_REQUIRED,
                            message=f"{plugin_id} 含原生扩展，更新/回滚需要重启应用",
                            duration_ms=(time.perf_counter() - started) * 1000,
                        )
                    )

            order = self._load_order(affected)
            for plugin_id in reversed(order):
                record = self._record_for(plugin_id)
                if record is None:
                    continue
                unload_plugin(record)
                self.registry.remove(plugin_id)
                self.records = [item for item in self.records if item.plugin_id != plugin_id]

            for plugin_id in order:
                self.registry.clear_errors(plugin_id)
                record = self._load_root(roots[plugin_id], replace=True)
                if record is None:
                    error = next(
                        (
                            item
                            for item in reversed(self.registry.errors)
                            if item.get("plugin_id") == plugin_id
                        ),
                        {},
                    )
                    return self._record_reload(
                        ReloadResult(
                            ok=False,
                            targets=targets,
                            affected=sorted(affected),
                            code=str(error.get("code") or PLUGIN_RELOAD_FAILED),
                            message=str(error.get("detail") or f"插件加载失败: {plugin_id}"),
                            duration_ms=(time.perf_counter() - started) * 1000,
                        )
                    )
                self.records.append(record)

            refresh_language_namespace(force=True)
            return self._record_reload(
                ReloadResult(
                    ok=True,
                    targets=targets,
                    affected=sorted(affected),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        finally:
            self._reloading = False

    def unload_plugins(self, plugin_ids: Iterable[str], *, reason: str = "manual") -> ReloadResult:
        """卸载目标插件及其反向依赖者，不重新加载（停用/卸载用）。"""
        started = time.perf_counter()
        targets = list(dict.fromkeys(str(item) for item in plugin_ids if str(item)))
        if not targets:
            return self._record_reload(
                ReloadResult(
                    ok=False,
                    code=PLUGIN_RELOAD_TARGET_MISSING,
                    message="未指定要卸载的插件",
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        if self._reloading:
            return self._record_reload(
                ReloadResult(
                    ok=False,
                    targets=targets,
                    code=PLUGIN_RELOAD_IN_PROGRESS,
                    message="已有插件重载正在进行",
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        self._reloading = True
        try:
            affected = self.affected_plugins(targets)
            order = self._load_order(affected)
            for plugin_id in reversed(order):
                record = self._record_for(plugin_id)
                if record is None:
                    continue
                unload_plugin(record)
                self.registry.remove(plugin_id)
                self.records = [item for item in self.records if item.plugin_id != plugin_id]
            refresh_language_namespace(force=True)
            return self._record_reload(
                ReloadResult(
                    ok=True,
                    targets=targets,
                    affected=sorted(affected),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        finally:
            self._reloading = False

    # ------------------------------------------------------------------
    # 重载与关闭
    # ------------------------------------------------------------------
    def reload(self) -> GalleryRegistry:
        Logger.info("Gallery 重新加载插件")
        # 重载只重建插件，托盘作为基座常驻能力继续持有，避免图标闪烁
        self.shutdown(clear_registry=False, dispose_tray=False)
        self.registry.clear()
        self.records.clear()
        self.registry_state = load_registry(self.store.registry_file, base_version=sllkgui.__version__)
        if self.sources is not None:
            self.sources.state = load_sources(self.store.sources_file)
        if self.manager is not None:
            self.manager.state = self.registry_state
        return self.bootstrap()

    def shutdown(self, *, clear_registry: bool = True, dispose_tray: bool = True) -> None:
        unload_all(self.records)
        self.records.clear()
        if dispose_tray:
            self.tray.dispose()
        # 重载时保留快捷键表（与托盘同理），只在真正退出时摘过滤器并清空
        if clear_registry and self._shortcuts is not None:
            self._shortcuts.shutdown()
            self._shortcuts = None
        if clear_registry:
            self.registry.clear()
            self.events.clear()
            self.services.clear()
            set_current_registry(None)
            set_current_runtime(None)
        Logger.info("Gallery 已关闭")


def ensure_gallery_error(exc: Exception) -> GalleryError:
    if isinstance(exc, GalleryError):
        return exc
    return GalleryError("GALLERY_ERROR", str(exc))


__all__ = ["GalleryRuntime", "Mode", "ReloadResult", "ensure_gallery_error"]
