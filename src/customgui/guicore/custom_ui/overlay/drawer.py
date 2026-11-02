"""抽屉：贴住内容区四边滑入，样式与交互对齐左列「软件信息」抽屉。

参考范例是主窗口的左侧抽屉（``CLeftColumn``）：47px 头部 + 圆角标题胶囊 +
30×30 图标位 + 30×30 关闭按钮 + 可滚动内容区。四个方向共用同一套头部与
内容结构，只有停靠边与滑入方向不同。

与旧实现的差别：

* **不再铺满整个父窗口**：范围收窄到内容区（``anchor``），左侧菜单栏、
  顶部标题栏、底部版权栏保持可见可点，四向抽屉都不会压住它们；
* 头部、内容区按 ``CLeftColumn`` 的结构与样式表对象名构建，主题切换自动跟随；
* 仅卡片滑入（遮罩不淡入），滑入方向由停靠边决定，阴影落在朝向内容的一侧。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from customgui.appcore import AppSettings, Language, get_design_tokens, get_theme_manager

from ..close_button import CCloseButton
from ..display.palette import tokens
from ..icon_utils import render_icon
from .base import _OverlayBase, overlay_settings

_POSITIONS = ("left", "right", "top", "bottom")
_GRIP_BAND = 6  # 边缘拖拽热区宽度（像素）
_MIN_DRAWER = 200  # 与构造参数的最小尺寸一致
_DRAWER_MARGIN = 80  # 拖宽后至少给窗口留出的空间

#: 头部尺寸与左列抽屉保持一致（CLeftColumn：47px 标题条 + 30px 控件位）
_HEADER_HEIGHT = 47
_CONTROL_BOX = 30
_HEADER_PADDING = 5
_ICON_SIZE = 18


class _EdgeGrip(QWidget):
    """抽屉边缘的隐形拖拽条：悬停显示主色细线，拖动改变抽屉尺寸。"""

    def __init__(self, drawer: CDrawer):
        super().__init__(drawer.card())
        self._drawer = drawer
        self._press_global: QPoint | None = None
        self._start_size = 0
        self._vertical = drawer._position in ("left", "right")
        self.setCursor(Qt.SizeHorCursor if self._vertical else Qt.SizeVerCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if not self.underMouse():
            return
        painter = QPainter(self)
        color = QColor(tokens()["accent"])
        if self._vertical:
            painter.fillRect(self.width() // 2 - 1, 0, 2, self.height(), color)
        else:
            painter.fillRect(0, self.height() // 2 - 1, self.width(), 2, color)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            # 拖动优先：停掉进行中的滑入动画
            slide = getattr(self._drawer, "_slide", None)
            if slide is not None and slide.state() == QPropertyAnimation.State.Running:
                slide.stop()
                self._drawer._sliding = False
                self._drawer._layout_card()
            self._press_global = event.globalPosition().toPoint()
            self._start_size = self._drawer._size
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._press_global is None:
            return
        delta = event.globalPosition().toPoint() - self._press_global
        self._drawer._resize_from_grip(self._start_size, delta)
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._press_global = None
        event.accept()


class CDrawer(_OverlayBase):
    """侧边抽屉：左/右/上/下四个方向滑入。

    ``anchor`` 为抽屉的活动范围；默认取主窗口的内容区
    （``ui.content_area_frame``），因此左侧菜单、标题栏、版权栏不会被遮挡。
    传入 ``None`` 之外的任意 QWidget 可把抽屉限制在指定区域。
    """

    #: 只滑卡片，不做整窗淡入（遮罩常亮，避免与滑入动画叠在一起）
    _fade_on_open = False

    def __init__(
        self,
        title: str = "",
        position: str = "right",
        size: int = 320,
        closable: bool = True,
        dismissable_mask: bool = True,
        parent=None,
        *,
        anchor: QWidget | None = None,
        icon: str | None = "icon_setting",
        resizable: bool = True,
        modal: bool = False,
    ):
        self._title_key = title
        self._position = position if position in _POSITIONS else "right"
        self._size = max(_MIN_DRAWER, int(size))
        self._anchor = anchor
        self._icon_name = icon
        self._resizable = resizable
        self._target_rect = QRect()
        self._sliding = False
        super().__init__(parent, modal=modal, closable=closable, dismissable_mask=dismissable_mask)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build_card(self) -> None:
        card = self.card()
        card.setRadius(0)
        card.setObjectName("CDrawer_Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header: QWidget | None = None
        self.title_label: QLabel | None = None
        self._close_button: CCloseButton | None = None

        if self._title_key or self._closable:
            layout.addWidget(self._build_header(card))

        self.content_frame = QFrame(card)
        self.content_frame.setObjectName("CLeftColumnContent_Frame")
        frame_layout = QVBoxLayout(self.content_frame)
        frame_layout.setContentsMargins(_HEADER_PADDING, _HEADER_PADDING, _HEADER_PADDING, _HEADER_PADDING)
        frame_layout.setSpacing(0)

        self._scroll = QScrollArea(self.content_frame)
        self._scroll.setObjectName("CDrawer_Scroll")
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 只给滚动区本身去底色：裸规则会级联到抽屉里的按钮，覆盖其填充色
        self._scroll.setStyleSheet("QScrollArea#CDrawer_Scroll { background: transparent; border: none; }")
        self._scroll.viewport().setAutoFillBackground(False)

        body = QWidget()
        body.setObjectName("CDrawer_Body")
        body.setStyleSheet("QWidget#CDrawer_Body { background: transparent; }")
        self.content_layout = QVBoxLayout(body)
        self.content_layout.setContentsMargins(14, 6, 14, 16)
        self.content_layout.setSpacing(10)
        # 末尾留一条弹性空间：内容不足一屏时控件贴顶，而不是被均分撑开
        self._stretch = self.content_layout.addStretch(1)
        self._scroll.setWidget(body)
        frame_layout.addWidget(self._scroll)

        layout.addWidget(self.content_frame, 1)

        self._grip = _EdgeGrip(self)
        self._grip.setVisible(self._resizable)

        get_theme_manager().subscribe(self._on_theme_changed)

    def _build_header(self, card: QWidget) -> QWidget:
        """47px 头部：圆角胶囊 + 图标位 + 标题 + 关闭按钮（与左列抽屉同构）。"""
        header = QWidget(card)
        header.setObjectName("CDrawerHeader_Widget")
        header.setFixedHeight(_HEADER_HEIGHT)

        outer = QVBoxLayout(header)
        outer.setContentsMargins(_HEADER_PADDING, 3, _HEADER_PADDING, 3)
        outer.setSpacing(0)

        pill = QFrame(header)
        pill.setObjectName("CLeftColumnTitle_Frame")
        radius = get_design_tokens().radius.window
        pill.setStyleSheet(f"#CLeftColumnTitle_Frame {{ border-radius: {radius}px; }}")
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(_HEADER_PADDING, _HEADER_PADDING, _HEADER_PADDING, _HEADER_PADDING)
        pill_layout.setSpacing(3)

        icon_frame = QFrame(pill)
        icon_frame.setObjectName("CLeftColumnIcon_Frame")
        icon_frame.setFixedSize(_CONTROL_BOX, _CONTROL_BOX)
        self._icon_label = QLabel(icon_frame)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setFixedSize(_CONTROL_BOX, _CONTROL_BOX)

        tokens_ = get_design_tokens()
        self.title_label = QLabel(Language.resolve_key(self._title_key), pill)
        self.title_label.setObjectName("CLeftColumnTitle_Label")
        self.title_label.setStyleSheet(
            f"#CLeftColumnTitle_Label {{"
            f" padding-bottom: {tokens_.spacing.label_padding_bottom}px;"
            f' font: {tokens_.typography.weight_label} {tokens_.typography.size_label}pt "{AppSettings.family}"; }}'
        )

        if self._closable:
            self._close_button = CCloseButton(QColor(tokens()["muted"]), size=_CONTROL_BOX, radius=6, parent=pill)
            self._close_button.setObjectName("btn_close_drawer")
            self._close_button.setToolTip(Language.resolve_key("language.UI.ui_Close"))
            self._close_button.clicked.connect(lambda: self.reject())

        pill_layout.addWidget(icon_frame)
        pill_layout.addWidget(self.title_label, 1)
        if self._close_button is not None:
            pill_layout.addWidget(self._close_button, 0, Qt.AlignVCenter)
        outer.addWidget(pill)

        self.header = header
        self._tint_icon()
        return header

    def _tint_icon(self) -> None:
        """按主题给头部图标着色（与左列抽屉的 ``PyIcon`` 同一取色）。"""
        pixmap = render_icon(self._icon_name, QColor(tokens()["muted"]), _ICON_SIZE, self.devicePixelRatioF())
        if isinstance(pixmap, QPixmap):
            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.clear()

    def _on_theme_changed(self) -> None:
        """主题切换：重新给图标/关闭按钮取色。"""
        if self.header is None:
            return
        self._tint_icon()
        if self._close_button is not None:
            self._close_button.set_color(QColor(tokens()["muted"]))

    # ------------------------------------------------------------------
    # 内容与标题
    # ------------------------------------------------------------------
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """追加内容控件（插在末尾弹性空间之前，保持贴顶排列）。"""
        index = max(0, self.content_layout.count() - 1)
        self.content_layout.insertWidget(index, widget, stretch)

    def set_title(self, title: str) -> None:
        self._title_key = title
        if self.title_label is not None:
            self.title_label.setText(Language.resolve_key(title))
        if self.header is not None:
            self.header.setVisible(bool(title) or self._closable)

    def set_icon(self, icon: str | None) -> None:
        self._icon_name = icon
        if self.header is not None:
            self._tint_icon()

    def set_resizable(self, resizable: bool) -> None:
        self._resizable = bool(resizable)
        grip = getattr(self, "_grip", None)
        if grip is not None:
            grip.setVisible(self._resizable)

    # ------------------------------------------------------------------
    # 位置
    # ------------------------------------------------------------------
    def bounds(self) -> QRect:
        """抽屉可活动的屏幕矩形（内容区，不含菜单/标题栏/版权栏）。"""
        return self._target_geometry()

    def _target_geometry(self) -> QRect:
        parent = self.parentWidget()
        if parent is None:
            return QRect()

        anchor = self._anchor
        if anchor is None:
            ui = getattr(parent, "ui", None)
            anchor = getattr(ui, "content_area_frame", None) if ui is not None else None
        if anchor is None or anchor is parent:
            origin = parent.mapToGlobal(QPoint(0, 0))
            return QRect(origin.x(), origin.y(), parent.width(), parent.height())

        origin = anchor.mapToGlobal(QPoint(0, 0))
        return QRect(origin.x(), origin.y(), max(1, anchor.width()), max(1, anchor.height()))

    def _compute_target_rect(self) -> QRect:
        width, height = self.width(), self.height()
        if self._position == "right":
            return QRect(width - self._size, 0, self._size, height)
        if self._position == "left":
            return QRect(0, 0, self._size, height)
        if self._position == "top":
            return QRect(0, 0, width, self._size)
        return QRect(0, height - self._size, width, self._size)

    def _layout_card(self) -> QRect:
        rect = self._compute_target_rect()
        self._target_rect = rect
        if getattr(self, "_sliding", False):
            return rect  # 动画期间由动画驱动几何，避免被 resizeEvent 拽回终点
        self.card().setGeometry(rect)
        self._place_grip()
        return rect

    def _place_grip(self) -> None:
        """把拖拽条贴到抽屉朝向内容的一侧。"""
        grip = getattr(self, "_grip", None)
        if grip is None:
            return
        card = self.card()
        if self._position == "left":
            grip.setGeometry(card.width() - _GRIP_BAND, 0, _GRIP_BAND, card.height())
        elif self._position == "right":
            grip.setGeometry(0, 0, _GRIP_BAND, card.height())
        elif self._position == "top":
            grip.setGeometry(0, card.height() - _GRIP_BAND, card.width(), _GRIP_BAND)
        else:
            grip.setGeometry(0, 0, card.width(), _GRIP_BAND)
        grip.setVisible(self._resizable)
        grip.raise_()

    def _resize_from_grip(self, start: int, delta: QPoint) -> None:
        """拖拽边缘时更新抽屉主轴尺寸（left/top 增大、right/bottom 反向）。"""
        if self._position == "left":
            new_size = start + delta.x()
        elif self._position == "right":
            new_size = start - delta.x()
        elif self._position == "top":
            new_size = start + delta.y()
        else:
            new_size = start - delta.y()
        axis = self.width() if self._position in ("left", "right") else self.height()
        limit = max(_MIN_DRAWER, axis - _DRAWER_MARGIN)
        self._size = max(_MIN_DRAWER, min(int(new_size), limit))
        self._layout_card()

    def _offscreen_rect(self) -> QRect:
        target = self._target_rect
        if self._position == "right":
            return target.translated(target.width(), 0)
        if self._position == "left":
            return target.translated(-target.width(), 0)
        if self._position == "top":
            return target.translated(0, -target.height())
        return target.translated(0, target.height())

    def _follow_parent(self) -> None:
        """父窗口缩放时重贴边；滑入途中也把动画终点改到新位置。"""
        super()._follow_parent()
        slide = getattr(self, "_slide", None)
        if self._sliding and slide is not None and slide.state() == QPropertyAnimation.State.Running:
            slide.setEndValue(self._target_rect)

    # ------------------------------------------------------------------
    # 动画
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        geometry = self._target_geometry()
        if not geometry.isNull():
            self.setGeometry(geometry)
        self._layout_card()
        # 先挪到屏外再滑入：窗口不透明，直接出现在终点会闪一下
        self.card().setGeometry(self._offscreen_rect())
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)
        self._animate_in()
        self.opened.emit()

    def _animate_in(self) -> None:
        duration = overlay_settings()[1]
        if duration <= 0:
            self._sliding = False
            self.card().setGeometry(self._target_rect)
            self._place_grip()
            return

        slide = QPropertyAnimation(self.card(), b"geometry", self)
        slide.setDuration(duration)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.setStartValue(self._offscreen_rect())
        slide.setEndValue(self._target_rect)
        slide.finished.connect(self._on_slide_in_finished)
        # 卡片每动一帧，遮罩与投影都要重画：否则旧位置的投影会留在原地成拖影
        slide.valueChanged.connect(lambda *_: self.update())
        self._sliding = True
        slide.start()
        self._slide = slide

    def _on_slide_in_finished(self) -> None:
        self._sliding = False
        self.card().setGeometry(self._target_rect)
        self._place_grip()

    def _finalize(self) -> None:
        self._sliding = False
        super()._finalize()

    def _animate_out(self) -> None:
        duration = overlay_settings()[1]
        if duration <= 0 or not self.isVisible():
            self._finalize()
            return

        slide = QPropertyAnimation(self.card(), b"geometry", self)
        slide.setDuration(duration)
        slide.setEasingCurve(QEasingCurve.InCubic)
        slide.setStartValue(self.card().geometry())
        slide.setEndValue(self._offscreen_rect())
        slide.finished.connect(self._finalize)
        slide.valueChanged.connect(lambda *_: self.update())
        self._sliding = True
        slide.start()
        self._slide = slide

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _shadow_band(self, card: QRect, depth: int) -> QRect:
        """抽屉朝向内容一侧的投影条带（深度为离抽屉边缘的像素数）。"""
        if self._position == "left":
            return QRect(card.right() + 1, card.top(), depth, card.height())
        if self._position == "right":
            return QRect(card.left() - depth, card.top(), depth, card.height())
        if self._position == "top":
            return QRect(card.left(), card.bottom() + 1, card.width(), depth)
        return QRect(card.left(), card.top() - depth, card.width(), depth)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        # 透明窗口不做背景擦除，局部重绘会把旧遮罩/投影再叠一层，卡片边缘
        # 因此出现一串越来越密的竖线；先清脏区再画。
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._mask_alpha))
        card = self._card.geometry()
        for depth, alpha in ((10, 8), (6, 12), (3, 18), (1, 26)):
            band = self._shadow_band(card, depth).intersected(self.rect())
            if not band.isEmpty():
                painter.fillRect(band, QColor(0, 0, 0, alpha))
        painter.end()

    def sizeHint(self):  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._size, self._size)


__all__ = ["CDrawer"]
