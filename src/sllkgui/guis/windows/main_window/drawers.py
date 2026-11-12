"""四向抽屉的统一布局策略：Static 占位 / Overlay 浮层。

``drawer_mode`` 是一个全局开关，同时作用于左、右、上、下四个抽屉：

* ``static``：抽屉框是布局成员，展开时挤压内容区（基座既有行为）；
* ``overlay``：抽屉框脱离布局、浮在内容区之上，展开时内容区宽度不变。

左 / 上 / 下三个抽屉的框直接复用；右侧抽屉就是设置面板
（``CSettingsDrawer``），在 static 模式下嵌入右列、在 overlay 模式下
浮在内容区右侧。``menu_mode`` 仍只控制左侧图标菜单，与本模块无关。

运行期切换模式会保留当前已展开的抽屉：先记录展开状态，换容器后再恢复，
避免用户在外观抽屉里点「抽屉模式」时面板自己消失。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect

from sllkgui.appcore import AppSettings, ColorPalette

#: 支持的两个取值
DRAWER_MODES = ("static", "overlay")
#: 由本模块直接搬动的三个方向（右侧由外观面板自身负责）
LAYOUT_DIRECTIONS = ("left", "top", "bottom")


def normalize_drawer_mode(mode) -> str:
    """把外部传入的模式归一化为 ``static`` / ``overlay``。"""
    return "overlay" if str(mode).lower() == "overlay" else "static"


class _DrawerResizeTracker(QObject):
    """窗口尺寸变化时把浮层抽屉重新贴回内容区边缘。"""

    def __init__(self, host: DrawerLayout):
        super().__init__(host.window)
        self._host = host

    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if obj is self._host.window and event.type() == QEvent.Type.Resize:
            self._host.sync_overlay_geometry()
        return False


class DrawerLayout:
    """四个抽屉共用的 Static / Overlay 容器与开合策略。"""

    def __init__(self, window):
        self.window = window
        self._mode = "static"
        self._overlay_ready = False
        self._overlay_open = {name: False for name in LAYOUT_DIRECTIONS}
        self._animations: dict[str, QPropertyAnimation] = {}
        self._indices: dict[str, int] = {}
        self._tracker: _DrawerResizeTracker | None = None
        self._right_embedded = False

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    @property
    def ui(self):
        return getattr(self.window, "ui", None)

    def mode(self) -> str:
        return self._mode

    def is_open(self, name: str) -> bool:
        """抽屉是否处于展开状态（两种模式语义一致）。"""
        if self._mode == "overlay" and self._overlay_ready:
            return bool(self._overlay_open.get(name))
        frame = self._frame(name)
        if frame is None:
            return False
        minimum, _maximum, axis = self._limits(name)
        return (frame.width() if axis == "width" else frame.height()) > minimum

    def right_is_open(self) -> bool:
        """右侧设置抽屉是否展开。"""
        if self._mode == "overlay" and self._overlay_ready:
            panel = self._panel()
            return bool(panel is not None and panel.is_open())
        frame = self._frame("right")
        if frame is None:
            return False
        return frame.width() > int(AppSettings.right_column_size.minimum)

    # ------------------------------------------------------------------
    # 模式切换
    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        value = normalize_drawer_mode(mode)
        if (
            value == self._mode
            and self._overlay_ready == (value == "overlay")
            and self._right_ready(value)
        ):
            return

        # 静态开合动画改的是 min/max 尺寸；换容器前必须先停掉，否则动画会
        # 继续写尺寸属性，把浮层的固定尺寸又改回去。
        group = getattr(self.window, "group", None)
        stop = getattr(group, "stop", None)
        if callable(stop):
            stop()

        states = {name: self.is_open(name) for name in LAYOUT_DIRECTIONS}
        right_open = self.right_is_open()
        self._mode = value

        if value == "static":
            if self._overlay_ready:
                self._leave_overlay()
            self._apply_static(states, right_open)
        else:
            self._enter_overlay(states, right_open)

    def _right_ready(self, mode: str) -> bool:
        if self._panel() is None:
            return True
        return self._right_embedded if mode == "static" else not self._right_embedded

    # ------------------------------------------------------------------
    # Static：布局占位
    # ------------------------------------------------------------------
    def _apply_static(self, states: dict[str, bool], right_open: bool) -> None:
        self._overlay_ready = False
        for name in LAYOUT_DIRECTIONS:
            self._restore_to_layout(name)
            self._set_static_size(name, states.get(name, False))
            frame = self._frame(name)
            if frame is not None:
                frame.show()
        self._apply_static_right(right_open)
        self._activate_layouts()

    def _set_static_size(self, name: str, opened: bool) -> None:
        frame = self._frame(name)
        if frame is None:
            return
        minimum, maximum, axis = self._limits(name)
        value = maximum if opened else minimum
        if axis == "width":
            frame.setMinimumWidth(value)
            frame.setMaximumWidth(value)
        else:
            frame.setMinimumHeight(value)
            frame.setMaximumHeight(value)

    def _restore_to_layout(self, name: str) -> None:
        frame = self._frame(name)
        layout = self._owner_layout(name)
        if frame is None or layout is None:
            return
        if layout.indexOf(frame) >= 0:
            return
        index = self._indices.get(name, 0)
        index = max(0, min(index, layout.count()))
        layout.insertWidget(index, frame)
        frame.show()

    def attach_right(self, panel) -> None:
        """外观面板首次创建后按当前模式挂载（惰性创建时调用）。

        静态模式：收进右列堆栈，宽度保持收起态；浮层模式：保持为内容区的
        浮层子控件并隐藏，等首次 open 时滑入。
        """
        if self._mode == "static":
            self._apply_static_right(False)
            return
        if self._right_embedded:
            self._float_right(panel)
        panel.hide()

    def _apply_static_right(self, opened: bool) -> None:
        panel = self._panel()
        frame = self._frame("right")
        if panel is None or frame is None:
            return
        self._embed_right(panel)
        stack = self._right_stack()
        if stack is not None:
            stack.setCurrentWidget(panel)
        if opened:
            panel.show()
        value = int(AppSettings.right_column_size.maximum if opened else AppSettings.right_column_size.minimum)
        frame.setMinimumWidth(value)
        frame.setMaximumWidth(value)

    def _embed_right(self, panel) -> None:
        if self._right_embedded:
            return
        stack = self._right_stack()
        if stack is None:
            return
        panel.set_embedded(True)
        if panel.parentWidget() is not stack:
            stack.addWidget(panel)
        self.ui.settings_menu = panel
        self._right_embedded = True

    def _float_right(self, panel) -> None:
        stack = self._right_stack()
        if not self._right_embedded:
            # 面板可能由宿主提前嵌入右列（惰性创建发生在抽屉管理器之前）
            if stack is None or panel.parentWidget() is not stack:
                return
            self._right_embedded = True
        if stack is not None:
            stack.removeWidget(panel)
        content = getattr(self.ui, "content_area_frame", None)
        panel.setParent(content)
        panel.set_embedded(False)
        panel.hide()
        self._right_embedded = False

    # ------------------------------------------------------------------
    # Overlay：浮层覆盖
    # ------------------------------------------------------------------
    def _enter_overlay(self, states: dict[str, bool], right_open: bool) -> None:
        panel = self._panel()
        if panel is not None:
            self._float_right(panel)
        right_frame = self._frame("right")
        if right_frame is not None:
            minimum = int(AppSettings.right_column_size.minimum)
            right_frame.setMinimumWidth(minimum)
            right_frame.setMaximumWidth(minimum)

        for name in LAYOUT_DIRECTIONS:
            frame = self._frame(name)
            if frame is None:
                continue
            layout = self._owner_layout(name)
            if layout is not None:
                self._indices[name] = max(0, layout.indexOf(frame))
                layout.removeWidget(frame)
            frame.setParent(self.window.ui.window)
            self._set_overlay_size(name)
            self._set_overlay_flag(name, True)
            self._apply_shadow(name, frame)
            frame.raise_()

        self._install_tracker()
        self._overlay_ready = True
        # 抽屉脱离布局后内容区会立刻扩展；先激活布局，浮层几何才不会按旧位置计算
        self._activate_layouts()
        for name in LAYOUT_DIRECTIONS:
            if states.get(name):
                self.open(name, animate=False)
            else:
                self._overlay_open[name] = False
                frame = self._frame(name)
                if frame is not None:
                    frame.setGeometry(self._hidden_rect(name))
                    frame.hide()

        self._enter_overlay_right(right_open)

    def _leave_overlay(self) -> None:
        for name in LAYOUT_DIRECTIONS:
            self._stop_animation(name)
            self._overlay_open[name] = False
            frame = self._frame(name)
            if frame is None:
                continue
            self._clear_shadow(frame)
            self._set_overlay_flag(name, False)
            frame.hide()
            layout = self._owner_layout(name)
            if layout is not None and layout.indexOf(frame) < 0:
                index = self._indices.get(name, 0)
                index = max(0, index if index >= 0 else layout.count())
                layout.insertWidget(min(index, layout.count()), frame)

        tracker = self._tracker
        if tracker is not None:
            self.window.removeEventFilter(tracker)
            tracker.deleteLater()
            self._tracker = None
        self._overlay_ready = False

        panel = self._panel()
        if panel is not None:
            self._float_right(panel)

    def _enter_overlay_right(self, opened: bool) -> None:
        panel = self._panel()
        if panel is None:
            return
        if panel.is_open():
            panel.close()
        if opened:
            panel.open()
        else:
            panel.hide()

    # ------------------------------------------------------------------
    # 开合（Overlay）
    # ------------------------------------------------------------------
    def toggle(self, name: str) -> bool:
        """切换单个抽屉，返回切换后的展开状态（仅 Overlay 模式使用）。"""
        opened = not self.is_open(name)
        if opened:
            self.open(name)
        else:
            self.close(name)
        return opened

    def open(self, name: str, animate: bool = True) -> None:
        if name not in LAYOUT_DIRECTIONS:
            return
        frame = self._frame(name)
        if frame is None:
            return
        self._set_overlay_size(name)
        if not frame.isVisible():
            frame.setGeometry(self._hidden_rect(name))
        frame.show()
        frame.raise_()
        self._overlay_open[name] = True
        target = self._target_rect(name)
        if animate:
            self._animate(name, target)
        else:
            self._stop_animation(name)
            frame.setGeometry(target)

    def close(self, name: str, animate: bool = True) -> None:
        if name not in LAYOUT_DIRECTIONS:
            return
        frame = self._frame(name)
        if frame is None:
            return
        self._overlay_open[name] = False
        if not frame.isVisible():
            return
        if animate:
            self._animate(name, self._hidden_rect(name), frame.hide)
        else:
            self._stop_animation(name)
            frame.hide()

    def sync_overlay_geometry(self) -> None:
        """窗口尺寸变化时同步浮层抽屉的几何。"""
        if not self._overlay_ready:
            return
        for name in LAYOUT_DIRECTIONS:
            frame = self._frame(name)
            if frame is None:
                continue
            if self._overlay_open.get(name):
                target = self._target_rect(name)
            else:
                target = self._hidden_rect(name)
            if self._animations.get(name) is not None:
                continue
            frame.setGeometry(target)

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------
    def _content_rect(self) -> QRect:
        ui = self.ui
        content = getattr(ui, "content_area_frame", None) if ui is not None else None
        window = getattr(ui, "window", None) if ui is not None else None
        if content is None or window is None or content.width() <= 0 or content.height() <= 0:
            return QRect(self.window.rect()) if hasattr(self.window, "rect") else QRect()
        return QRect(content.mapTo(window, QPoint(0, 0)), content.size())

    def _target_rect(self, name: str) -> QRect:
        content = self._content_rect()
        _minimum, maximum, axis = self._limits(name)
        if axis == "width":
            return QRect(content.left(), content.top(), max(1, maximum), max(1, content.height()))
        if name == "top":
            return QRect(content.left(), content.top(), max(1, content.width()), max(1, maximum))
        return QRect(
            content.left(),
            content.bottom() - maximum + 1,
            max(1, content.width()),
            max(1, maximum),
        )

    def _hidden_rect(self, name: str) -> QRect:
        target = self._target_rect(name)
        if name == "left":
            return target.translated(-target.width(), 0)
        if name == "top":
            return target.translated(0, -target.height())
        return target.translated(0, target.height())

    def _set_overlay_size(self, name: str) -> None:
        frame = self._frame(name)
        if frame is None:
            return
        _minimum, maximum, axis = self._limits(name)
        if axis == "width":
            frame.setFixedWidth(maximum)
        else:
            frame.setFixedHeight(maximum)

    # ------------------------------------------------------------------
    # 动画与阴影
    # ------------------------------------------------------------------
    def _animate(self, name: str, end: QRect, finished=None) -> None:
        frame = self._frame(name)
        if frame is None:
            return
        self._stop_animation(name)
        duration = self._duration()
        if duration <= 0:
            frame.setGeometry(end)
            if callable(finished):
                finished()
            return
        animation = QPropertyAnimation(frame, b"geometry", frame)
        animation.setDuration(duration)
        animation.setStartValue(frame.geometry())
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        if callable(finished):
            animation.finished.connect(finished)
        animation.finished.connect(lambda: self._forget_animation(name))
        self._animations[name] = animation
        animation.start()

    def _stop_animation(self, name: str) -> None:
        animation = self._animations.pop(name, None)
        if animation is not None:
            animation.stop()
            animation.deleteLater()

    def _forget_animation(self, name: str) -> None:
        animation = self._animations.get(name)
        if animation is not None and animation.state() != QPropertyAnimation.State.Running:
            self._animations.pop(name, None)

    def _duration(self) -> int:
        try:
            return int(AppSettings.overlay.drawer_duration)
        except Exception:
            return 200

    def _apply_shadow(self, name: str, frame) -> None:
        effect = QGraphicsDropShadowEffect(frame)
        effect.setBlurRadius(28)
        shadow_color = QColor(ColorPalette.custom_black)
        shadow_color.setAlpha(90)
        effect.setColor(shadow_color)
        effect.setXOffset(8 if name == "left" else 0)
        effect.setYOffset(8 if name == "top" else (-8 if name == "bottom" else 0))
        frame.setGraphicsEffect(effect)

    def _set_overlay_flag(self, name: str, enabled: bool) -> None:
        """给抽屉框打/去 ``overlay`` 动态属性，切换到浮层玻璃表面。

        与浮层左菜单同一套做法：只改动态属性并由全局样式表的属性选择器接管
        颜色，切换模式时只重刷该控件，不重建样式表。
        """
        frame = self._frame(name)
        if frame is None:
            return
        value = "true" if enabled else None
        if frame.property("overlay") == value:
            return
        frame.setProperty("overlay", value)
        style = frame.style()
        style.unpolish(frame)
        style.polish(frame)
        frame.update()

    @staticmethod
    def _clear_shadow(frame) -> None:
        if frame.graphicsEffect() is not None:
            frame.setGraphicsEffect(None)

    # ------------------------------------------------------------------
    # 组件查找
    # ------------------------------------------------------------------
    def _frame(self, name: str):
        ui = self.ui
        if ui is None:
            return None
        attribute = {
            "left": "left_column_frame",
            "right": "right_column_frame",
            "top": "top_column_frame",
            "bottom": "bottom_column_frame",
        }.get(name)
        return getattr(ui, attribute, None) if attribute else None

    def _panel(self):
        ui = self.ui
        return getattr(ui, "settings_drawer", None) if ui is not None else None

    def _right_stack(self):
        ui = self.ui
        column = getattr(ui, "right_column", None) if ui is not None else None
        return getattr(column, "menus", None) if column is not None else None

    def _owner_layout(self, name: str):
        ui = self.ui
        if ui is None:
            return None
        if name == "left":
            return getattr(getattr(ui, "window", None), "layout", None)
        if name in ("top", "bottom"):
            return getattr(ui, "right_app_layout", None)
        return None

    def _limits(self, name: str) -> tuple[int, int, str]:
        """返回 (收起尺寸, 展开尺寸, 主轴)。"""
        if name == "left":
            size = AppSettings.left_column_size
            return int(size.minimum), int(size.maximum), "width"
        if name == "right":
            size = AppSettings.right_column_size
            return int(size.minimum), int(size.maximum), "width"
        if name == "top":
            size = AppSettings.top_column_size
            return int(size.minimum), int(size.maximum), "height"
        size = AppSettings.bottom_column_size
        return int(size.minimum), int(size.maximum), "height"

    def _install_tracker(self) -> None:
        if self._tracker is not None or not isinstance(self.window, QObject):
            return
        self._tracker = _DrawerResizeTracker(self)
        self.window.installEventFilter(self._tracker)

    def _activate_layouts(self) -> None:
        """立即生效容器变更，避免浮层按切换前的旧几何定位。"""
        ui = self.ui
        if ui is None:
            return
        layouts = (
            getattr(getattr(ui, "window", None), "layout", None),
            getattr(ui, "right_app_layout", None),
            getattr(ui, "content_area_layout", None),
        )
        for layout in layouts:
            activate = getattr(layout, "activate", None)
            if callable(activate):
                activate()


__all__ = ["DRAWER_MODES", "DrawerLayout", "normalize_drawer_mode"]
