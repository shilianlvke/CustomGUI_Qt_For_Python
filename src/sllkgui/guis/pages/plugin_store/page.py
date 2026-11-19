"""插件管理工作台：模式导轨 + 三段工作区 + 业务动作。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from sllkgui.appcore import get_theme_manager
from sllkgui.guicore import (
    CConfirmDialog,
    CDialog,
    CMetricCard,
    CSideNav,
    CSideNavGroup,
    CSideNavItem,
    CSurfacePanel,
    CText,
    CToast,
    run_task,
    single_shot,
)

from .context import PageContext
from .panels import _DiscoverPanel, _InstalledPanel, _SourcesPanel
from .theme import _toast_offset


def build_plugin_store_page(window) -> QWidget:
    """原生页面工厂：由窗口装配层在首次导航时调用。"""
    return StorePage(PageContext(lambda: window))


class StorePage(QWidget):
    """插件管理工作台。"""

    def __init__(self, ctx: PageContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.runtime = ctx.runtime()
        #: 三个模式的计数，用于导轨徽标（切换模式/刷新统计时同步）
        self._counts = {"installed": 0, "discover": 0, "sources": 0}
        self._detail_dialog: CDialog | None = None
        self._busy = False
        self._busy_toast: CToast | None = None
        self._build()
        self.switch_mode("installed")
        self.refresh_stats()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(12)

        hero = QHBoxLayout()
        hero.setSpacing(14)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(CText.with_role("eyebrow", "SLLKGUI / PLUGINS"))
        titles.addWidget(CText.with_role("title", self.ctx.text("store.title", "插件管理")))
        subtitle = CText.with_role("muted", self.ctx.text("store.subtitle", "已安装、发现与来源，在一页内完成"))
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        hero.addLayout(titles, 1)

        self.stat_installed = CMetricCard(self.ctx.text("stats.installed", "已安装"))
        self.stat_enabled = CMetricCard(self.ctx.text("stats.enabled", "启用中"))
        self.stat_sources = CMetricCard(self.ctx.text("stats.sources", "来源"))
        hero.addWidget(self.stat_installed)
        hero.addWidget(self.stat_enabled)
        hero.addWidget(self.stat_sources)
        root.addLayout(hero)

        body = QHBoxLayout()
        body.setSpacing(12)

        rail = QVBoxLayout()
        rail.setContentsMargins(10, 10, 10, 10)
        rail.setSpacing(4)
        self.mode_nav = CSideNav(self._mode_groups(), item_height=58)
        self.mode_nav.itemClicked.connect(self.switch_mode)
        rail.addWidget(self.mode_nav)
        rail.addStretch(1)
        rail_host = CSurfacePanel(radius=8)
        rail_host.setLayout(rail)
        rail_host.setFixedWidth(232)
        body.addWidget(rail_host)

        self.stack = QStackedWidget()
        self.installed_panel = _InstalledPanel(self)
        self.discover_panel = _DiscoverPanel(self)
        self.sources_panel = _SourcesPanel(self)
        self.stack.addWidget(self.installed_panel)
        self.stack.addWidget(self.discover_panel)
        self.stack.addWidget(self.sources_panel)
        workspace = CSurfacePanel(radius=8)
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 14, 16, 14)
        workspace_layout.setSpacing(10)
        workspace_layout.addWidget(self.stack)
        body.addWidget(workspace, 1)
        root.addLayout(body, 1)

    # ------------------------------------------------------------------
    # 模式
    # ------------------------------------------------------------------
    def switch_mode(self, mode: str) -> None:
        mapping = {
            "installed": self.installed_panel,
            "discover": self.discover_panel,
            "sources": self.sources_panel,
        }
        panel = mapping.get(mode)
        if panel is None:
            return
        self.stack.setCurrentWidget(panel)
        self.mode_nav.set_current(mode)
        if mode == "installed":
            self.installed_panel.refresh()
        elif mode == "discover":
            self.discover_panel.search()
        else:
            self.sources_panel.refresh()
        self.refresh_stats()

    # ------------------------------------------------------------------
    # 数据源
    # ------------------------------------------------------------------
    def _manager(self):
        return getattr(self.runtime, "manager", None)

    def _sources(self):
        return getattr(self.runtime, "sources", None)

    # ------------------------------------------------------------------
    # 状态 / 刷新
    # ------------------------------------------------------------------
    def set_status(self, message: str, level: str = "info") -> None:
        """用基座通知条反馈操作结果：浮在页面上，不占布局，自动堆叠与消失。"""
        if not message:
            return
        window = self.ctx.parent_window()
        if window is None:
            return
        severity = {"error": "error", "warning": "warn"}.get(level, level)
        life = 6000 if level in {"error", "warning"} else 3000
        CToast.show_message(
            window,
            message,
            self.ctx.text("store.title", "插件管理"),
            severity,
            life=life,
            offset_top=_toast_offset(window),
        )

    def refresh_stats(self) -> None:
        manager = self._manager()
        rows = list(manager.installed_rows()) if manager is not None else []
        sources = self._sources()
        source_count = len(sources.list()) if sources is not None else 0
        discover = getattr(self, "discover_panel", None)
        discover_count = len(discover.data_view.rows()) if discover is not None else 0
        self.stat_installed.set_value(len(rows))
        self.stat_enabled.set_value(sum(1 for row in rows if row.get("enabled")))
        self.stat_sources.set_value(source_count)
        self._counts = {
            "installed": len(rows),
            "discover": discover_count,
            "sources": source_count,
        }
        self._sync_mode_nav()

    def update_discover_count(self, count: int) -> None:
        self._counts["discover"] = max(0, int(count))
        self._sync_mode_nav()

    #: 模式导轨：(id, 语言键, 文案兜底, 图标)
    _MODE_SPECS = (
        ("installed", "modes.installed", "已安装", "icon_store"),
        ("discover", "modes.discover", "发现", "icon_search"),
        ("sources", "modes.sources", "源", "icon_database"),
    )

    def _mode_groups(self) -> list[CSideNavGroup]:
        items = tuple(
            CSideNavItem(
                mode,
                self.ctx.text(key, caption),
                icon,
                str(self._counts.get(mode, 0)),
            )
            for mode, key, caption, icon in self._MODE_SPECS
        )
        return [CSideNavGroup("", items)]

    def _sync_mode_nav(self) -> None:
        """计数变化后重建导轨；``set_groups`` 会保留当前选中项。"""
        self.mode_nav.set_groups(self._mode_groups())

    def refresh_all(self) -> None:
        self.installed_panel.refresh()
        self.discover_panel.search()
        self.sources_panel.refresh()
        self.refresh_stats()

    def schedule_reload(self) -> None:
        window = self.ctx.parent_window()
        if window is not None and hasattr(window, "reload_plugins"):
            single_shot(window, 120, window.reload_plugins)

    def _theme_changed(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.update()

    # ------------------------------------------------------------------
    # 插件动作
    # ------------------------------------------------------------------
    def _fail(self, code: str, message: str, exc: Exception) -> None:
        self.ctx.report_error(code, message, str(exc))
        self.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")

    def _run_async(
        self,
        *,
        name: str,
        fn: Callable[[], Any],
        busy_text: str,
        success_message: Callable[[Any], str] | None,
        error_code: str,
        error_prefix: str,
        on_done: Callable[[Any], None] | None = None,
        reload_plugins: bool = False,
    ) -> None:
        """把 git / 文件操作放到后台线程，主线程只负责状态与刷新。"""
        if self._busy:
            return
        self._busy = True
        self.setEnabled(False)
        window = self.ctx.parent_window()
        offset = _toast_offset(window) if window is not None else 8
        toast = CToast.show_message(
            window or self,
            busy_text,
            self.ctx.text("store.title", "插件管理"),
            "info",
            life=0,
            offset_top=offset,
        )
        self._busy_toast = toast
        # 页面被语言切换/重载销毁时，持久通知不能留在窗口上。
        try:
            self.destroyed.connect(lambda *_: toast.dismiss(immediate=True))
        except Exception:  # noqa: BLE001 - 清理绑定失败不影响任务
            pass

        def finish() -> None:
            self._busy = False
            self.setEnabled(True)
            toast = self._busy_toast
            self._busy_toast = None
            if toast is not None:
                toast.dismiss()

        def done(result: Any) -> None:
            finish()
            if on_done is not None:
                on_done(result)
            elif success_message is not None:
                self.set_status(success_message(result), "success")
            single_shot(self, 0, self.refresh_all)
            if reload_plugins:
                self.schedule_reload()

        def failed(error: str) -> None:
            finish()
            self._fail(error_code, f"{error_prefix}: {error}", RuntimeError(error))
            single_shot(self, 0, self.refresh_all)

        try:
            run_task(self, lambda _emit: fn(), on_done=done, on_error=failed, name=name)
        except Exception as exc:  # noqa: BLE001 - 任务启动失败不能让页面停在忙碌态
            failed(str(exc))

    def _set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        if self._busy:
            return
        manager = self._manager()
        if manager is None:
            return
        try:
            manager.set_enabled(plugin_id, enabled)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001 - 页面必须保持可用
            self._fail("PLUGIN_STORE_TOGGLE_FAILED", f"切换插件状态失败: {exc}", exc)
        single_shot(self, 0, self.refresh_all)
        self.schedule_reload()

    def _update_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return

        def done(result: dict[str, Any]) -> None:
            if result.get("updated"):
                message = self.ctx.text("status.update_done", "已更新到 v{version}").format(
                    version=result.get("version") or ""
                )
            else:
                message = self.ctx.text("status.up_to_date", "已是最新版本")
            self.set_status(message, "success")

        self._run_async(
            name="plugin_store.update",
            fn=lambda: manager.update(plugin_id),
            busy_text=self.ctx.text("status.updating", "正在更新 {id}…").format(id=plugin_id),
            success_message=None,
            error_code="PLUGIN_STORE_UPDATE_FAILED",
            error_prefix="更新失败",
            on_done=done,
            reload_plugins=True,
        )

    def _rollback_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        self._run_async(
            name="plugin_store.rollback",
            fn=lambda: manager.rollback(plugin_id),
            busy_text=self.ctx.text("status.rolling_back", "正在回滚 {id}…").format(id=plugin_id),
            success_message=lambda _result: self.ctx.text("status.action_done", "操作完成"),
            error_code="PLUGIN_STORE_ROLLBACK_FAILED",
            error_prefix="回滚失败",
            reload_plugins=True,
        )

    def _remove_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None or self._busy:
            return
        ok = CConfirmDialog.ask(
            self.ctx.parent_window() or self,
            title=self.ctx.text("installed.remove", "卸载"),
            message=self.ctx.text("confirm.remove", "确定卸载该插件？数据目录默认保留。"),
            severity="danger",
        )
        if not ok:
            return
        self._run_async(
            name="plugin_store.remove",
            fn=lambda: manager.remove(plugin_id),
            busy_text=self.ctx.text("status.removing", "正在卸载 {id}…").format(id=plugin_id),
            success_message=lambda _result: self.ctx.text("status.action_done", "操作完成"),
            error_code="PLUGIN_STORE_REMOVE_FAILED",
            error_prefix="卸载失败",
            reload_plugins=True,
        )

    def _install_plugin(self, record: dict[str, Any]) -> None:
        manager = self._manager()
        if manager is None or self._busy:
            return
        plugin_id = str(record.get("id") or "")
        # 详情页本身已经展示权限与「安装」按钮，不再叠加一层确认框，
        # 避免详情关闭动画尚未结束时弹出模态框导致窗口失去焦点。
        self._run_async(
            name="plugin_store.install",
            fn=lambda: manager.install(plugin_id, source_id=str(record.get("source") or "")),
            busy_text=self.ctx.text("status.installing", "正在安装 {id}…").format(id=plugin_id),
            success_message=lambda _result: self.ctx.text("status.install_done", "已安装 {count} 个插件").format(
                count=1
            ),
            error_code="PLUGIN_STORE_INSTALL_FAILED",
            error_prefix="安装失败",
            reload_plugins=True,
        )

    # ------------------------------------------------------------------
    # 源动作
    # ------------------------------------------------------------------
    def _add_source(self, url: str) -> bool:
        sources = self._sources()
        if sources is None or not url or self._busy:
            return False
        self._run_async(
            name="plugin_store.source_add",
            fn=lambda: sources.add(url, refresh=True),
            busy_text=self.ctx.text("status.adding_source", "正在添加源…"),
            success_message=lambda record: self.ctx.text("sources.added", "已添加源 {id}").format(
                id=getattr(record, "source_id", url)
            ),
            error_code="PLUGIN_STORE_SOURCE_ADD_FAILED",
            error_prefix="添加源失败",
        )
        return True

    def _refresh_source(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None:
            return
        self._run_async(
            name="plugin_store.source_refresh",
            fn=lambda: sources.refresh(source_id),
            busy_text=self.ctx.text("status.refreshing", "正在刷新源…"),
            success_message=lambda _result: self.ctx.text("status.refresh_done", "源刷新完成"),
            error_code="PLUGIN_STORE_SOURCE_REFRESH_FAILED",
            error_prefix="刷新源失败",
        )

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self._run_async(
            name="plugin_store.source_refresh_all",
            fn=lambda: sources.refresh_all(),
            busy_text=self.ctx.text("status.refreshing", "正在刷新源…"),
            success_message=lambda _result: self.ctx.text("status.refresh_done", "源刷新完成"),
            error_code="PLUGIN_STORE_SOURCE_FAILED",
            error_prefix="刷新源失败",
        )

    def _remove_source(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None or self._busy:
            return
        ok = CConfirmDialog.ask(
            self.ctx.parent_window() or self,
            title=self.ctx.text("sources.remove", "移除"),
            message=self.ctx.text("sources.confirm_remove", "移除源 {id}？已安装插件不受影响。").format(id=source_id),
            severity="warn",
        )
        if not ok:
            return
        self._run_async(
            name="plugin_store.source_remove",
            fn=lambda: sources.remove(source_id),
            busy_text=self.ctx.text("status.removing_source", "正在移除源…"),
            success_message=lambda _result: self.ctx.text("status.action_done", "操作完成"),
            error_code="PLUGIN_STORE_SOURCE_REMOVE_FAILED",
            error_prefix="移除源失败",
        )

    def _set_source_enabled(self, source_id: str, enabled: bool) -> None:
        if self._busy:
            return
        sources = self._sources()
        if sources is None:
            return
        try:
            sources.set_enabled(source_id, enabled)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_TOGGLE_FAILED", f"切换源状态失败: {exc}", exc)
        single_shot(self, 0, self.refresh_all)


__all__ = ["PageContext", "StorePage", "build_plugin_store_page"]
