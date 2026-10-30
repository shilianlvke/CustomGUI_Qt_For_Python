"""遮罩浮层基类：全窗口遮罩、卡片居中/贴边、进出动画、ESC 与点外关闭。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog

from .card import COverlayCard


def overlay_settings() -> tuple[int, int, int]:
    """(对话框动画, 抽屉动画, 遮罩透明度)。"""
    try:
        from AppCore import AppSettings

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
        self._card = COverlayCard(self)

        self._fade: QPropertyAnimation | None = None
        self._slide: QPropertyAnimation | None = None
        self._build_card()

    # ------------------------------------------------------------------
    # 子类实现
    # ------------------------------------------------------------------
    def _build_card(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _layout_card(self) -> QRect:  # pragma: no cover - 子类实现
        return QRect(0, 0, self.width(), self.height())

    # ------------------------------------------------------------------
    # 展示与关闭
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        """以父窗口为范围铺满遮罩并淡入。"""
        parent = self.parentWidget()
        if parent is not None:
            origin = parent.mapToGlobal(QPoint(0, 0))
            self.setGeometry(origin.x(), origin.y(), parent.width(), parent.height())
        self._layout_card()
        self.setWindowOpacity(0.0)
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
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._mask_alpha))

        rect = QRectF(self._card.geometry())
        for offset, alpha in ((14, 10), (7, 18), (3, 28)):
            painter.fillRect(rect.translated(0, offset).adjusted(6, 0, -6, 0), QColor(0, 0, 0, alpha))
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
