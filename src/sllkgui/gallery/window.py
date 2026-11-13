"""Gallery 外壳窗口：组件预览与插件运行共用同一套窗口骨架。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmapCache
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from sllkgui.appcore import Language, Logger, record_event
from sllkgui.gallery.registry import SurfaceRecord
from sllkgui.gallery.runtime import GalleryRuntime
from sllkgui.guicore import CPageTransition
from sllkgui.guis.windows.main_window.controller import MainWindowController
from sllkgui.guis.windows.main_window.functions import MainFunctions
from sllkgui.guis.windows.main_window.native_pages import NATIVE_PAGES, NativePage
from sllkgui.guis.windows.main_window.registry import (
    ensure_registered_page,
    get_default_page_object,
    get_menu_items,
)
from sllkgui.guis.windows.main_window.setup_main_window import SetupMainWindow
from sllkgui.guis.windows.main_window.ui_main import UiMainWindow


class GalleryWindow(QMainWindow):
    """插件 Surface 宿主；路由切换、菜单重建与空状态都在这里。"""

    def __init__(self, runtime: GalleryRuntime, route: str = "", parent=None) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.gallery_registry = runtime.registry
        self._current_route = ""
        self.setObjectName("GalleryWindow")
        self.setMouseTracking(True)
        self.ui = UiMainWindow()
        self.ui.setup_ui(self)
        runtime.set_navigation(self.open_route, lambda: self)
        runtime.attach_window(self)
        self._force_close = False
        try:
            Language.subscribe(self._refresh_tray_texts)
        except Exception as exc:  # noqa: BLE001 - 托盘文案刷新失败不阻断启动
            Logger.debug(f"托盘语言订阅失败: {exc}")
        SetupMainWindow.setup_gui(self)
        self.controller = MainWindowController(self)
        title = "SllkGUI Gallery" if runtime.mode == "gallery" else "SllkGUI"
        self.setWindowTitle(title)
        self.ui.title_bar.set_title(title)
        if self.gallery_registry.surface_count() == 0 and not get_default_page_object():
            self._show_empty_state()
        target = route or runtime.default_route()
        if target:
            self.open_route(target)

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
        self.focusNextChild()

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------
    def open_route(self, route: str) -> bool:
        surface = self.gallery_registry.get(route)
        if surface is None:
            Logger.warning(f"路由不存在: {route}")
            return False
        if not ensure_registered_page(self, surface.page_object):
            return False
        page = self.ui.load_pages.pages.findChild(QWidget, surface.page_object)
        if page is None:
            return False
        previous = self.ui.left_menu.active_button_id()
        self.ui.left_menu.select_only_one(surface.button_id)
        MainFunctions.set_page(
            self,
            page,
            menu=self.ui.left_menu,
            button_id=surface.button_id,
            previous_button_id=previous,
        )
        self.ui.title_bar.set_title(surface.display_title(Language.current()))
        self._current_route = route
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
    # 重载
    # ------------------------------------------------------------------
    def reload_plugins(self) -> None:
        current = self._current_route
        self._clear_pages()
        self.runtime.reload()
        self.gallery_registry = self.runtime.registry
        self._current_route = ""
        self.ui.left_menu.clear_menus()
        self.ui.left_menu.add_menus(get_menu_items("LeftMenu"))
        target = current if self.gallery_registry.get(current) else self.runtime.default_route()
        if target and self.open_route(target):
            return
        # 停用了最后一个插件时不存在任何 Surface：回到基座原生页面，
        # 不能把页面栈清空后停在空白背景上。
        if not self._open_default_native_page():
            self._show_empty_state()

    def _open_default_native_page(self) -> bool:
        for native in NATIVE_PAGES:
            if self._open_native_page(native):
                return True
        return False

    def _open_native_page(self, native: NativePage) -> bool:
        if not ensure_registered_page(self, native.page_object):
            return False
        page = self.ui.load_pages.pages.findChild(QWidget, native.page_object)
        if page is None:
            return False
        previous = self.ui.left_menu.active_button_id()
        self.ui.left_menu.select_only_one(native.button_id)
        MainFunctions.set_page(
            self,
            page,
            menu=self.ui.left_menu,
            button_id=native.button_id,
            previous_button_id=previous,
        )
        title = str(Language.resolve_key(native.title_key, native.title_fallback))
        self.ui.title_bar.set_title(title)
        self._current_route = ""
        return True

    def _clear_pages(self) -> None:
        """移除全部已构建页面，让重载后的插件重新构建 Surface。

        插件页面持有插件运行时（如 py-rm 的 ``DesktopRuntime``）。只换注册表
        而保留旧页面时，``ensure_registered_page`` 会命中原名控件直接返回，
        新运行时永远不会启动，页面和桌面小部件就会停在旧数据上。
        """
        pages = self.ui.load_pages.pages
        CPageTransition.cancel(pages)
        while pages.count():
            widget = pages.widget(0)
            pages.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()

    # ------------------------------------------------------------------
    # 空状态
    # ------------------------------------------------------------------
    def _show_empty_state(self) -> None:
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
    )
    return _run_window(runtime, route)


def surface_of(window: GalleryWindow) -> SurfaceRecord | None:
    return window.gallery_registry.get(window.current_route())


__all__ = ["GalleryWindow", "load_gallery", "load_run", "surface_of"]
