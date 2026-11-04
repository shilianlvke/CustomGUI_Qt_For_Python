"""图片展示（复刻 PrimeVue Image，附带点击放大的预览遮罩）。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from customgui.appcore import AppSettings, ColorPalette

from ..display.palette import tokens
from ..icon_utils import render_icon

#: 圆角半径（几何量，与主题无关）
_RADIUS = 8
#: 预览遮罩的透明度
_MASK_ALPHA = 210
#: 底部说明文字占用的高度
_CAPTION_HEIGHT = 28


def _image_config() -> tuple[int, int, int]:
    """(圆角, 遮罩透明度, 说明文字高度)，配置缺失时回落默认值。"""
    try:
        cfg = AppSettings.media
        return int(cfg.radius), int(cfg.image_mask_alpha), int(cfg.image_caption_height)
    except Exception:
        return _RADIUS, _MASK_ALPHA, _CAPTION_HEIGHT


def _as_pixmap(source: str | QPixmap | None) -> QPixmap:
    """把路径 / QPixmap 统一成 ``QPixmap``（空值为空图）。"""
    if isinstance(source, QPixmap):
        return QPixmap(source)
    if isinstance(source, str) and source:
        return QPixmap(source)
    return QPixmap()


class _PreviewButton(QAbstractButton):
    """预览工具栏的圆形小按钮（放大 / 重置 / 关闭）。"""

    def __init__(self, kind: str, tooltip: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 预览遮罩恒为暗色，工具按钮固定使用高对比浅色前景；跟随主题正文色
        # 时，浅色主题的深色图标会淹没在遮罩里几乎看不见。常态再垫一层淡
        # 白色底片，保证压在深色图片上也始终可辨认。
        fill = QColor(255, 255, 255, 60 if self._hover else 28)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))

        pen = QPen(QColor(ColorPalette.custom_white), 1.8, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        if self._kind == "zoom":
            painter.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
            painter.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 6))
        elif self._kind == "reset":
            painter.drawArc(QRectF(cx - 7, cy - 7, 14, 14), 40 * 16, 280 * 16)
            painter.drawLine(QPointF(cx + 3, cy - 8), QPointF(cx + 7, cy - 5))
            painter.drawLine(QPointF(cx + 7, cy - 5), QPointF(cx + 3, cy - 1))
        else:
            painter.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
            painter.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx - 5, cy + 5))
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()


class _ImagePreview(QWidget):
    """覆盖在窗口上的图片预览遮罩，带缩放工具栏。"""

    closed = Signal()

    def __init__(self, parent: QWidget, pixmap: QPixmap, caption: str = "", zoom: bool = True):
        super().__init__(parent)
        _, self._mask_alpha, _ = _image_config()
        self._pixmap = pixmap
        self._caption = caption
        self._scale = 1.0
        self._zoom_enabled = bool(zoom)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setGeometry(parent.rect())
        parent.installEventFilter(self)

        self._zoom_button = _PreviewButton("zoom", "放大", self)
        self._reset_button = _PreviewButton("reset", "重置", self)
        self._close_button = _PreviewButton("close", "关闭", self)
        self._zoom_button.clicked.connect(lambda: self._set_scale(self._scale + 0.25))
        self._reset_button.clicked.connect(lambda: self._set_scale(1.0))
        self._close_button.clicked.connect(self.close_preview)
        self._zoom_button.setEnabled(self._zoom_enabled)
        self._reset_button.setEnabled(self._zoom_enabled)
        self.hide()

    # ------------------------------------------------------------------
    # 展示
    # ------------------------------------------------------------------
    def open_preview(self) -> None:
        self.setGeometry(self.parentWidget().rect())
        self._place_buttons()
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)

    def close_preview(self) -> None:
        self.hide()

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        self.update()

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._scale = 1.0
        self.update()

    def set_zoom_enabled(self, enabled: bool) -> None:
        self._zoom_enabled = bool(enabled)
        self._zoom_button.setEnabled(self._zoom_enabled)
        self._reset_button.setEnabled(self._zoom_enabled)
        if not self._zoom_enabled:
            self._set_scale(1.0)

    def scale(self) -> float:
        return self._scale

    def buttons(self) -> tuple[_PreviewButton, _PreviewButton, _PreviewButton]:
        return self._zoom_button, self._reset_button, self._close_button

    # ------------------------------------------------------------------
    # 几何与绘制
    # ------------------------------------------------------------------
    def _set_scale(self, value: float) -> None:
        self._scale = max(0.25, min(4.0, float(value)))
        self.update()

    def _image_rect(self) -> QRectF:
        area = QRectF(self.rect()).adjusted(56, 40, -56, -56)
        if self._pixmap.isNull() or area.width() <= 1 or area.height() <= 1:
            return QRectF()
        size = self._pixmap.size()
        size.scale(area.size().toSize(), Qt.KeepAspectRatio)
        width = size.width() * self._scale
        height = size.height() * self._scale
        return QRectF(
            area.center().x() - width / 2,
            area.center().y() - height / 2,
            width,
            height,
        )

    def _place_buttons(self) -> None:
        margin = 16
        x = self.width() - margin - 3 * 30 - 2 * 6
        for button in (self._zoom_button, self._reset_button, self._close_button):
            button.move(x, margin)
            x += 30 + 6

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._place_buttons()

    def eventFilter(self, watched, event):  # noqa: N802 - 覆写 Qt 命名
        if watched is self.parentWidget() and event.type() in (QEvent.Resize, QEvent.Show):
            self.setGeometry(self.parentWidget().rect())
            self._place_buttons()
            if self.isVisible():
                self.raise_()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        mask = QColor(ColorPalette.custom_dark_one)
        mask.setAlpha(self._mask_alpha)
        painter.fillRect(self.rect(), mask)

        target = self._image_rect()
        if not target.isEmpty():
            painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
            painter.setPen(QPen(QColor(ColorPalette.custom_white), 1))
            painter.drawRect(target.adjusted(0.5, 0.5, -0.5, -0.5))

        if self._caption:
            font = QFont(self.font())
            font.setPixelSize(14)
            painter.setFont(font)
            painter.setPen(QColor(ColorPalette.custom_white))
            painter.drawText(
                QRectF(24, self.height() - 42, self.width() - 48, 26),
                Qt.AlignCenter,
                self._caption,
            )
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            image_rect = self._image_rect()
            toolbar_rect = QRectF(16, 16, self.width() - 32, 30)
            if not image_rect.contains(event.position()) and not toolbar_rect.contains(event.position()):
                self.close_preview()
                event.accept()
                return
        super().mousePressEvent(event)

    def wheelEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self._zoom_enabled:
            return
        step = 0.15 if event.angleDelta().y() > 0 else -0.15
        self._set_scale(self._scale + step)
        event.accept()

    def hideEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().hideEvent(event)
        self.closed.emit()

    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.key() == Qt.Key_Escape:
            self.close_preview()
            event.accept()
            return
        super().keyPressEvent(event)


class CImage(QWidget):
    """图片展示控件：无图占位、点击预览、缩放工具栏与说明文字。"""

    clicked = Signal()
    previewOpened = Signal()
    previewClosed = Signal()

    def __init__(
        self,
        image: str | QPixmap | None = None,
        caption: str = "",
        preview: bool = True,
        zoom: bool = True,
        placeholder: str = "No Image",
        parent=None,
    ):
        super().__init__(parent)
        self._radius, _, self._caption_height = _image_config()
        self._pixmap = _as_pixmap(image)
        self._caption = caption
        self._preview_enabled = bool(preview)
        self._zoom_enabled = bool(zoom)
        self._placeholder = placeholder
        self._preview: _ImagePreview | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(48, 48)
        self.setCursor(Qt.PointingHandCursor if self._preview_enabled else Qt.ArrowCursor)

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def image(self) -> QPixmap:
        return QPixmap(self._pixmap)

    def caption(self) -> str:
        return self._caption

    def set_image(self, source: str | QPixmap | None) -> None:
        self._pixmap = _as_pixmap(source)
        if self._preview is not None:
            self._preview.set_pixmap(self._pixmap)
        self.update()

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        if self._preview is not None:
            self._preview.set_caption(caption)
        self.update()

    def set_preview(self, enabled: bool) -> None:
        self._preview_enabled = bool(enabled)
        self.setCursor(Qt.PointingHandCursor if self._preview_enabled else Qt.ArrowCursor)
        if not self._preview_enabled:
            self.close_preview()

    def preview_enabled(self) -> bool:
        return self._preview_enabled

    def set_zoom(self, enabled: bool) -> None:
        self._zoom_enabled = bool(enabled)
        if self._preview is not None:
            self._preview.set_zoom_enabled(self._zoom_enabled)

    def zoom_enabled(self) -> bool:
        return self._zoom_enabled

    # ------------------------------------------------------------------
    # 预览
    # ------------------------------------------------------------------
    def _ensure_preview(self) -> _ImagePreview:
        if self._preview is None:
            self._preview = _ImagePreview(self.window(), self._pixmap, self._caption, self._zoom_enabled)
            self._preview.closed.connect(self.previewClosed.emit)
        return self._preview

    def preview_widget(self) -> _ImagePreview:
        return self._ensure_preview()

    def open_preview(self) -> None:
        if self._pixmap.isNull():
            return
        preview = self._ensure_preview()
        preview.set_zoom_enabled(self._zoom_enabled)
        preview.set_pixmap(self._pixmap)
        preview.set_caption(self._caption)
        preview.open_preview()
        self.previewOpened.emit()

    def close_preview(self) -> None:
        if self._preview is not None:
            self._preview.close_preview()

    def is_preview_open(self) -> bool:
        return self._preview is not None and self._preview.isVisible()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _content_rect(self) -> QRectF:
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._caption:
            rect.setBottom(rect.bottom() - self._caption_height)
        return rect

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        palette = tokens()
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(body, self._radius, self._radius)
        painter.fillPath(path, QColor(palette["surface"]))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)

        content = self._content_rect()
        if content.width() > 1 and content.height() > 1:
            if not self._pixmap.isNull():
                scaled = self._pixmap.scaled(
                    content.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = content.left() + (content.width() - scaled.width()) / 2
                y = content.top() + (content.height() - scaled.height()) / 2
                painter.drawPixmap(int(x), int(y), scaled)
            else:
                self._paint_placeholder(painter, content, palette)

        if self._caption:
            font = QFont(self.font())
            font.setPixelSize(13)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            text = metrics.elidedText(self._caption, Qt.ElideRight, int(body.width()) - 24)
            painter.setPen(QColor(palette["muted"]))
            painter.drawText(
                QRectF(body.left() + 12, body.bottom() - self._caption_height, body.width() - 24, self._caption_height),
                Qt.AlignCenter,
                text,
            )
        painter.end()

    def _paint_placeholder(self, painter: QPainter, content: QRectF, palette: dict[str, str]) -> None:
        icon = render_icon("icon_pic_not_found", QColor(palette["muted"]), 36, self.devicePixelRatioF())
        if icon is not None:
            logical = icon.deviceIndependentSize()
            painter.drawPixmap(
                int(content.center().x() - logical.width() / 2),
                int(content.center().y() - logical.height() / 2 - 8),
                icon,
            )
        font = QFont(self.font())
        font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(QColor(palette["muted"]))
        painter.drawText(
            QRectF(content.left(), content.center().y() + 22, content.width(), 24),
            Qt.AlignCenter,
            self._placeholder,
        )

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            if self._preview_enabled:
                self.open_preview()
            event.accept()
            return
        super().mouseReleaseEvent(event)


__all__ = ["CImage"]
