"""宠物控制器：常驻窗口的生命周期、偏好持久化与托盘动作。

与插件解耦：基座窗口层在启动后调用 start()，关闭时调用 shutdown()。
偏好写在 <data_root>/settings/pet.yaml（与 user.yaml 分离，避免污染基座 schema），
读写失败只告警，绝不影响启动或主窗口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from sllkgui.appcore import Logger, user_settings_path

from .engine.core import PALETTE, SHAPES, MihoutaoEngine

if TYPE_CHECKING:
    from .pet_window import PetWindow

SETTINGS_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "show_pet": True,
    "follow_pointer": True,
    "pinned": True,
    "shape": "blob",
    "color": "green",
    "size": 220,
    "deco_scale": 1.32,
    "pos_x": None,
    "pos_y": None,
}


def data_root():
    """可写数据根：从基座公开的 user.yaml 路径反推。

    表现层不允许 import appcore.sysx 内部模块（见
    tests/test_architecture_boundaries.py），此处与
    settings_window.pages._data_root 采用同样的公开推导方式。
    """
    return user_settings_path().parent.parent


def settings_path():
    """宠物偏好文件路径（随数据根走，清理数据目录即重置）。"""
    return data_root() / "settings" / "pet.yaml"


def load_preferences() -> dict[str, Any]:
    """读取偏好：缺失/损坏/非法一律回落默认值，绝不抛给调用方。"""
    data = dict(DEFAULTS)
    path = settings_path()
    if not path.is_file():
        return data
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        Logger.warning(f"宠物偏好读取失败，使用默认值: {path}: {exc}")
        return data
    if not isinstance(raw, dict):
        return data
    for key, default in DEFAULTS.items():
        value = raw.get(key, default)
        if key in ("size",):
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            value = max(96, min(480, value))
        elif key == "deco_scale":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            value = max(0.55, min(1.5, float(value)))
        elif key in ("pos_x", "pos_y"):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                continue
        elif key == "shape":
            if value not in SHAPES:
                continue
        elif key == "color":
            if value not in PALETTE:
                continue
        elif isinstance(default, bool) and not isinstance(value, bool):
            continue
        data[key] = value
    return data


def save_preferences(values: dict[str, Any]) -> bool:
    """原子写入偏好；失败只告警并返回 False。"""
    path = settings_path()
    payload = {**DEFAULTS, **{k: v for k, v in values.items() if k in DEFAULTS}}
    payload["schema_version"] = SETTINGS_VERSION
    tmp = path.with_suffix(".yaml.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=True), encoding="utf-8")
        import os

        os.replace(tmp, path)
    except (OSError, yaml.YAMLError) as exc:
        Logger.warning(f"宠物偏好保存失败: {path}: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


class MihoutaoPetController:
    """宠物宿主：持有引擎与窗口，暴露给托盘 / 设置页的动作。"""

    def __init__(self) -> None:
        self.preferences: dict[str, Any] = dict(DEFAULTS)
        self.engine: MihoutaoEngine | None = None
        self.window: PetWindow | None = None
        self._tray: Any = None
        self._tray_actions: list[str] = []
        self._started = False

    def configure(self, *, tray: Any = None) -> None:
        """注入托盘服务并注册动作（托盘不可用时静默跳过）。"""
        self._tray = tray
        if tray is None:
            return
        for action_id, text, callback, order in (
            ("pet.toggle", "显示/隐藏猕猴桃", self.toggle, 10),
            ("pet.spin", "猕猴桃转一圈", self.spin, 20),
            ("pet.hop", "猕猴桃跳一下", self.hop, 30),
        ):
            try:
                tray.add_action(action_id, text, callback, order=order)
            except (AttributeError, TypeError) as exc:
                Logger.debug(f"宠物托盘动作注册失败 {action_id}: {exc}")
                continue
            self._tray_actions.append(action_id)

    def start(self) -> None:
        """启动宠物：读偏好、建引擎；按偏好决定是否立即显示。"""
        if self._started:
            return
        self._started = True
        self.preferences = load_preferences()
        self.engine = MihoutaoEngine(
            shape=str(self.preferences["shape"]),
            color=str(self.preferences["color"]),
        )
        self.engine.set_deco_scale(float(self.preferences["deco_scale"]))
        self.engine.set_follow_pointer(bool(self.preferences["follow_pointer"]))
        if bool(self.preferences["show_pet"]):
            self.show()

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
        pos_x = self.preferences.get("pos_x")
        pos_y = self.preferences.get("pos_y")
        if isinstance(pos_x, int) and isinstance(pos_y, int):
            window.move(pos_x, pos_y)
        self.window = window
        return window

    def show(self) -> None:
        window = self._ensure_window()
        if window is not None:
            window.start()

    def hide(self) -> None:
        if self.window is not None:
            self.window.stop()
        self.preferences["show_pet"] = False
        self._persist()

    def toggle(self) -> None:
        if self.window is not None and self.window.isVisible():
            self.hide()
        else:
            self.preferences["show_pet"] = True
            self.show()
            self._persist()

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
        if self.engine is not None:
            self.engine.set_mode("hold")
            self.engine.set_state(name)

    def set_shape(self, shape_id: str) -> None:
        if self.engine is None or shape_id not in SHAPES:
            return
        self.engine.set_shape(shape_id)
        self.preferences["shape"] = shape_id
        self._persist()

    def set_color(self, color_id: str) -> None:
        if self.engine is None or color_id not in PALETTE:
            return
        self.engine.set_color(color_id)
        self.preferences["color"] = color_id
        self._persist()

    def set_follow_pointer(self, enabled: bool) -> None:
        if self.engine is not None:
            self.engine.set_follow_pointer(bool(enabled))
        self.preferences["follow_pointer"] = bool(enabled)
        self._persist()

    def set_pinned(self, enabled: bool) -> None:
        if self.window is not None:
            self.window.set_pinned(bool(enabled))
        self.preferences["pinned"] = bool(enabled)
        self._persist()

    def set_deco_scale(self, value: float) -> None:
        scale = max(0.55, min(1.5, float(value)))
        if self.engine is not None:
            self.engine.set_deco_scale(scale)
        self.preferences["deco_scale"] = scale
        self._persist()

    def _on_window_moved(self, x: int, y: int) -> None:
        self.preferences["pos_x"] = int(x)
        self.preferences["pos_y"] = int(y)
        self._persist()

    def _persist(self) -> None:
        save_preferences(dict(self.preferences))

    def shutdown(self) -> None:
        """幂等释放：停计时器、销毁窗口、摘托盘动作。"""
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
