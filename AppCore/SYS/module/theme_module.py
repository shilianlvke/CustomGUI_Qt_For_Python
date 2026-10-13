"""主题管理器：主题状态、切换与变更通知（订阅模式）。

主题系统架构：
- 数据源：``AppThemes``（themes 目录下的主题文件）；
- 颜色载体：``ColorPalette``（color_module 中的全局调色板）；
- 全局样式：由表现层（GuiCore.styles.Styles）按当前调色板生成，
  表现层订阅本管理器，在主题变更时重建样式表；
- 自绘组件：paintEvent 中实时读取 ``ColorPalette``，主题切换后
  由全局样式重刷触发的 repaint 自动生效；需要主动刷新的组件
  （内联样式、tooltip 等）通过 :meth:`subscribe` 注册回调。

使用::

    from AppCore import get_theme_manager

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


@dataclass
class ThemeManager:
    """主题切换协调器（单例，通过 :func:`get_theme_manager` 获取）。"""

    _current: str | None = None
    _listeners: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # ------------------------------------------------------------------
    def current(self) -> str:
        """当前主题名（首次访问时取 AppSettings.theme_name）。"""
        with self._lock:
            if self._current is None:
                from ..config import AppSettings

                self._current = AppSettings.theme_name
            return self._current

    def apply(self, name: str) -> str:
        """应用指定主题：更新调色板 -> 通知订阅者 -> 记录日志与遥测。"""
        from ..config import AppThemes

        if name not in AppThemes:
            raise ValueError(f"未知主题: {name}（可用: {sorted(AppThemes.keys())}）")

        ColorPalette.update(AppThemes[name].data)
        self._current = name
        self._notify()
        Logger.info(f"切换主题: {name}")
        record_event("ui.theme_switch", category="ui", payload={"theme": name})
        return name

    def cycle(self) -> str:
        """按循环顺序切换到下一个主题。"""
        index = (THEME_SEQUENCE.index(self.current()) + 1) % len(THEME_SEQUENCE)
        return self.apply(THEME_SEQUENCE[index])

    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[[], None]) -> None:
        """订阅主题变更通知。

        绑定方法使用弱引用；若订阅者提供 ``destroyed`` 信号（如 QObject
        组件），自动连接信号在其销毁时退订，避免回调命中已删除的
        C++ 对象。普通函数/闭包使用强引用（需自行保证生命周期）。
        """
        with self._lock:
            if hasattr(callback, "__self__"):
                ref = weakref.WeakMethod(callback)
                self._listeners.append(ref)
                self._bind_destroyed_cleanup(callback.__self__, ref)
            else:
                self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """退订（按等价回调移除）。"""
        with self._lock:
            self._listeners = [
                entry
                for entry in self._listeners
                if not (isinstance(entry, weakref.WeakMethod) and entry() is callback) and entry is not callback
            ]

    def _remove_listener(self, ref) -> None:
        with self._lock:
            if ref in self._listeners:
                self._listeners.remove(ref)

    def _bind_destroyed_cleanup(self, obj, ref) -> None:
        """鸭子类型连接 QObject.destroyed 信号（AppCore 不依赖 PySide6）。"""
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
        for entry in listeners:
            callback = entry() if isinstance(entry, (weakref.WeakMethod, weakref.ref)) else entry
            if callback is None:
                continue
            try:
                callback()
            except RuntimeError as exc:
                if self._is_deleted_cpp_error(exc):
                    # C++ 对象已销毁：移除失效订阅，不再重试
                    self._remove_listener(entry)
                    Logger.debug(f"移除已销毁组件的主题订阅: {exc}")
                else:
                    Logger.warning(f"主题订阅回调执行失败: {exc}")
            except Exception as exc:
                Logger.warning(f"主题订阅回调执行失败: {exc}")


_THEME_MANAGER = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """获取全局主题管理器单例。"""
    return _THEME_MANAGER


__all__ = ["ThemeManager", "get_theme_manager", "THEME_SEQUENCE"]
