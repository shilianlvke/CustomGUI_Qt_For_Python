"""Gallery 运行时装配：模式、插件来源、加载与关闭。

``gallery`` 与 ``run`` 共用注册表与窗口外壳，唯一差别是插件来源：

- gallery：只读 ``<package>/showcase``，不读 registry/sources/plugins，不联网；
- run：``core_plugins`` + 已启用已安装插件 + ``--plugin-dir`` 开发插件。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import sllkgui
from sllkgui.appcore import Logger, record_event

from .defaults import CORE_PLUGINS_DIRNAME, GALLERY_DIRNAME, SHOWCASE_DIRNAME
from .errors import GalleryError
from .loader import discover_plugin_dirs, load_plugin, refresh_language_namespace, unload_all
from .manager import PluginManager
from .registry import GalleryRegistry, PluginRecord, set_current_registry
from .source import SourceManager
from .state import RegistryState, SourcesState, load_registry, load_sources
from .store import GalleryStore
from .tray import TrayService

Mode = Literal["gallery", "run"]

_CURRENT_RUNTIME: GalleryRuntime | None = None


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
    ) -> None:
        self.mode = mode
        self.data_dir = Path(data_dir).resolve() if data_dir else self._default_data_dir()
        self.gallery_dir = (
            Path(gallery_dir).resolve() if gallery_dir else self.data_dir / GALLERY_DIRNAME
        )
        self.plugin_dirs = [Path(item).resolve() for item in (plugin_dirs or [])]
        self.safe_mode = bool(safe_mode)
        self.allow_local = bool(allow_local)
        self.install_missing_deps = bool(install_missing_deps)
        self.interactive = bool(interactive)
        self.check_tools = bool(check_tools)
        from sllkgui.config import current_config

        self.index_url = (index_url or current_config().resolved_pip_index_url()).strip()
        self.store = GalleryStore(self.gallery_dir)
        self.registry = GalleryRegistry()
        self.tray = TrayService()
        self.registry_state: RegistryState = RegistryState(base_version=sllkgui.__version__)
        self.sources_state: SourcesState = SourcesState()
        self.sources: SourceManager | None = None
        self.manager: PluginManager | None = None
        self.records: list[PluginRecord] = []
        self.last_error: dict[str, str] | None = None
        self.tools: Any = None
        self._navigate: Callable[[str], bool] | None = None
        self._parent_window: Callable[[], Any] | None = None

    @staticmethod
    def _default_data_dir() -> Path:
        from sllkgui.appcore.sysx.config.paths import data_root

        return data_root()

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
            self.registry_state = load_registry(
                self.store.registry_file, base_version=sllkgui.__version__
            )
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
                record = load_plugin(
                    plugin_dir,
                    self.store,
                    self.registry,
                    is_core=is_core,
                    install_missing_deps=self.install_missing_deps,
                    interactive=self.interactive,
                    index_url=self.index_url,
                    open_surface=self._open_surface,
                    parent_window=self._parent_window_provider,
                    error_reporter=self._report_error,
                    tray=self.tray,
                )
                if record is not None:
                    self.records.append(record)
        refresh_language_namespace()
        Logger.info(
            f"Gallery 启动: mode={self.mode} 插件 {len(self.records)} 个 / "
            f"Surface {self.registry.surface_count()} 个"
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
        roots.append((sllkgui.package_root() / CORE_PLUGINS_DIRNAME, True))
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
        """把宿主窗口接入托盘：显示主窗口 / 退出。"""
        self.tray.attach_window(window.show_and_raise, window.quit_application)

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
    # 重载与关闭
    # ------------------------------------------------------------------
    def reload(self) -> GalleryRegistry:
        Logger.info("Gallery 重新加载插件")
        self.shutdown(clear_registry=False)
        self.registry.clear()
        self.records.clear()
        self.registry_state = load_registry(self.store.registry_file, base_version=sllkgui.__version__)
        if self.sources is not None:
            self.sources.state = load_sources(self.store.sources_file)
        if self.manager is not None:
            self.manager.state = self.registry_state
        return self.bootstrap()

    def shutdown(self, *, clear_registry: bool = True) -> None:
        unload_all(self.records)
        self.records.clear()
        self.tray.dispose()
        if clear_registry:
            self.registry.clear()
            set_current_registry(None)
            set_current_runtime(None)
        Logger.info("Gallery 已关闭")


def ensure_gallery_error(exc: Exception) -> GalleryError:
    if isinstance(exc, GalleryError):
        return exc
    return GalleryError("GALLERY_ERROR", str(exc))


__all__ = ["GalleryRuntime", "Mode", "ensure_gallery_error"]
