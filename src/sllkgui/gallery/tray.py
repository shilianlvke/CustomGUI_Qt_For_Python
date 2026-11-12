"""基座托盘服务：全进程唯一 ``QSystemTrayIcon``，插件只注册动作。

设计约束：

- 一个应用只有一个托盘图标，由 Gallery 窗口持有；插件不得自建托盘。
- 菜单外壳固定包含「显示主窗口」「退出」，插件动作按 ``order`` 插入其前。
- 托盘在插件首次注册动作/通知时惰性创建；系统托盘不可用时全部降级为空操作。
- 插件卸载时按 ``plugin_id`` 清理动作，避免重载后残留。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sllkgui.appcore import Language, Logger, record_event

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
    """基座级托盘：动作注册、菜单重建、图标与通知。"""

    def __init__(self) -> None:
        self._actions: dict[str, TrayAction] = {}
        self._icon: Any = None
        self._menu: Any = None
        self._show_window: Callable[[], None] | None = None
        self._quit_app: Callable[[], None] | None = None
        self._tooltip = ""
        self._icon_path = ""
        self._icon_owner = ""
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
        if self._icon is not None:
            if not self._icon.isVisible():
                self._icon.show()
            return True
        if not self.available():
            if not self._warned_unavailable:
                self._warned_unavailable = True
                Logger.warning("系统托盘不可用：托盘动作与通知已禁用")
            return False
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

        app = QApplication.instance()
        assert app is not None  # available() 已保证
        self._menu = QMenu()
        self._icon = QSystemTrayIcon(QIcon(self._icon_path) if self._icon_path else app.windowIcon())
        self._icon.setToolTip(self._tooltip or _tray_text("custom_ui.sys_name", "SllkGUI"))
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        self._rebuild_menu()
        self._icon.show()
        record_event("tray.shown", category="gallery", payload={"actions": len(self._actions)})
        return True

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
        if self._icon_owner == plugin_id:
            self._icon_path = ""
            self._icon_owner = ""
            if self._icon is not None:
                from PySide6.QtWidgets import QApplication

                app = QApplication.instance()
                if app is not None:
                    self._icon.setIcon(app.windowIcon())
        self._rebuild_menu()

    def action_count(self, plugin_id: str = "") -> int:
        if not plugin_id:
            return len(self._actions)
        return sum(1 for action in self._actions.values() if action.plugin_id == plugin_id)

    # ------------------------------------------------------------------
    # 图标 / 提示 / 通知
    # ------------------------------------------------------------------
    def set_icon(self, path: str | Path | None, *, plugin_id: str = "") -> bool:
        self._icon_path = str(path) if path else ""
        self._icon_owner = plugin_id if path else ""
        if self._icon is None:
            return self.ensure_visible()
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication

        if self._icon_path:
            icon = QIcon(self._icon_path)
        else:
            app = QApplication.instance()
            icon = app.windowIcon() if app is not None else QIcon()
        self._icon.setIcon(icon)
        return True

    def set_tooltip(self, text: str) -> None:
        self._tooltip = text
        if self._icon is not None:
            self._icon.setToolTip(text or _tray_text("custom_ui.sys_name", "SllkGUI"))

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
        self._rebuild_menu()

    # ------------------------------------------------------------------
    # 菜单
    # ------------------------------------------------------------------
    def _rebuild_menu(self) -> None:
        if self._menu is None:
            return
        self._menu.clear()
        ordered = sorted(self._actions.values(), key=lambda item: (item.order, item.action_id))
        for action in ordered:
            item = self._menu.addAction(action.text)
            item.triggered.connect(lambda _checked=False, cb=action.callback: cb())
        if ordered:
            self._menu.addSeparator()
        show = self._menu.addAction(_tray_text("UI.ui_TrayShowWindow", "显示主窗口"))
        show.triggered.connect(lambda _checked=False: self.show_window())
        quit_item = self._menu.addAction(_tray_text("UI.ui_TrayQuit", "退出"))
        quit_item.triggered.connect(lambda _checked=False: self.quit_app())


class TrayHandle(GalleryTray):
    """单个插件的托盘句柄：权限校验 + 卸载清理。"""

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

    def set_icon(self, path: str | Path | None = None) -> bool:
        self._require(Permission.TRAY, "设置托盘图标")
        return self._service.set_icon(path, plugin_id=self._plugin_id)

    def set_tooltip(self, text: str) -> None:
        self._require(Permission.TRAY, "设置托盘提示")
        self._service.set_tooltip(text)

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
