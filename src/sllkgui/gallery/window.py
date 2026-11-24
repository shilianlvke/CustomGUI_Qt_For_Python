"""Gallery 外壳窗口：组件预览与插件运行共用同一套窗口骨架。"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmapCache
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, Language, Logger, PathFactory, record_event
from sllkgui.gallery.loader import discover_plugin_dirs
from sllkgui.gallery.registry import SurfaceRecord
from sllkgui.gallery.runtime import GalleryRuntime, ReloadResult
from sllkgui.guicore import CPageTransition
from sllkgui.guis.windows.main_window.builtin_shortcuts import (
    install_builtin_shortcuts,
    uninstall_builtin_shortcuts,
)
from sllkgui.guis.windows.main_window.controller import MainWindowController
from sllkgui.guis.windows.main_window.functions import MainFunctions
from sllkgui.guis.windows.main_window.native_pages import NATIVE_PAGES, NativePage, native_page_for
from sllkgui.guis.windows.main_window.registry import (
    ensure_registered_page,
    get_default_page_object,
    get_menu_items,
)
from sllkgui.guis.windows.main_window.setup_main_window import SetupMainWindow
from sllkgui.guis.windows.main_window.ui_main import UiMainWindow

#: Win32 常量：窗口显示后重设原生图标（见 :func:`_reapply_taskbar_icon`）
_WM_SETICON = 0x0080
_ICON_SMALL = 0
_ICON_BIG = 1
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_LR_DEFAULTSIZE = 0x00000040
#: 按槽位缓存 HICON，避免窗口每次显示都重复加载图标句柄
_TASKBAR_ICONS: dict[int, int] = {}

#: 依赖类错误：启动时聚合成一条可操作提示，而不是逐个弹通知
_DEPENDENCY_CODES = frozenset(
    {"PYTHON_DEPENDENCY_MISSING", "PYTHON_DEPENDENCY_INSTALL_FAILED", "FROZEN_ENV_UNSUPPORTED"}
)


def _reapply_taskbar_icon(window: QMainWindow) -> None:
    """窗口显示后重设一次原生图标，刷新 Windows 任务栏按钮。

    Windows 11 的任务栏按钮可能在 Qt 写入窗口图标之前就创建完成，按钮会一直
    沿用系统默认图标；显示时重新发送 ``WM_SETICON`` 可强制任务栏重新取图标。
    """
    if sys.platform != "win32":  # pragma: no cover - 非 Windows 无此问题
        return
    try:
        icon_path = PathFactory.set_ico(AppSettings.logo)
        if not icon_path or not Path(icon_path).is_file():
            return
        hwnd = int(window.winId())
        if not hwnd:
            return
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        for slot in (_ICON_SMALL, _ICON_BIG):
            hicon = _TASKBAR_ICONS.get(slot)
            if not hicon:
                hicon = user32.LoadImageW(
                    None,
                    str(icon_path),
                    _IMAGE_ICON,
                    0,
                    0,
                    _LR_LOADFROMFILE | _LR_DEFAULTSIZE,
                )
                if not hicon:
                    continue
                _TASKBAR_ICONS[slot] = hicon
            user32.SendMessageW(hwnd, _WM_SETICON, slot, hicon)
    except (AttributeError, OSError) as exc:  # pragma: no cover - 仅 Windows 真实窗口路径
        Logger.debug(f"重设任务栏图标失败: {exc}")


class GalleryWindow(QMainWindow):
    """插件 Surface 宿主；路由切换、菜单重建与空状态都在这里。"""

    def __init__(self, runtime: GalleryRuntime, route: str = "", parent=None) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.gallery_registry = runtime.registry
        self._current_route = ""
        #: 当前激活的插件 Surface 路由；空串表示当前在原生页或尚未进入任何 Surface。
        #: 生命周期钩子只在这里依据路由变化成对触发（见 _notify_surface_leave/enter）。
        self._active_route = ""
        self.setObjectName("GalleryWindow")
        self.setMouseTracking(True)
        self.ui = UiMainWindow()
        self.ui.setup_ui(self)
        runtime.set_navigation(self.open_route, lambda: self)
        self._force_close = False
        #: 选择性重载期间暂存的 Surface 状态：route -> save_state() 返回值
        self._surface_state_cache: dict[str, object] = {}
        self._dev_watcher = None
        #: 当前停留的原生页；菜单按钮高亮可能被外部重建，保留独立记录更稳
        self._current_native: NativePage | None = None
        try:
            Language.subscribe(self._refresh_tray_texts)
        except Exception as exc:  # noqa: BLE001 - 托盘文案刷新失败不阻断启动
            Logger.debug(f"托盘语言订阅失败: {exc}")
        SetupMainWindow.setup_gui(self)
        self.controller = MainWindowController(self)
        # 必须在 controller 之后接入托盘：托盘的「设置…」项取自
        # MainWindowController.open_settings_window（见 docs/TRAY.md §2）
        runtime.attach_window(self)
        # 内置快捷键与插件共用同一张表：此处注册后，插件条目只要不撞序列即可共存
        self._builtin_shortcuts = install_builtin_shortcuts(self, self.controller)
        # 桌面宠物是基座原生常驻 UI：与托盘同属外壳，先接入托盘再启动宠物
        self._pet = self._start_pet()
        self._start_dev_watch()
        title = "SllkGUI Gallery" if runtime.mode == "gallery" else "SllkGUI"
        self.setWindowTitle(title)
        self.ui.title_bar.set_title(title)
        if self.gallery_registry.surface_count() == 0 and not get_default_page_object(self):
            self._show_empty_state()
        target = route or runtime.default_route()
        if target:
            self.open_route(target)
        errors = self.runtime.errors()
        if errors:
            dependency_errors = [item for item in errors if item.get("code") in _DEPENDENCY_CODES]
            other_errors = [item for item in errors if item.get("code") not in _DEPENDENCY_CODES]
            if dependency_errors:
                self._notify_dependencies(len(dependency_errors))
            if other_errors:
                first = other_errors[0]
                self._notify_failure(
                    first.get("plugin_id", "unknown"),
                    code=first.get("code"),
                    message=f"启动时 {len(other_errors)} 个插件未就绪，详情见日志",
                )

    def _notify_dependencies(self, count: int) -> None:
        """启动期依赖缺失：一条聚合提示 + 直达插件管理（不阻断启动）。"""
        from sllkgui.appcore.feedback import (
            ToastAction,
            ToastAnchor,
            ToastLevel,
            ToastMode,
            ToastRequest,
        )
        from sllkgui.guicore.feedback import toast_bus

        def open_store(_action_id: str) -> None:
            native = native_page_for("page_native_plugin_store")
            if native is not None:
                self._open_native_page(native)

        toast_bus().show(
            ToastAnchor.AUTO,
            ToastRequest(
                text=f"{count} 个插件因缺少依赖未加载",
                title="插件未就绪",
                level=ToastLevel.WARN,
                detail="打开「插件管理」可一键补全依赖；插件数据与设置已保留。",
                code="PYTHON_DEPENDENCY_MISSING",
                scope="base",
                channel="base.gallery",
                mode=ToastMode.REPLACE,
                dedupe_key="gallery.dependencies",
                actions=(ToastAction("open-store", "打开插件管理"),),
                on_action=open_store,
            ),
        )

    def _notify_failure(self, target: str, *, code: str | None = None, message: str | None = None) -> None:
        """把插件加载 / 页面构建失败显示给用户，避免「点了没反应」。

        错误详情仍只写日志；通知条只给出可定位的最小信息（目标、错误码、
        日志入口）。统一走 toast 总线：去重、时长、锚点与堆叠由总线裁决，
        ``gallery`` 只在本组合根弹通知，``guis`` 侧的桩窗口不受影响。
        """
        from sllkgui.appcore.feedback import (
            DedupePolicy,
            ToastAnchor,
            ToastCode,
            ToastLevel,
            ToastRequest,
        )
        from sllkgui.guicore.feedback import toast_bus

        hint = "详情见日志"
        detail = message or hint
        if hint not in detail:
            detail = f"{detail}（{hint}）"
        text = f"{target} · {code}" if code else str(target)
        bus = toast_bus()
        bus.show(
            ToastAnchor.AUTO,
            ToastRequest(
                text=text,
                title="页面加载失败",
                level=ToastLevel.ERROR,
                detail=detail,
                code=str(code or ToastCode.OK),
                scope="base",
                channel="base.gallery",
                dedupe_key=f"gallery.failure.{target}.{code or 'unknown'}",
                dedupe=DedupePolicy.RESTART,
            ),
        )

    # ------------------------------------------------------------------
    # 窗口骨架信号槽（与宿主 MainWindow 约定一致）
    # ------------------------------------------------------------------
    def btn_clicked(self) -> None:
        button = SetupMainWindow.setup_btns(self)
        if button is not None:
            self.controller.handle_button(button)

    def btn_released(self) -> None:
        SetupMainWindow.setup_btns(self)

    def resizeEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        SetupMainWindow.resize_grips(self)
        super().resizeEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self.dragPos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------
    def _notify_surface_leave(self, route: str | None = None) -> None:
        """对当前激活的 Surface 触发 leave（幂等），并清空激活态。"""
        route = route or self._active_route
        self._active_route = ""
        if not route:
            return
        surface = self.gallery_registry.get(route)
        if surface is None:
            return
        try:
            surface.plugin.plugin.on_surface_leave(surface.surface_id)
        except Exception as exc:  # noqa: BLE001 - 插件钩子失败不阻断导航
            Logger.warning(f"插件 {surface.plugin_id} 的 on_surface_leave 失败: {exc}")

    def _notify_surface_enter(self, surface: SurfaceRecord) -> None:
        """对目标 Surface 触发 enter，并记为当前激活态。"""
        self._active_route = surface.route
        try:
            surface.plugin.plugin.on_surface_enter(surface.surface_id)
        except Exception as exc:  # noqa: BLE001 - 插件钩子失败不阻断导航
            Logger.warning(f"插件 {surface.plugin_id} 的 on_surface_enter 失败: {exc}")

    def open_route(self, route: str, *, animate: bool = True) -> bool:
        surface = self.gallery_registry.get(route)
        if surface is None:
            Logger.warning(f"路由不存在: {route}")
            self._notify_failure(route, message="路由不存在，详情见日志")
            return False
        failure: dict[str, str] = {}

        def _record(code: str, detail: str = "") -> None:
            failure["code"] = code
            failure["detail"] = detail

        if not ensure_registered_page(self, surface.page_object, on_error=_record):
            self._notify_failure(
                surface.route,
                code=failure.get("code"),
                message=failure.get("detail") or "页面构建失败，详情见日志",
            )
            return False
        page = self.ui.load_pages.pages.findChild(QWidget, surface.page_object)
        if page is None:
            self._notify_failure(surface.route, message="页面未生成，详情见日志")
            return False
        self._restore_surface_state(page, surface.route)
        # 导航级成对：目标与当前不同时先离开旧页；同页重复打开不触发任何钩子
        if self._active_route and self._active_route != surface.route:
            self._notify_surface_leave()
        previous = self.ui.left_menu.active_button_id()
        self.ui.left_menu.select_only_one(surface.button_id)
        MainFunctions.set_page(
            self,
            page,
            animate=animate,
            menu=self.ui.left_menu,
            button_id=surface.button_id,
            previous_button_id=previous,
        )
        self.ui.title_bar.set_title(surface.display_title(Language.current()))
        self._current_route = route
        self._current_native = None
        if self._active_route != surface.route:
            self._notify_surface_enter(surface)
        record_event(
            "surface.navigated",
            category="gallery",
            payload={"route": route, "mode": self.runtime.mode},
        )
        return True

    def open_surface(self, plugin_id: str, surface_id: str) -> bool:
        return self.open_route(f"{plugin_id}/{surface_id}")

    def current_route(self) -> str:
        return self._current_route

    # ------------------------------------------------------------------
    # 选择性重载
    # ------------------------------------------------------------------
    def _save_surface_state(self, page: QWidget, route: str) -> None:
        saver = getattr(page, "save_state", None)
        if not callable(saver):
            return
        try:
            self._surface_state_cache[route] = saver()
        except Exception as exc:  # noqa: BLE001 - 页面状态保存失败不阻断重载
            Logger.warning(f"Surface 状态保存失败 {route}: {exc}")

    def _restore_surface_state(self, page: QWidget, route: str) -> None:
        if route not in self._surface_state_cache:
            return
        state = self._surface_state_cache.pop(route)
        restorer = getattr(page, "restore_state", None)
        if not callable(restorer):
            return
        try:
            restorer(state)
        except Exception as exc:  # noqa: BLE001 - 页面状态恢复失败不阻断导航
            Logger.warning(f"Surface 状态恢复失败 {route}: {exc}")

    def _remove_pages_for_plugins(self, plugin_ids: set[str]) -> int:
        """只移除目标插件（及其依赖者）已构建的页面，保留其它页面。"""
        targets: dict[str, str] = {}
        for plugin_id in plugin_ids:
            for surface in self.gallery_registry.menu_surface_of_plugin(plugin_id):
                targets[surface.page_object] = surface.route
        if not targets:
            return 0
        pages = self.ui.load_pages.pages
        target_routes = set(targets.values())
        current = pages.currentWidget()
        current_surface = self.gallery_registry.route_for_page(current.objectName()) if current is not None else None
        if current_surface is not None and current_surface.route in target_routes:
            self._notify_surface_leave(current_surface.route)
        elif self._active_route and self._active_route in target_routes:
            self._notify_surface_leave()
        removed = 0
        canceled = False
        for index in range(pages.count() - 1, -1, -1):
            widget = pages.widget(index)
            route = targets.get(widget.objectName())
            if route is None:
                continue
            if not canceled:
                CPageTransition.cancel(pages)
                canceled = True
            self._save_surface_state(widget, route)
            pages.removeWidget(widget)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
            removed += 1
        return removed

    def _sync_left_menu(self) -> None:
        items = get_menu_items("LeftMenu", self)
        sync = getattr(self.ui.left_menu, "sync_menus", None)
        if callable(sync):
            sync(items)
            return
        self.ui.left_menu.clear_menus()
        self.ui.left_menu.add_menus(items)

    def _notify_settings_pages(self, plugin_ids: set[str]) -> None:
        """让打开中的设置窗口重建受影响插件的设置页（未打开时为空操作）。"""
        try:
            from sllkgui.appcore import plugin_namespace, settings_page_bus

            bus = settings_page_bus()
            for plugin_id in plugin_ids:
                bus.notify(plugin_namespace(plugin_id))
        except Exception as exc:  # noqa: BLE001 - 设置页刷新失败不影响重载
            Logger.debug(f"设置页刷新失败: {exc}")

    def _page_exists(self, page_object: str) -> bool:
        return self.ui.load_pages.pages.findChild(QWidget, page_object) is not None

    def _restore_after_selective_reload(self, route: str, native: NativePage | None) -> bool:
        """恢复当前页面；返回是否**新建**了页面（用于诊断计数）。"""
        if route:
            surface = self.gallery_registry.get(route)
            if surface is not None:
                existed = self._page_exists(surface.page_object)
                if self.open_route(route, animate=False):
                    return not existed
        if native is not None:
            existed = self._page_exists(native.page_object)
            if self._open_native_page(native, animate=False):
                return not existed
        target = self.runtime.default_route()
        surface = self.gallery_registry.get(target) if target else None
        if surface is not None:
            existed = self._page_exists(surface.page_object)
            if self.open_route(target, animate=False):
                return not existed
        for item in NATIVE_PAGES:
            existed = self._page_exists(item.page_object)
            if self._open_native_page(item, animate=False):
                return not existed
        self._show_empty_state()
        return True

    def reload_plugin_in_place(
        self,
        plugin_id: str,
        *,
        reason: str = "manual",
        load: bool = True,
    ) -> ReloadResult:
        """只刷新目标插件及其反向依赖者，不重建未受影响页面。

        ``load=False`` 用于停用/卸载：只卸载运行时并移除页面，不再加载。
        当前页面属于目标插件时，会先触发 ``on_surface_leave`` 并安全回退；
        不属于目标插件时，页面实例、滚动与表单状态保持不变。
        """
        current_route, native = self._current_page_context()
        if self.runtime.is_reloading():
            busy = ReloadResult(
                ok=False,
                targets=[plugin_id],
                code="PLUGIN_RELOAD_IN_PROGRESS",
                message="已有插件重载正在进行",
            )
            self._notify_failure(plugin_id, code=busy.code, message=busy.message)
            return busy
        manager = getattr(self.runtime, "manager", None)
        installed = getattr(getattr(manager, "state", None), "plugins", {}).get(plugin_id) if manager else None
        if load and installed is not None and not installed.enabled:
            # 已安装但被停用的插件只更新文件/状态，不重新加载。
            load = False
        if load:
            check = self.runtime.preflight_reload([plugin_id], reason=reason)
            if not check.ok:
                self._notify_failure(
                    plugin_id,
                    code=check.code or None,
                    message=check.message or "插件预检失败，详情见日志",
                )
                return check
            affected = set(check.affected)
        else:
            affected = self.runtime.affected_plugins([plugin_id])
        pages_destroyed = self._remove_pages_for_plugins(affected)
        if reason == "remove":
            prefix = f"{plugin_id}/"
            for route in [key for key in self._surface_state_cache if key.startswith(prefix)]:
                self._surface_state_cache.pop(route, None)
        if load:
            result = self.runtime.reload_plugins([plugin_id], reason=reason)
        else:
            result = self.runtime.unload_plugins([plugin_id], reason=reason)
        result.pages_destroyed = pages_destroyed
        self.gallery_registry = self.runtime.registry
        self._sync_left_menu()
        self._notify_settings_pages(affected)
        result.pages_built = 1 if self._restore_after_selective_reload(current_route, native) else 0

        if result.ok:
            return result

        self._notify_failure(
            plugin_id,
            code=result.code or None,
            message=result.message or "插件重载失败，详情见日志",
        )
        manager = getattr(self.runtime, "manager", None)
        if manager is not None and reason in {"update", "rollback"}:
            try:
                manager.rollback(plugin_id, hot_reload=True)
                again = self.runtime.reload_plugins(sorted(affected), reason="rollback")
                self.gallery_registry = self.runtime.registry
                self._sync_left_menu()
                self._notify_settings_pages(affected)
                self._restore_after_selective_reload(current_route, native)
                result.rollback = "files" if again.ok else "failed"
                if again.ok:
                    result.message = f"{result.message}；已回滚到上一版本"
            except Exception as exc:  # noqa: BLE001 - 回滚失败保留原始错误
                result.rollback = "failed"
                Logger.warning(f"插件回滚失败 {plugin_id}: {exc}")
        elif manager is not None and reason in {"enable", "install"}:
            try:
                manager.set_enabled(plugin_id, False)
            except Exception as exc:  # noqa: BLE001 - 状态回写失败不覆盖原始错误
                Logger.warning(f"插件失败后禁用状态回写失败 {plugin_id}: {exc}")
        return result

    # ------------------------------------------------------------------
    # 开发插件文件监听（--watch）
    # ------------------------------------------------------------------
    def _start_dev_watch(self) -> None:
        if not getattr(self.runtime, "watch", False):
            return
        roots = discover_plugin_dirs(self.runtime.plugin_dirs)
        if not roots:
            Logger.warning("--watch 已开启，但 --plugin-dir 下没有发现插件目录")
            return
        try:
            from .dev_watch import DevPluginWatcher

            watcher = DevPluginWatcher(roots, parent=self)
            watcher.changed.connect(self._on_dev_plugin_changed)
            watcher.start()
            self._dev_watcher = watcher
            Logger.info(f"开发插件文件监听已启动: {len(roots)} 个目录")
        except Exception as exc:  # noqa: BLE001 - 监听失败不应阻断窗口
            Logger.warning(f"开发插件文件监听启动失败: {exc}")

    def _stop_dev_watch(self) -> None:
        watcher = self._dev_watcher
        self._dev_watcher = None
        if watcher is not None:
            try:
                watcher.stop()
                watcher.deleteLater()
            except Exception as exc:  # noqa: BLE001 - 退出路径不阻断
                Logger.debug(f"开发插件监听停止失败: {exc}")

    def _on_dev_plugin_changed(self, root: str) -> None:
        target = Path(root).resolve()
        record = next(
            (item for item in self.runtime.records if Path(item.path).resolve() == target),
            None,
        )
        if record is None:
            Logger.warning(f"开发目录变化未匹配到已加载插件: {root}")
            return
        if self.runtime.is_reloading():
            QTimer.singleShot(300, lambda value=root: self._on_dev_plugin_changed(value))
            return
        result = self.reload_plugin_in_place(record.plugin_id, reason="dev-watch")
        if not result.ok:
            self._notify_failure(
                record.plugin_id,
                code=result.code or None,
                message=result.message or "开发插件重载失败，详情见日志",
            )

    # ------------------------------------------------------------------
    # 重载
    # ------------------------------------------------------------------
    def reload_plugins(self, native_page: str = "") -> None:
        """重载插件；``native_page`` 指定要停留的原生页面。

        插件管理页在页内完成安装/更新/启停后调用本方法：传入它自己的
        ``page_object`` 就会**原地重建并停留**在该页，不再跳到默认路由，
        页面因此不会「点一下就闪到别处」。不传时保持原有语义：优先回到当前
        路由，其次默认路由，最后原生页。
        """
        current = self._current_route
        # 原生页不在路由里：优先用调用方指定的，其次用重载前菜单实际停留的那一页。
        # 后者让忘记传参的调用点也不会把用户弹离原生页。
        native = native_page_for(native_page) if native_page else self._current_native_page()
        getattr(self, "_surface_state_cache", {}).clear()
        self._clear_pages()
        self.runtime.reload()
        self.gallery_registry = self.runtime.registry
        self._current_route = ""
        sync = getattr(self, "_sync_left_menu", None)
        if callable(sync):
            sync()
        else:  # 测试桩/旧宿主：回退到全量菜单重建
            self.ui.left_menu.clear_menus()
            self.ui.left_menu.add_menus(get_menu_items("LeftMenu", self))
        if native is not None:
            # 原地停留：只重建这一张原生页，菜单高亮与标题保持指向它
            if self._open_native_page(native):
                return
        target = current if self.gallery_registry.get(current) else self.runtime.default_route()
        if target and self.open_route(target):
            return
        # 停用了最后一个插件时不存在任何 Surface：回到基座原生页面，
        # 不能把页面栈清空后停在空白背景上。
        if not self._open_default_native_page():
            self._show_empty_state()

    def _on_page_router_switch(self, page_name: str) -> None:
        """菜单直切页面时同步 Surface 生命周期与当前页状态。

        ``PageRouterController`` 不依赖 gallery，因此这里用鸭子类型钩子接收。
        插件页正常进入/离开钩子、``current_route()`` 与选择性重载都依赖这份
        状态；不更新会出现“点原生页后 current_route 仍是上一个插件页”的问题。
        """
        native = native_page_for(page_name)
        if native is not None:
            self._notify_surface_leave()
            self._current_route = ""
            self._current_native = native
            return
        surface = self.gallery_registry.route_for_page(page_name)
        if surface is None:
            self._notify_surface_leave()
            self._current_route = ""
            self._current_native = None
            return
        if self._active_route != surface.route:
            self._notify_surface_leave()
            self._notify_surface_enter(surface)
        self._current_route = surface.route
        self._current_native = None

    def _current_page_context(self) -> tuple[str, NativePage | None]:
        """以页面栈实际当前控件为准，避免菜单切换后状态字段滞后。

        原生页由 ``PageRouterController.switch_page`` 直接切换，不会经过
        ``open_route``；如果只看 ``_current_route`` / ``_active_route``，重载
        时会把上次插件页当成当前页，从而跳离插件管理页。
        """
        current = self.ui.load_pages.pages.currentWidget()
        if current is not None:
            native = native_page_for(current.objectName())
            if native is not None:
                return "", native
            surface = self.gallery_registry.route_for_page(current.objectName())
            if surface is not None:
                return surface.route, None
        if self._current_native is not None:
            return "", self._current_native
        return self._current_route, None

    def _current_native_page(self) -> NativePage | None:
        """重载前左侧菜单停留的原生页；当前在插件 Surface 上时返回 ``None``。"""
        current = self.ui.load_pages.pages.currentWidget()
        if current is not None:
            native = native_page_for(current.objectName())
            if native is not None:
                return native
        if self._current_native is not None:
            return self._current_native
        if self._active_route:
            return None
        active = getattr(self.ui.left_menu, "active_button_id", None)
        button_id = active() if callable(active) else None
        if not button_id:
            return None
        return next((page for page in NATIVE_PAGES if page.button_id == button_id), None)

    def reload_plugins_in_place(self, page_object: str) -> None:
        """重载插件并停留在指定原生页（插件管理页专用）。"""
        self.reload_plugins(native_page=page_object)

    def _open_default_native_page(self, *, animate: bool = True) -> bool:
        for native in NATIVE_PAGES:
            if self._open_native_page(native, animate=animate):
                return True
        return False

    def _open_native_page(self, native: NativePage, *, animate: bool = True) -> bool:
        failure: dict[str, str] = {}

        def _record(code: str, detail: str = "") -> None:
            failure["code"] = code
            failure["detail"] = detail

        if not ensure_registered_page(self, native.page_object, on_error=_record):
            self._notify_failure(
                native.page_object,
                code=failure.get("code"),
                message=failure.get("detail") or "原生页面构建失败，详情见日志",
            )
            return False
        page = self.ui.load_pages.pages.findChild(QWidget, native.page_object)
        if page is None:
            return False
        # 切到原生页也离开当前插件 Surface
        self._notify_surface_leave()
        previous = self.ui.left_menu.active_button_id()
        self.ui.left_menu.select_only_one(native.button_id)
        MainFunctions.set_page(
            self,
            page,
            animate=animate,
            menu=self.ui.left_menu,
            button_id=native.button_id,
            previous_button_id=previous,
        )
        title = str(Language.resolve_key(native.title_key, native.title_fallback))
        self.ui.title_bar.set_title(title)
        self._current_route = ""
        self._current_native = native
        return True

    def _clear_pages(self) -> None:
        """移除全部已构建页面，让重载后的插件重新构建 Surface。

        插件页面持有插件运行时（如 py-rm 的 ``DesktopRuntime``）。只换注册表
        而保留旧页面时，``ensure_registered_page`` 会命中原名控件直接返回，
        新运行时永远不会启动，页面和桌面小部件就会停在旧数据上。
        """
        pages = self.ui.load_pages.pages
        # 销毁页面前先离开当前 Surface（重载会重建，必须成对）
        self._notify_surface_leave()
        CPageTransition.cancel(pages)
        while pages.count():
            widget = pages.widget(0)
            pages.removeWidget(widget)
            # 先 hide()：可见页面 setParent(None) 后会变成顶层窗口并闪现。
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()

    # ------------------------------------------------------------------
    # 空状态
    # ------------------------------------------------------------------
    def _show_empty_state(self) -> None:
        self._current_native = None
        pages = self.ui.load_pages.pages
        existing = pages.findChild(QWidget, "GalleryEmptyState")
        if existing is not None:
            pages.setCurrentWidget(existing)
            return
        page = QWidget()
        page.setObjectName("GalleryEmptyState")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)
        title = QLabel("尚未安装插件" if Language.current().startswith("zh") else "No plugins installed")
        title.setObjectName("GalleryEmptyStateTitle")
        hint = QLabel(
            "打开左侧「插件管理」搜索并安装插件。"
            if Language.current().startswith("zh")
            else "Open Plugin Manager to search and install plugins."
        )
        hint.setObjectName("GalleryEmptyStateHint")
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch(1)
        pages.addWidget(page)
        pages.setCurrentWidget(page)

    # ------------------------------------------------------------------
    # 托盘 / 生命周期
    # ------------------------------------------------------------------
    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        self._force_close = True
        self.close()
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _start_pet(self):
        """启动基座原生桌面宠物；失败只降级为「无宠物」，不影响主窗口。"""
        from sllkgui.guicore.pet import MihoutaoPetController

        try:
            pet = MihoutaoPetController()
            pet.configure(tray=self.runtime.tray)
            pet.start()
        except Exception as exc:  # noqa: BLE001 - 宠物不可用不应阻断 Gallery
            Logger.warning(f"桌面宠物启动失败，已跳过: {type(exc).__name__}: {exc}")
            return None
        record_event("pet.started", category="gallery", payload={"mode": self.runtime.mode})
        return pet

    def _stop_pet(self) -> None:
        """释放宠物；幂等，失败只记日志。"""
        pet = getattr(self, "_pet", None)
        if pet is None:
            return
        try:
            pet.shutdown()
        except Exception as exc:  # noqa: BLE001 - 关闭失败不应阻塞退出
            Logger.debug(f"桌面宠物关闭失败: {exc}")
        self._pet = None

    def _refresh_tray_texts(self) -> None:
        try:
            self.runtime.tray.refresh_texts()
        except Exception as exc:  # noqa: BLE001 - 托盘文案刷新失败不影响切语言
            Logger.debug(f"托盘文案刷新失败: {exc}")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        # 插件启用托盘时，关闭窗口只隐藏，保留桌面小部件与运行时
        if not self._force_close and self.runtime.tray.is_active():
            event.ignore()
            self._trim_ui_caches()
            self.hide()
            record_event("window.hidden_to_tray", category="gallery", payload={"mode": self.runtime.mode})
            return
        try:
            Language.unsubscribe(self._refresh_tray_texts)
        except Exception as exc:  # noqa: BLE001 - 退订失败不应阻塞退出
            Logger.debug(f"托盘语言退订失败: {exc}")
        try:
            self.controller.settings_controller.detach()
        except Exception as exc:  # noqa: BLE001 - 退订失败不应阻塞退出
            Logger.debug(f"Gallery 主题订阅清理失败: {exc}")
        # 内置快捷键绑定在本窗口上：先显式注销，再让运行时整体收尾
        uninstall_builtin_shortcuts()
        self._stop_pet()
        self._stop_dev_watch()
        try:
            self.runtime.shutdown()
        except Exception as exc:  # noqa: BLE001 - 关闭失败不应阻塞退出
            Logger.debug(f"Gallery 关闭时清理失败: {exc}")
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        # 托盘隐藏期间释放过背景图解码缓存，显示前按路径重载
        restore = getattr(self.ui.window, "restore_background_pixmap", None)
        if callable(restore):
            restore()
        super().showEvent(event)
        # 每次显示都会重建任务栏按钮；延后到窗口完成映射后再设一次图标，
        # 避免按钮沿用系统默认图标。
        QTimer.singleShot(0, lambda: _reapply_taskbar_icon(self))

    def _trim_ui_caches(self) -> None:
        """托盘隐藏时释放纯 UI 缓存，重新显示会自动重建。

        - 过场快照：切换页面中途隐藏时，两张全窗口 pixmap 会一直常驻；
        - QPixmapCache：图标/皮肤缩略图的全局缓存（上限 10MB）；
        - 背景图：4K 原图解码约 30MB，窗口尺寸缩放缓存再占一份。
        插件运行时与桌面小部件不受影响，页面控件保留以便瞬时恢复。
        """
        CPageTransition.cancel(self.ui.load_pages.pages)
        QPixmapCache.clear()
        release = getattr(self.ui.window, "release_background_pixmap", None)
        if callable(release):
            release()


def _run_window(runtime: GalleryRuntime, route: str) -> GalleryWindow:
    runtime.bootstrap()
    return GalleryWindow(runtime, route)


def load_gallery(
    *,
    route: str = "",
    data_dir: Path | str | None = None,
) -> GalleryWindow:
    runtime = GalleryRuntime("gallery", data_dir=Path(data_dir) if data_dir else None)
    return _run_window(runtime, route)


def load_run(
    *,
    route: str = "",
    data_dir: Path | str | None = None,
    gallery_dir: Path | str | None = None,
    plugin_dirs: list[Path | str] | None = None,
    safe_mode: bool = False,
    allow_local: bool = False,
    install_missing_deps: bool = True,
    interactive: bool = True,
    index_url: str = "",
    check_tools: bool = False,
    watch: bool = False,
) -> GalleryWindow:
    runtime = GalleryRuntime(
        "run",
        data_dir=Path(data_dir) if data_dir else None,
        gallery_dir=Path(gallery_dir) if gallery_dir else None,
        plugin_dirs=[Path(item) for item in (plugin_dirs or [])],
        safe_mode=safe_mode,
        allow_local=allow_local,
        install_missing_deps=install_missing_deps,
        interactive=interactive,
        index_url=index_url,
        check_tools=check_tools,
        watch=watch,
    )
    return _run_window(runtime, route)


def surface_of(window: GalleryWindow) -> SurfaceRecord | None:
    return window.gallery_registry.get(window.current_route())


__all__ = ["GalleryWindow", "load_gallery", "load_run", "surface_of"]
