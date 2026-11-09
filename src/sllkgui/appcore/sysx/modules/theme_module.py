"""主题管理器：主题状态、切换与变更通知（订阅模式）。

主题系统架构：
- 数据源：``AppThemes``（themes 目录下的主题文件）；
- 颜色载体：``ColorPalette``（color_module 中的全局调色板）；
- 全局样式：由表现层（sllkgui.guicore.styles.Styles）按当前调色板生成，
  表现层订阅本管理器，在主题变更时重建样式表；
- 自绘组件：paintEvent 中实时读取 ``ColorPalette``，主题切换后
  由全局样式重刷触发的 repaint 自动生效；需要主动刷新的组件
  （内联样式、tooltip 等）通过 :meth:`subscribe` 注册回调。

使用::

    from sllkgui.appcore import get_theme_manager

    manager = get_theme_manager()
    manager.subscribe(lambda: widget.update_style())   # 弱引用，组件销毁自动移除
    manager.apply("bright")
    manager.cycle()
"""

from __future__ import annotations

import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field

from .color_module import ColorPalette
from .logger_module import Logger
from .telemetry_module import record_event

# 主题循环顺序（与历史行为一致）
THEME_SEQUENCE = ("eye", "bright", "default")


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def _mix(value: str, target: int, amount: float) -> str:
    rgb = _hex_to_rgb(value)
    if rgb is None:
        return value
    amount = max(0.0, min(1.0, amount))
    mixed = tuple(round(component + (target - component) * amount) for component in rgb)
    return "#{:02x}{:02x}{:02x}".format(*mixed)


@dataclass
class ThemeManager:
    """主题切换协调器（单例，通过 :func:`get_theme_manager` 获取）。"""

    _current: str | None = None
    _listeners: list = field(default_factory=list)
    # FIX-07: 可重入锁，供 current()/apply()/_notify() 等共享；apply() 内的
    # 状态更新与读侧在同一把锁下串行，避免半更新状态。
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _accent: str = ""

    # ------------------------------------------------------------------
    def current(self) -> str:
        """当前主题名（首次访问时取 AppSettings.theme_name）。"""
        with self._lock:
            if self._current is None:
                from ..config import AppSettings

                self._current = AppSettings.theme_name
            return self._current

    def apply(self, name: str, accent: str | None = None) -> str:
        """应用指定主题：更新调色板 -> 通知订阅者 -> 记录日志与遥测。

        ``accent`` is an optional ``#rrggbb`` override applied on top of the
        selected theme. It is remembered so ``cycle()`` keeps the user's accent.

        FIX-07: 调色板更新、强调色派生与 ``self._current`` 赋值在 RLock 内完成；
        ``_notify()`` / 日志 / 遥测一律放到锁外，避免持锁回调造成死锁或重入。
        """
        from ..config import AppThemes

        if name not in AppThemes:
            raise ValueError(f"未知主题: {name}（可用: {sorted(AppThemes.keys())}）")
        if accent is not None and _hex_to_rgb(accent) is None:
            raise ValueError(f"无效的强调色: {accent}")

        with self._lock:
            if accent is not None:
                self._accent = accent
            ColorPalette.update(AppThemes[name].data)
            if self._accent:
                base = self._accent
                ColorPalette.custom_context_color = base
                ColorPalette.custom_context_hover = _mix(base, 255, 0.16)
                ColorPalette.custom_context_pressed = _mix(base, 0, 0.18)
                ColorPalette.custom_icon_pressed = ColorPalette.custom_context_hover
            self._current = name
            current, accent_value = name, self._accent

        # 锁外执行：订阅回调、日志与遥测，避免持锁回调引发死锁/重入。
        self._notify()
        Logger.info(f"切换主题: {current}")
        record_event("ui.theme_switch", category="ui", payload={"theme": current, "accent": accent_value})
        return current

    @property
    def accent(self) -> str:
        return self._accent

    def cycle(self) -> str:
        """按循环顺序切换到下一个主题。

        FIX-07: 当前主题不在 THEME_SEQUENCE（如 dracula）时回退到序列首项，
        避免 ``list.index`` 抛 ValueError；不扩大到其它健壮性改动。
        """
        current = self.current()
        if current in THEME_SEQUENCE:
            index = (THEME_SEQUENCE.index(current) + 1) % len(THEME_SEQUENCE)
            return self.apply(THEME_SEQUENCE[index])
        return self.apply(THEME_SEQUENCE[0])

    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[[], None]) -> None:
        """订阅主题变更通知。

        绑定方法使用弱引用；若订阅者提供 ``destroyed`` 信号（如 QObject
        组件），自动连接信号在其销毁时退订，避免回调命中已删除的
        C++ 对象。普通函数/闭包使用强引用（需自行保证生命周期）。
        """
        with self._lock:
            import types

            if isinstance(callback, types.MethodType):
                ref = weakref.WeakMethod(callback)
                self._listeners.append(ref)
                self._bind_destroyed_cleanup(callback.__self__, ref)
            else:
                self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """退订（按等价回调移除）。

        FIX-07: ``WeakMethod()`` 每次返回新的 bound method 对象，``is`` 比较恒为
        False，绑定方法永远退订不掉；这里对绑定方法改用 ``==`` 等价比较，
        普通函数/闭包仍按身份比较。
        """
        with self._lock:
            kept = []
            for entry in self._listeners:
                if isinstance(entry, weakref.WeakMethod):
                    resolved = entry()
                    if resolved is not None and resolved == callback:
                        continue
                elif entry is callback:
                    continue
                kept.append(entry)
            self._listeners = kept

    def _remove_listener(self, ref) -> None:
        with self._lock:
            if ref in self._listeners:
                self._listeners.remove(ref)

    def _bind_destroyed_cleanup(self, obj, ref) -> None:
        """鸭子类型连接 QObject.destroyed 信号（sllkgui.appcore 不依赖 PySide6）。"""
        destroyed = getattr(obj, "destroyed", None)
        if destroyed is not None and callable(getattr(destroyed, "connect", None)):
            try:
                destroyed.connect(lambda *_args, _ref=ref: self._remove_listener(_ref))
            except Exception:
                pass

    @staticmethod
    def _is_deleted_cpp_error(exc: RuntimeError) -> bool:
        message = str(exc)
        return "Internal C++ object" in message or "has been deleted" in message

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        # FIX-07: 收集失效弱引用 / 已销毁 C++ 组件，遍历结束后统一清理，
        # 避免原来「只 continue」导致订阅列表单调增长。
        dead: list = []
        for entry in listeners:
            callback = entry() if isinstance(entry, (weakref.WeakMethod, weakref.ref)) else entry
            if callback is None:
                dead.append(entry)
                continue
            try:
                callback()
            except RuntimeError as exc:
                if self._is_deleted_cpp_error(exc):
                    # C++ 对象已销毁：记录失效订阅，遍历后移除，不再重试
                    dead.append(entry)
                    Logger.debug(f"移除已销毁组件的主题订阅: {exc}")
                else:
                    Logger.warning(f"主题订阅回调执行失败: {exc}")
            except Exception as exc:
                Logger.warning(f"主题订阅回调执行失败: {exc}")
        if dead:
            dead_ids = {id(entry) for entry in dead}
            with self._lock:
                self._listeners = [entry for entry in self._listeners if id(entry) not in dead_ids]


_THEME_MANAGER = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """获取全局主题管理器单例。"""
    return _THEME_MANAGER


__all__ = ["ThemeManager", "get_theme_manager", "THEME_SEQUENCE"]
