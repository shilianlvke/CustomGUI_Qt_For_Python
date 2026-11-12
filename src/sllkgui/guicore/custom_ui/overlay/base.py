"""遮罩浮层基类：全窗口遮罩、卡片居中/贴边、进出动画、ESC 与点外关闭。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog

from sllkgui.appcore import ColorPalette

from .card import COverlayCard


def overlay_settings() -> tuple[int, int, int]:
    """(对话框动画, 抽屉动画, 遮罩透明度)。"""
    try:
        from sllkgui.appcore import AppSettings

        cfg = AppSettings.overlay
        return int(cfg.dialog_duration), int(cfg.drawer_duration), int(cfg.mask_alpha)
    except Exception:
        return 160, 200, 120


class _OverlayBase(QDialog):
    """全窗口遮罩 + 内容卡片的基类。"""

    opened = Signal()
    closed = Signal()
    accepted = Signal()
    rejected = Signal()

    #: 打开时是否让整个浮层窗口淡入（抽屉只滑入卡片，遮罩保持常亮）
    _fade_on_open = True

    def __init__(
        self,
        parent=None,
        modal: bool = True,
        closable: bool = True,
        dismissable_mask: bool = True,
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(modal)
        self.setFocusPolicy(Qt.StrongFocus)

        _, _, self._mask_alpha = overlay_settings()
        self._closable = closable
        self._dismissable = dismissable_mask
        self._closing = False
        self._follow_pending = False
        self._card = COverlayCard(self)

        self._fade: QPropertyAnimation | None = None
        self._slide: QPropertyAnimation | None = None
        self._build_card()

        # 父窗口移动/缩放（最大化、还原、拖边框）时重新贴靠：浮层是独立顶层
        # 窗口，Qt 不会带着它一起动，否则会停在旧位置、露出半截。
        parent_widget = self.parentWidget()
        if parent_widget is not None:
            parent_widget.installEventFilter(self)

    # ------------------------------------------------------------------
    # 子类实现
    # ------------------------------------------------------------------
    def _build_card(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _layout_card(self) -> QRect:  # pragma: no cover - 子类实现
        return QRect(0, 0, self.width(), self.height())

    def _target_geometry(self) -> QRect:
        """浮层窗口应占据的屏幕矩形；默认铺满父窗口。

        抽屉会覆盖此方法，把范围收窄到内容区，避免遮住左侧菜单、标题栏与版权栏。
        """
        parent = self.parentWidget()
        if parent is None:
            return QRect()
        origin = parent.mapToGlobal(QPoint(0, 0))
        return QRect(origin.x(), origin.y(), parent.width(), parent.height())

    # ------------------------------------------------------------------
    # 跟随父窗口
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if obj is self.parentWidget() and event.type() in (QEvent.Resize, QEvent.Move):
            self._schedule_follow()
        return super().eventFilter(obj, event)

    def _schedule_follow(self) -> None:
        """父窗口几何变化后，延到本轮事件末尾再贴靠。

        父窗口的 Resize 早于它内部控件（内容区）完成布局，此刻读到的锚点尺寸
        还是旧的；等一轮事件循环再算，才拿得到布局后的真实几何。
        """
        if self._follow_pending or not self.isVisible() or self._closing:
            return
        self._follow_pending = True
        QTimer.singleShot(0, self._follow_parent)

    def _follow_parent(self) -> None:
        """按父窗口的新几何重新铺开浮层（关闭中/未显示时跳过）。"""
        self._follow_pending = False
        if not self.isVisible() or self._closing:
            return
        geometry = self._target_geometry()
        if geometry.isNull() or geometry == self.geometry():
            return
        self.setGeometry(geometry)
        self._layout_card()
        self.update()

    # ------------------------------------------------------------------
    # 展示与关闭
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        """按 :meth:`_target_geometry` 定位并铺开遮罩。"""
        geometry = self._target_geometry()
        if not geometry.isNull():
            self.setGeometry(geometry)
        self._layout_card()
        self.setWindowOpacity(0.0 if self._fade_on_open else 1.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)
        self._animate_in()
        self.opened.emit()

    def close_dialog(self) -> None:
        if self._closing or not self.isVisible():
            return
        self._closing = True
        self._animate_out()

    def accept(self) -> None:
        self.accepted.emit()
        self.close_dialog()

    def reject(self) -> None:
        self.rejected.emit()
        self.close_dialog()

    def exec_dialog(self) -> bool:
        """阻塞式运行，返回是否点了确认。"""
        from PySide6.QtCore import QEventLoop

        loop = QEventLoop()
        result = {"accepted": False}

        def finish(ok: bool) -> None:
            result["accepted"] = ok
            loop.quit()

        self.accepted.connect(lambda: finish(True))
        self.rejected.connect(lambda: finish(False))
        self.closed.connect(lambda: finish(False))
        self.open_dialog()
        loop.exec()
        return result["accepted"]

    # ------------------------------------------------------------------
    # 动画
    # ------------------------------------------------------------------
    def _animate_in(self) -> None:
        duration, _, _ = overlay_settings()
        if duration <= 0:
            self.setWindowOpacity(1.0)
            return
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(duration)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.start()
        self._fade = fade

    def _finalize(self) -> None:
        self.hide()
        self.setWindowOpacity(1.0)
        self._closing = False
        self.closed.emit()
        if self.testAttribute(Qt.WA_DeleteOnClose):
            self.deleteLater()

    def _animate_out(self) -> None:
        duration, _, _ = overlay_settings()

        def finish() -> None:
            self._finalize()

        if duration <= 0 or not self.isVisible():
            finish()
            return
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(duration)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.finished.connect(finish)
        fade.start()
        self._fade = fade

    # ------------------------------------------------------------------
    # 布局与绘制
    # ------------------------------------------------------------------
    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._layout_card()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        # 透明窗口没有背景擦除：局部重绘时旧遮罩留在后备存储里，再叠一层就会
        # 变深，表现为卡片边缘一串越来越密的竖线（滑入/缩放时最明显）。
        # 先把本次脏区清成透明，再画遮罩与投影。
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.Antialiasing)
        mask = QColor(ColorPalette.custom_black)
        mask.setAlpha(self._mask_alpha)
        painter.fillRect(self.rect(), mask)

        rect = QRectF(self._card.geometry())
        for offset, alpha in ((14, 10), (7, 18), (3, 28)):
            shadow = QColor(ColorPalette.custom_black)
            shadow.setAlpha(alpha)
            painter.fillRect(rect.translated(0, offset).adjusted(6, 0, -6, 0), shadow)
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._dismissable and not self._card.geometry().contains(event.position().toPoint()):
            self.reject()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.key() == Qt.Key_Escape and self._closable:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self.closed.emit()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # 供子类使用
    # ------------------------------------------------------------------
    def card(self) -> COverlayCard:
        return self._card

    def move_card(self, position: QPoint) -> None:
        """拖动卡片，限制在遮罩范围内。"""
        x = max(0, min(position.x(), self.width() - self._card.width()))
        y = max(0, min(position.y(), self.height() - self._card.height()))
        self._card.move(x, y)
        self.update()


__all__ = ["_OverlayBase", "overlay_settings"]
