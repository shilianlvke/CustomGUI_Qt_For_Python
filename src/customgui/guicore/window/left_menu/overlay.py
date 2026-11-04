"""左菜单 Overlay 模式的浮层基础设施。

Overlay 与 Static 的差别只在**容器与交互**：

- Static：菜单框是窗口水平布局的成员，展开时挤压内容区；
- Overlay：布局里只保留一条与收起态等宽的“轨道占位”，菜单框浮动在内容区
  之上；展开时覆盖内容、收起时回到轨道，内容区宽度始终不变。

为了让浮层看起来像“一层临时的面板”而不是贴在页面上的色块，这里补充三件
基础设施：内容遮罩（点击/滚轮关闭并拦截穿透）、窗口尺寸跟随器、几何计算。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QRect, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from customgui.appcore import AppSettings

from ...custom_ui.display.palette import is_dark_theme

#: 遮罩最深的不透明度（0-255）：深色主题压得更重，浅色主题保持轻盈。
#: 保留为配置不可用时的兜底默认，运行时以 :attr:`AppSettings.menu_overlay` 为准。
SCRIM_ALPHA_DARK = 80
SCRIM_ALPHA_LIGHT = 52
#: 遮罩淡入淡出时长（毫秒）；同上，运行时以配置为准
SCRIM_DURATION = 160


def _scrim_settings() -> tuple[int, int, int]:
    """(深色遮罩透明度, 浅色遮罩透明度, 动画时长)，配置缺失时回落到常量。"""
    try:
        cfg = AppSettings.menu_overlay
        return int(cfg.scrim_alpha_dark), int(cfg.scrim_alpha_light), int(cfg.duration)
    except Exception:
        return SCRIM_ALPHA_DARK, SCRIM_ALPHA_LIGHT, SCRIM_DURATION


def menu_rail_width() -> int:
    """收起态的菜单轨道宽度（菜单最小宽度 + 两侧内容边距）。"""
    margin = int(AppSettings.left_menu_content_margins)
    return max(1, int(AppSettings.lef_menu_size.minimum) + margin * 2)


def menu_panel_width() -> int:
    """展开态的菜单浮层宽度。"""
    margin = int(AppSettings.left_menu_content_margins)
    return max(menu_rail_width(), int(AppSettings.lef_menu_size.maximum) + margin * 2)


def overlay_menu_rect(window, width: int | None = None) -> QRect:
    """浮动菜单的几何：贴窗口左上，高度随窗口伸缩。"""
    ui = window.ui
    frame = ui.left_menu_frame
    margins = ui.window.layout.contentsMargins()
    width = frame.width() if width is None else width
    return QRect(
        margins.left(),
        margins.top(),
        max(1, int(width)),
        max(1, window.height() - margins.top() - margins.bottom()),
    )


def overlay_scrim_rect(window) -> QRect:
    """遮罩几何：只覆盖内容区，标题栏、版权栏与左列不被挡住。"""
    ui = window.ui
    content = getattr(ui, "content_area_frame", None)
    if content is None:
        return QRect()
    origin = content.mapTo(ui.window, QPoint(0, 0))
    return QRect(origin, content.size())


class CMenuOverlayScrim(QWidget):
    """浮层菜单展开时的内容遮罩：点击、滚轮都会关闭菜单并拦住穿透。"""

    dismissed = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("CMenuOverlayScrim")
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.NoFocus)
        self._alpha = 0
        # 遮罩参数来自 settings（构造时读取，避免导入期触发配置加载）
        self._scrim_alpha_dark, self._scrim_alpha_light, duration = _scrim_settings()
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_alpha)
        self._animation.finished.connect(self._on_finished)
        self.hide()

    # ------------------------------------------------------------------
    # 显隐
    # ------------------------------------------------------------------
    def fade_in(self) -> None:
        self.show()
        self.raise_()
        self._animate(self._scrim_alpha_dark if is_dark_theme() else self._scrim_alpha_light)

    def fade_out(self) -> None:
        if not self.isVisible():
            return
        self._animate(0)

    def alpha(self) -> int:
        return self._alpha

    def _animate(self, target: int) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._alpha)
        self._animation.setEndValue(int(target))
        self._animation.start()

    def _on_alpha(self, value) -> None:
        self._alpha = int(value)
        self.update()

    def _on_finished(self) -> None:
        if self._alpha <= 0:
            self.hide()

    # ------------------------------------------------------------------
    # 绘制与输入拦截
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._alpha <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(QRectF(self.rect()), QColor(0, 0, 0, self._alpha))
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802
        event.accept()
        self.dismissed.emit()

    def mouseReleaseEvent(self, event):  # noqa: N802
        event.accept()

    def wheelEvent(self, event):  # noqa: N802
        event.accept()


class CLeftMenuOverlayTracker(QObject):
    """窗口缩放时同步浮动菜单与遮罩的几何。"""

    def __init__(self, window):
        super().__init__(window)
        self._window = window

    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if obj is self._window and event.type() == QEvent.Type.Resize:
            self.sync()
        return False

    def sync(self) -> None:
        window = self._window
        frame = window.ui.left_menu_frame
        frame.setGeometry(overlay_menu_rect(window, frame.width()))
        scrim = getattr(window, "_menu_overlay_scrim", None)
        if scrim is not None:
            scrim.setGeometry(overlay_scrim_rect(window))


__all__ = [
    "CMenuOverlayScrim",
    "CLeftMenuOverlayTracker",
    "overlay_menu_rect",
    "overlay_scrim_rect",
    "menu_rail_width",
    "menu_panel_width",
    "SCRIM_ALPHA_DARK",
    "SCRIM_ALPHA_LIGHT",
]
