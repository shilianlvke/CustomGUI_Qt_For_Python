"""基座托盘服务：全进程唯一 ``QSystemTrayIcon``，随基座启动常驻。

协议要点（详见 ``docs/TRAY.md``）：

- 一个应用只有一个托盘图标，由基座持有并常驻；插件不得自建托盘；
- 图标与悬停提示固定使用基座品牌，插件没有任何修改入口；
- 菜单外壳固定包含「显示主窗口」「退出」，插件动作按 ``order`` 插入其前；
- 插件动作以 ``plugin_id:action_id`` 命名隔离，卸载/重载时由基座清理；
- 系统托盘不可用时全部降级为空操作，只告警一次。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sllkgui.appcore import AppSettings, Language, Logger, PathFactory, record_event

from .api import GalleryTray, Permission
from .errors import PLUGIN_PERMISSION_DENIED, GalleryError


@dataclass
class TrayAction:
    action_id: str
    text: str
    callback: Callable[[], None]
    order: int = 100
    plugin_id: str = ""


def _tray_text(key: str, default: str) -> str:
    try:
        return Language.resolve(key, default) or default
    except Exception:  # noqa: BLE001 - 语言表未就绪时用默认文案
        return default


class TrayService:
    """基座级托盘：常驻图标、动作注册、菜单重建与通知。"""

    def __init__(self) -> None:
        self._actions: dict[str, TrayAction] = {}
        self._icon: Any = None
        self._menu: Any = None
        self._show_window: Callable[[], None] | None = None
        self._quit_app: Callable[[], None] | None = None
        self._warned_unavailable = False

    # ------------------------------------------------------------------
    # 窗口回调
    # ------------------------------------------------------------------
    def attach_window(self, show_window: Callable[[], None], quit_app: Callable[[], None]) -> None:
        self._show_window = show_window
        self._quit_app = quit_app

    # ------------------------------------------------------------------
    # 可用性 / 生命周期
    # ------------------------------------------------------------------
    def available(self) -> bool:
        try:
            from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        except ImportError:  # pragma: no cover - 无 Qt 环境
            return False
        return QApplication.instance() is not None and bool(QSystemTrayIcon.isSystemTrayAvailable())

    def is_active(self) -> bool:
        return self._icon is not None and bool(self._icon.isVisible())

    def ensure_visible(self) -> bool:
        """确保基座托盘常驻；系统不支持时返回 ``False`` 并只告警一次。"""
        if not self.available():
            if not self._warned_unavailable:
                self._warned_unavailable = True
                Logger.warning("系统托盘不可用：托盘动作与通知已禁用")
            return False
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        if self._icon is None:
            self._menu = QMenu()
            # 图标固定取基座品牌，插件没有任何替换入口
            self._icon = QSystemTrayIcon(self._base_icon())
            self._icon.setToolTip(self._tooltip_text())
            self._icon.setContextMenu(self._menu)
            self._icon.activated.connect(self._on_activated)
            self._rebuild_menu()
            record_event("tray.shown", category="gallery", payload={"actions": len(self._actions)})
        if not self._icon.isVisible():
            self._icon.show()
        return True

    def _base_icon(self):
        """基座托盘图标：优先应用图标，缺失时回落到内置品牌图标。"""
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        icon = app.windowIcon() if app is not None else QIcon()
        if icon.isNull():
            for path in (
                PathFactory.set_ico(AppSettings.logo),
                PathFactory.set_svg_image(AppSettings.logo_title),
            ):
                icon = QIcon(path)
                if not icon.isNull():
                    break
            if app is not None and not icon.isNull():
                app.setWindowIcon(icon)
        return icon

    @staticmethod
    def _tooltip_text() -> str:
        return _tray_text("custom_ui.sys_name", "SllkGUI")

    def _on_activated(self, reason: Any) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        if self._show_window is not None:
            self._show_window()

    def quit_app(self) -> None:
        record_event("tray.quit", category="gallery")
        if self._quit_app is not None:
            self._quit_app()

    def dispose(self) -> None:
        if self._icon is not None:
            self._icon.hide()
            self._icon.deleteLater()
            self._icon = None
        self._menu = None
        self._actions.clear()
        self._warned_unavailable = False

    # ------------------------------------------------------------------
    # 动作
    # ------------------------------------------------------------------
    def add_action(
        self,
        action_id: str,
        text: str,
        callback: Callable[[], None],
        *,
        order: int = 100,
        plugin_id: str = "",
    ) -> None:
        self._actions[action_id] = TrayAction(action_id, text, callback, order, plugin_id)
        self._rebuild_menu()
        self.ensure_visible()

    def set_action_text(self, action_id: str, text: str) -> None:
        action = self._actions.get(action_id)
        if action is None:
            return
        action.text = text
        self._rebuild_menu()

    def remove_action(self, action_id: str, *, plugin_id: str = "") -> None:
        action = self._actions.get(action_id)
        if action is None:
            return
        if plugin_id and action.plugin_id != plugin_id:
            return
        self._actions.pop(action_id, None)
        self._rebuild_menu()

    def remove_plugin(self, plugin_id: str) -> None:
        for action_id in [key for key, action in self._actions.items() if action.plugin_id == plugin_id]:
            self._actions.pop(action_id, None)
        self._rebuild_menu()

    def action_count(self, plugin_id: str = "") -> int:
        if not plugin_id:
            return len(self._actions)
        return sum(1 for action in self._actions.values() if action.plugin_id == plugin_id)

    # ------------------------------------------------------------------
    # 提示 / 通知
    # ------------------------------------------------------------------
    def show_message(self, title: str, message: str, *, level: str = "info", timeout_ms: int = 4000) -> bool:
        if not self.ensure_visible():
            return False
        from PySide6.QtWidgets import QSystemTrayIcon

        icons = {
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error": QSystemTrayIcon.MessageIcon.Critical,
            "critical": QSystemTrayIcon.MessageIcon.Critical,
            "info": QSystemTrayIcon.MessageIcon.Information,
        }
        self._icon.showMessage(title, message, icons.get(str(level).lower(), QSystemTrayIcon.MessageIcon.Information), timeout_ms)
        return True

    def refresh_texts(self) -> None:
        """语言切换后刷新菜单外壳与悬停提示（插件动作文案由插件自己刷新）。"""
        self._rebuild_menu()
        if self._icon is not None:
            self._icon.setToolTip(self._tooltip_text())

    # ------------------------------------------------------------------
    # 菜单
    # ------------------------------------------------------------------
    def _invoke(self, action: TrayAction) -> None:
        """执行插件动作并隔离异常，避免单个回调打断 Qt 事件循环。"""
        try:
            action.callback()
        except Exception as exc:  # noqa: BLE001 - 插件回调错误不得影响基座
            Logger.exception(f"托盘动作失败 {action.plugin_id}:{action.action_id}: {exc}")

    def _rebuild_menu(self) -> None:
        if self._menu is None:
            return
        self._menu.clear()
        ordered = sorted(self._actions.values(), key=lambda item: (item.order, item.action_id))
        for action in ordered:
            item = self._menu.addAction(action.text)
            item.triggered.connect(lambda _checked=False, entry=action: self._invoke(entry))
        if ordered:
            self._menu.addSeparator()
        show = self._menu.addAction(_tray_text("UI.ui_TrayShowWindow", "显示主窗口"))
        show.triggered.connect(lambda _checked=False: self.show_window())
        quit_item = self._menu.addAction(_tray_text("UI.ui_TrayQuit", "退出"))
        quit_item.triggered.connect(lambda _checked=False: self.quit_app())


class TrayHandle(GalleryTray):
    """单个插件的托盘句柄：权限校验 + 卸载清理。

    图标与悬停提示由基座固定持有，句柄只暴露动作与通知。
    """

    def __init__(self, service: TrayService, plugin_id: str, permissions: tuple[Permission, ...]) -> None:
        self._service = service
        self._plugin_id = plugin_id
        self._permissions = permissions
        self._action_ids: set[str] = set()

    def _require(self, permission: Permission, action: str) -> None:
        if permission not in self._permissions:
            raise GalleryError(
                PLUGIN_PERMISSION_DENIED,
                f"插件未声明 {permission.value} 权限，无法{action}",
                "在 sllkgui-plugin.yml 的 permissions 中添加对应权限",
            )

    def available(self) -> bool:
        return self._service.available()

    def add_action(self, action_id: str, text: str, callback: Callable[[], None], *, order: int = 100) -> None:
        self._require(Permission.TRAY, "注册托盘动作")
        action_id = f"{self._plugin_id}:{action_id}"
        self._service.add_action(action_id, text, callback, order=order, plugin_id=self._plugin_id)
        self._action_ids.add(action_id)

    def set_action_text(self, action_id: str, text: str) -> None:
        self._service.set_action_text(f"{self._plugin_id}:{action_id}", text)

    def remove_action(self, action_id: str) -> None:
        full = f"{self._plugin_id}:{action_id}"
        self._action_ids.discard(full)
        self._service.remove_action(full, plugin_id=self._plugin_id)

    def show_message(self, title: str, message: str, *, level: str = "info", timeout_ms: int = 4000) -> bool:
        self._require(Permission.NOTIFICATIONS, "发送托盘通知")
        return self._service.show_message(title, message, level=level, timeout_ms=timeout_ms)

    def clear(self) -> None:
        for action_id in list(self._action_ids):
            self._service.remove_action(action_id, plugin_id=self._plugin_id)
        self._action_ids.clear()
        self._service.remove_plugin(self._plugin_id)


__all__ = ["TrayAction", "TrayHandle", "TrayService"]
