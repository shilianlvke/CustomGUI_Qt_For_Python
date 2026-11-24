"""宠物控制器：常驻窗口的生命周期、基座设置同步与能力接入。

统一接入点：
- 事件：经 pet_bus 订阅 pet.command.* 控制宠物、发布 pet.event.* 汇报状态；
- 设置：同步基座原生宠物设置页（core.pet）的值，由 SettingsStore 读写；
  通过 settings_change_bus 接收保存后的变化，即时同步到引擎/窗口；
- 主题：订阅 ThemeManager，用强调色覆盖默认描边/徽标色；
- 语言：订阅 Language，刷新菜单、tooltip、托盘与快捷键说明；
- 快捷键：经 shortcut_registry 注册，冲突时降级并提示；
- 托盘：沿用基座托盘服务注册动作。
所有订阅在 shutdown() 中逐一退订，保证生命周期一致。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sllkgui.appcore import Language, Logger, get_theme_manager, settings_change_bus
from sllkgui.appcore.settings import SettingsSession

from .engine.core import PALETTE, SHAPES, STATES, MihoutaoEngine
from .events import (
    CMD_BURST,
    CMD_COLOR,
    CMD_HIDE,
    CMD_HOP,
    CMD_REACT,
    CMD_SETTING,
    CMD_SHAPE,
    CMD_SHOW,
    CMD_SPIN,
    CMD_STATE,
    CMD_TOGGLE,
    EVT_COLOR_CHANGED,
    EVT_READY,
    EVT_SETTING_CHANGED,
    EVT_SHAPE_CHANGED,
    EVT_STATE_CHANGED,
    EVT_VISIBILITY_CHANGED,
    pet_bus,
)
from .settings import DEFAULTS, KEY_PREFIX, PET_NAMESPACE, STORAGE_KEYS, register_pet_page
from .shortcuts import install_pet_shortcuts, uninstall_pet_shortcuts

if TYPE_CHECKING:
    from .pet_window import PetWindow


class MihoutaoPetController:
    """宠物宿主：持有引擎与窗口，统一接入基座各项基础能力。"""

    def __init__(self) -> None:
        self.preferences: dict[str, Any] = dict(DEFAULTS)
        self.engine: MihoutaoEngine | None = None
        self.window: PetWindow | None = None
        self._tray: Any = None
        self._tray_actions: list[str] = []
        self._started = False
        self._unsub_settings = None
        self._unsub_theme = None
        self._unsub_language = None
        self._theme_manager = None
        self._unsub_events: list[Callable[[], None]] = []
        self._event_handle = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def configure(self, *, tray: Any = None) -> None:
        """注入托盘服务并注册动作（托盘不可用时静默跳过）。"""
        self._tray = tray
        # 基座托盘由运行时常驻拉起；宠物只往已有菜单里加动作，
        # 不应重复触发 ensure_visible（既有托盘测试正是这条契约）。
        if tray is None or not callable(getattr(tray, "is_active", None)):
            return
        if not tray.is_active():
            Logger.debug("跳过宠物托盘动作：基座托盘尚未就绪")
            return
        for action_id, key, fallback, callback, order in (
            ("pet.toggle", "language.UI.ui_PetShortcutToggle", "显示/隐藏猕猴桃", self.toggle, 10),
            ("pet.spin", "language.UI.ui_PetShortcutSpin", "猕猴桃转一圈", self.spin, 20),
            ("pet.hop", "language.UI.ui_PetShortcutHop", "猕猴桃跳一下", self.hop, 30),
        ):
            text = str(Language.resolve_key(key, fallback))
            try:
                tray.add_action(action_id, text, callback, order=order)
            except (AttributeError, TypeError) as exc:
                Logger.debug(f"宠物托盘动作注册失败 {action_id}: {exc}")
                continue
            self._tray_actions.append(action_id)

    def start(self) -> None:
        """启动宠物：注册设置页、订阅能力、读偏好、建引擎。"""
        if self._started:
            return
        self._started = True

        register_pet_page(replace=True)
        self.preferences = self._load_from_store()

        self._unsub_settings = settings_change_bus().subscribe(PET_NAMESPACE, self._on_settings_changed)
        self._theme_manager = get_theme_manager()
        self._unsub_theme = self._theme_manager.subscribe(self._apply_theme)
        self._unsub_language = Language.subscribe(self._apply_language)

        self.engine = MihoutaoEngine(
            shape=str(self.preferences["shape"]),
            color=str(self.preferences["color"]),
        )
        self._apply_theme()
        self.engine.set_deco_scale(float(self.preferences["deco_scale"]))
        self.engine.set_follow_pointer(bool(self.preferences["follow_pointer"]))
        if bool(self.preferences["show_pet"]):
            self.show()
        install_pet_shortcuts(self)
        self._subscribe_events()
        self._publish(EVT_READY, {"visible": bool(self.window and self.window.isVisible())})

    def shutdown(self) -> None:
        """幂等释放：停计时器、退订、注销快捷键并销毁窗口。"""
        if not self._started:
            return
        for unsubscribe in (self._unsub_settings, self._unsub_theme, self._unsub_language):
            if unsubscribe is not None:
                try:
                    unsubscribe()
                except Exception as exc:  # noqa: BLE001 - 退订失败不阻断退出
                    Logger.debug(f"宠物能力退订失败: {exc}")
        self._unsub_settings = self._unsub_theme = self._unsub_language = None
        for unsubscribe in self._unsub_events:
            try:
                unsubscribe()
            except Exception as exc:  # noqa: BLE001 - 退订失败不阻断退出
                Logger.debug(f"宠物事件订阅退订失败: {exc}")
        self._unsub_events.clear()
        self._event_handle = None
        uninstall_pet_shortcuts()
        if self.window is not None:
            try:
                self.window.stop()
                self.window.close()
            except RuntimeError:
                pass
            self.window = None
        self.engine = None
        if self._tray is not None:
            for action_id in self._tray_actions:
                try:
                    self._tray.remove_action(action_id)
                except (AttributeError, RuntimeError):
                    pass
        self._tray_actions.clear()
        self._started = False

    # ------------------------------------------------------------------
    # 设置读写与同步
    # ------------------------------------------------------------------
    @staticmethod
    def _session() -> SettingsSession:
        return SettingsSession()

    @staticmethod
    def _load_from_store() -> dict[str, Any]:
        """从基座 SettingsStore 读取宠物偏好，缺失/损坏回落默认。"""
        values = dict(DEFAULTS)
        try:
            session = MihoutaoPetController._session()
            page = session.registry.page("pet", namespace=PET_NAMESPACE)
            if page is None:
                return values
            for key, default in DEFAULTS.items():
                full = KEY_PREFIX + key
                try:
                    raw = session.value(full)
                except Exception:  # noqa: BLE001 - 未注册键按默认处理
                    continue
                normalized = _normalize(key, raw, default)
                if normalized is not None:
                    values[key] = normalized
        except Exception as exc:  # noqa: BLE001 - 读取失败只告警并回落默认
            Logger.warning(f"宠物设置读取失败，使用默认值: {exc}")
        return values

    def _on_settings_changed(self, changes: dict[str, Any]) -> None:
        """设置页保存后的统一同步入口（core 命名空间回调给的是 storage_key）。"""
        by_storage = {storage: key for key, storage in STORAGE_KEYS.items()}
        for changed_key, value in changes.items():
            key = changed_key if changed_key in DEFAULTS else by_storage.get(changed_key)
            if key is None:
                continue
            normalized = _normalize(key, value, DEFAULTS[key])
            if normalized is not None:
                self.preferences[key] = normalized
        self._sync_all()

    def _sync_all(self) -> None:
        """把当前偏好一次性应用到引擎/窗口（设置变化与初始化共用）。"""
        if self.engine is None:
            return
        p = self.preferences
        if self.engine.shape_name != p["shape"]:
            self.engine.set_shape(str(p["shape"]))
        if self.engine.color_id != p["color"]:
            self.engine.set_color(str(p["color"]))
        self.engine.set_deco_scale(float(p["deco_scale"]))
        self.engine.set_follow_pointer(bool(p["follow_pointer"]))
        if self.window is not None:
            self.window.set_pinned(bool(p["pinned"]))
        if bool(p["show_pet"]):
            self.show()
        else:
            self.hide(run_task=False)

    def _apply_theme(self) -> None:
        """主题/强调色变化：只覆盖原型默认 ring，保留状态显式配色。"""
        if self.engine is None or self._theme_manager is None:
            return
        try:
            accent = str(getattr(self._theme_manager, "accent", "") or "")
        except Exception as exc:  # noqa: BLE001
            Logger.debug(f"读取主题强调色失败: {exc}")
            accent = ""
        self.engine.set_accent_color(accent or None)

    def _apply_language(self) -> None:
        """语言切换：就地刷新窗口/托盘/快捷键文案，不重复注册动作。"""
        if self.window is not None:
            self.window.refresh_texts()
        if self._tray is not None:
            for action_id, key, fallback in (
                ("pet.toggle", "language.UI.ui_PetShortcutToggle", "显示/隐藏猕猴桃"),
                ("pet.spin", "language.UI.ui_PetShortcutSpin", "猕猴桃转一圈"),
                ("pet.hop", "language.UI.ui_PetShortcutHop", "猕猴桃跳一下"),
            ):
                try:
                    self._tray.set_action_text(action_id, str(Language.resolve_key(key, fallback)))
                except (AttributeError, TypeError) as exc:
                    Logger.debug(f"宠物托盘文案刷新失败 {action_id}: {exc}")
        # 快捷键说明随语言更新（同一 owner 覆盖注册，不会重复叠加）
        install_pet_shortcuts(self)

    # ------------------------------------------------------------------
    # 事件协议：命令订阅与状态发布
    # ------------------------------------------------------------------
    def _subscribe_events(self) -> None:
        """订阅全部命令事件；退订闭包集中保存，shutdown 统一释放。"""
        self._event_handle = pet_bus().handle("sllkgui.base")
        for topic in (
            CMD_SHOW,
            CMD_HIDE,
            CMD_TOGGLE,
            CMD_SPIN,
            CMD_HOP,
            CMD_BURST,
            CMD_STATE,
            CMD_SHAPE,
            CMD_COLOR,
            CMD_SETTING,
            CMD_REACT,
        ):
            self._unsub_events.append(self._event_handle.subscribe(topic, self._on_command))

    @staticmethod
    def _publish(topic: str, payload: dict[str, Any] | None = None) -> None:
        """以基座身份发布状态/响应事件；总线保证不向调用方抛异常。"""
        pet_bus().handle("sllkgui.base").publish(topic, payload)

    def _on_command(self, topic: str, event: dict[str, Any]) -> None:
        """统一命令入口：校验载荷后调用控制器动作，异常隔离。"""
        try:
            if topic == CMD_SHOW:
                self.set_setting("show_pet", True)
                self.show()
            elif topic == CMD_HIDE:
                self.hide()
            elif topic == CMD_TOGGLE:
                self.toggle()
            elif topic == CMD_SPIN:
                self.spin()
            elif topic == CMD_HOP:
                self.hop()
            elif topic == CMD_BURST:
                self.burst()
            elif topic == CMD_STATE:
                name = str(event.get("state", ""))
                if name in STATES:
                    self.set_state(name)
                    self._publish(EVT_STATE_CHANGED, {"state": name})
            elif topic == CMD_SHAPE:
                value = str(event.get("shape", ""))
                if value in SHAPES:
                    self.set_shape(value)
                    self._publish(EVT_SHAPE_CHANGED, {"shape": value})
            elif topic == CMD_COLOR:
                value = str(event.get("color", ""))
                if value in PALETTE:
                    self.set_color(value)
                    self._publish(EVT_COLOR_CHANGED, {"color": value})
            elif topic == CMD_SETTING:
                key = str(event.get("key", ""))
                if key in DEFAULTS:
                    self.set_setting(key, event.get("value"))
                    self._publish(EVT_SETTING_CHANGED, {"key": key, "value": self.preferences[key]})
            elif topic == CMD_REACT:
                name = str(event.get("state", ""))
                hold_ms = _coerce_hold(event.get("hold_ms"), bool(event.get("hold")))
                if self.react(name, hold_ms=hold_ms):
                    self._publish(EVT_STATE_CHANGED, {"state": name, "transient": True})
        except Exception as exc:  # noqa: BLE001 - 单个命令失败不影响总线与其它订阅者
            Logger.warning(f"宠物命令处理失败 {topic}: {exc}")

    # ------------------------------------------------------------------
    # 窗口
    # ------------------------------------------------------------------
    def _ensure_window(self) -> PetWindow | None:
        """惰性建窗：没有 QApplication 时返回 None 而不是崩溃。"""
        if self.window is not None:
            return self.window
        if self.engine is None:
            return None
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            Logger.debug("跳过宠物窗口：QApplication 尚未就绪")
            return None
        from .pet_window import PetWindow as Window

        window = Window(self.engine, size=int(self.preferences["size"]))
        window.on_quit = self.hide
        window.on_moved = self._on_window_moved
        window.on_shape_changed = self.set_shape
        window.on_color_changed = self.set_color
        window.on_pinned_changed = self.set_pinned
        window.set_pinned(bool(self.preferences["pinned"]))
        self.window = window
        return window

    def show(self) -> None:
        window = self._ensure_window()
        if window is not None:
            was_visible = window.isVisible()
            window.start()
            if not was_visible:
                self._publish(EVT_VISIBILITY_CHANGED, {"visible": True})

    def hide(self, *, run_task: bool = True) -> None:
        was_visible = self.window is not None and self.window.isVisible()
        if self.window is not None:
            self.window.stop()
        if self.engine is not None:
            # 隐藏时取消未到期的反应，再显示时不会跳回过期情绪
            self.engine.clear_react()
        if run_task:
            self.set_setting("show_pet", False)
        else:
            self.preferences["show_pet"] = False
        if was_visible:
            self._publish(EVT_VISIBILITY_CHANGED, {"visible": False})

    def toggle(self) -> None:
        if self.window is not None and self.window.isVisible():
            self.hide()
        else:
            self.set_setting("show_pet", True)
            self.show()

    # ------------------------------------------------------------------
    # 动作与设置写入
    # ------------------------------------------------------------------
    def set_setting(self, key: str, value: Any) -> None:
        """写入一个偏好：统一经 SettingsSession.save()，持久化由基座负责。"""
        if key not in DEFAULTS:
            return
        normalized = _normalize(key, value, DEFAULTS[key])
        if normalized is None:
            return
        self.preferences[key] = normalized
        try:
            session = self._session()
            full = KEY_PREFIX + key
            if session.registry.page("pet", namespace=PET_NAMESPACE) is not None:
                session.set(full, normalized)
                session.save()
        except Exception as exc:  # noqa: BLE001 - 持久化失败不影响本次会话
            Logger.warning(f"宠物偏好保存失败: {key}: {exc}")
        self._sync_all()

    def spin(self) -> None:
        if self.engine is not None:
            self.engine.spin_once()

    def hop(self) -> None:
        if self.engine is not None:
            self.engine.hop_once()

    def burst(self) -> None:
        if self.engine is not None:
            self.engine.burst_once()

    def set_state(self, name: str) -> None:
        """用户显式选择情绪：保持，直到下次显式切换。"""
        if self.engine is not None:
            self.engine.set_mode("hold")
            self.engine.set_state(name)

    def react(self, name: str, *, hold_ms: float = 1600) -> bool:
        """瞬态情绪反应：``hold_ms`` 后自动回到反应前的常态。

        基座操作（搜索、插件安装、切页等）用它，避免把宠物永久钉在某次
        操作的情绪上。``hold_ms <= 0`` 表示保持到下次显式切换。
        """
        if self.engine is None:
            return False
        return bool(self.engine.react(name, hold_ms=hold_ms))

    def set_shape(self, shape_id: str) -> None:
        if shape_id in SHAPES:
            self.set_setting("shape", shape_id)

    def set_color(self, color_id: str) -> None:
        if color_id in PALETTE:
            self.set_setting("color", color_id)

    def set_follow_pointer(self, enabled: bool) -> None:
        self.set_setting("follow_pointer", bool(enabled))

    def set_pinned(self, enabled: bool) -> None:
        self.set_setting("pinned", bool(enabled))

    def set_deco_scale(self, value: float) -> None:
        self.set_setting("deco_scale", value)

    def _on_window_moved(self, x: int, y: int) -> None:
        """窗口位置变化只更新内存值，避免拖拽期间高频落盘。"""
        self.preferences["pos_x"] = int(x)
        self.preferences["pos_y"] = int(y)


def _coerce_hold(raw: Any, hold: bool) -> float:
    """把事件载荷里的 ``hold_ms`` 归一成毫秒；``hold=True`` 表示保持。"""
    if hold:
        return 0.0
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 1600.0
    return float(raw)


def _normalize(key: str, raw: Any, default: Any) -> Any:
    """按声明默认值校验偏好值；非法返回 None 表示「沿用默认」。"""
    if key in ("size",):
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None
        return max(96, min(480, raw))
    if key == "deco_scale":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        return max(0.55, min(1.5, float(raw)))
    if key == "shape":
        return raw if raw in SHAPES else None
    if key == "color":
        return raw if raw in PALETTE else None
    if isinstance(default, bool):
        return bool(raw) if isinstance(raw, bool) else None
    return None


__all__ = ["MihoutaoPetController"]
