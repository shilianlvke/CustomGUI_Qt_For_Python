"""桌面宠物窗口：无边框、置顶、透明、可拖拽的猕猴桃。

使用 QSvgRenderer 渲染 engine.core 生成的 SVG，
逐帧 QTimer 驱动引擎（约 60fps），与原型的 requestAnimationFrame 等价。
"""

from __future__ import annotations

import time

from PySide6.QtCore import QByteArray, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QCursor, QMouseEvent, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from sllkgui.appcore import Language

from .engine.core import GROUPS, PALETTE, SHAPES, MihoutaoEngine, canvas_scale

#: 规格表里的分组英文标签 → 语言键后缀。spec.json 与原型同源、标签不可改，
#: 因此用这张固定映射把「规格」和「显示文案」解耦。
_GROUP_KEY: dict[str, str] = {
    "Lifecycle": "lifecycle",
    "Reactions": "reactions",
    "Agent morphs": "agentmorphs",
    "Product lifecycle": "productlifecycle",
}


class PetWindow(QWidget):
    """常驻桌面的透明宠物窗口。

    - Tool | FramelessWindowHint | WindowStaysOnTopHint 常驻置顶，不进任务栏；
    - 左键拖拽移动；右键弹出菜单（状态/果形/色板/动作/退出）；
    - 开启跟随指针后根据全局光标相对窗口中心的位置设置 gaze_target；
    - 双击触发弹跳。
    """

    def __init__(self, engine: MihoutaoEngine, *, size: int = 220) -> None:
        super().__init__(None)
        self.engine = engine
        # 引擎的 viewBox 比本体大一圈（承接 overflow: visible 的装饰层），
        # 画布按同样倍率放大，本体才维持 size 指定的视觉尺寸。
        self._size = max(64, round(size * canvas_scale()))
        self._body_size = size
        self._drag_offset: QPoint | None = None
        self._renderer = QSvgRenderer()
        self._pixmap = QPixmap(self._size, self._size)
        self._pixmap.fill(Qt.transparent)
        self.on_quit = None
        self.on_state_changed = None
        self.on_moved = None
        # 由控制器注入：让菜单改动写回偏好（无控制器时退化为仅影响本次会话）
        self.on_shape_changed = None
        self.on_color_changed = None
        self.on_pinned_changed = None

        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(self._size, self._size)
        self.setMouseTracking(True)
        self.setWindowTitle(self._text("PetSettingsTitle", "桌面宠物"))
        self.setToolTip(self._text("PetTooltip", "桌面宠物 · 左键拖拽 / 双击跳跃 / 右键菜单"))

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._place_initial()

    @staticmethod
    def _text(key: str, fallback: str) -> str:
        """读取基座语言资源键，缺失时回退到内置中文。"""
        return str(Language.resolve_key("language.UI.ui_" + key, fallback))

    @classmethod
    def _state_text(cls, name: str) -> str:
        """情绪状态显示名（``idle`` → 空闲）；缺失时回落为状态名本身。"""
        return cls._text("PetState_" + name, name)

    @classmethod
    def _group_text(cls, label: str) -> str:
        """分组显示名；未登记的分组沿用规格表标签，绝不显示空白。"""
        suffix = _GROUP_KEY.get(label)
        return cls._text("PetGroup_" + suffix, label) if suffix else label

    def refresh_texts(self) -> None:
        """语言切换后刷新标题与提示（菜单为即时构建，下次打开即为新文案）。"""
        self.setWindowTitle(self._text("PetSettingsTitle", "桌面宠物"))
        self.setToolTip(self._text("PetTooltip", "桌面宠物 · 左键拖拽 / 双击跳跃 / 右键菜单"))

    def _place_initial(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.move(100, 100)
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self._size - 24, geo.bottom() - self._size - 24)

    def start(self) -> None:
        self._last_monotonic = time.monotonic()
        self.show()
        self.raise_()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def set_pinned(self, pinned: bool) -> None:
        flags = self.windowFlags()
        if pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def _tick(self) -> None:
        now = time.monotonic()
        last = getattr(self, "_last_monotonic", now)
        self._last_monotonic = now
        dt = min(0.05, max(0.0, now - last))
        self.engine.update(dt)

        if self.engine.follow_pointer:
            cursor = QCursor.pos()
            center = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
            screen = QApplication.primaryScreen()
            w, h = (screen.geometry().width(), screen.geometry().height()) if screen else (1920, 1080)
            self.engine.gaze_target = (
                max(-1.0, min(1.0, (cursor.x() - center.x()) / (w * 0.5))) * 0.055,
                max(-1.0, min(1.0, (cursor.y() - center.y()) / (h * 0.5))) * 0.045,
            )
        else:
            self.engine.gaze_target = None

        self._pixmap.fill(Qt.transparent)
        painter = QPainter(self._pixmap)
        renderer = QSvgRenderer(QByteArray(self.engine.render_svg().encode("utf-8")))
        renderer.render(painter, QRectF(0, 0, self._size, self._size))
        painter.end()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self.mapToGlobal(event.position().toPoint()) - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._drag_offset is not None
            self._drag_offset = None
            if was_dragging and self.on_moved is not None:
                pos = self.pos()
                self.on_moved(pos.x(), pos.y())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.engine.hop_once()

    def _show_menu(self, pos: QPoint) -> None:
        self._build_menu().exec(pos)

    def _build_menu(self) -> QMenu:
        """构建右键菜单（不弹出）。

        构建与弹出分离：菜单文案要在语言切换后立即重建，测试也需要
        在不进入模态事件循环的前提下断言每一项的文案。
        """
        menu = QMenu(self)
        # 分组与状态名都走语言资源：spec.json 的英文标签只用于查键，不上屏。
        for group in GROUPS:
            sub = menu.addMenu(self._group_text(group["label"]))
            for name in group["states"]:
                action = sub.addAction(self._state_text(name))
                action.setCheckable(True)
                action.setChecked(self.engine.state == name)
                action.triggered.connect(lambda _checked=False, n=name: self._set_state(n))
        menu.addSeparator()
        shapes_menu = menu.addMenu(self._text("PetMenuShapes", "果形"))
        for shape_id, shape in SHAPES.items():
            action = shapes_menu.addAction(self._text("PetShape_" + shape_id, str(shape["label"])))
            action.setCheckable(True)
            action.setChecked(self.engine.shape_name == shape_id)
            action.triggered.connect(lambda _checked=False, s=shape_id: self._set_shape(s))
        colors_menu = menu.addMenu(self._text("PetMenuColors", "果肉色"))
        for color_id, pal in PALETTE.items():
            action = colors_menu.addAction(self._text("PetColor_" + color_id, str(pal["label"])))
            action.setCheckable(True)
            action.setChecked(self.engine.color_id == color_id)
            action.triggered.connect(lambda _checked=False, c=color_id: self._set_color(c))
        menu.addSeparator()
        menu.addAction(self._text("PetMenuSpin", "转一圈"), lambda: self.engine.spin_once())
        menu.addAction(self._text("PetMenuHop", "跳一下"), lambda: self.engine.hop_once())
        menu.addAction(self._text("PetMenuBurst", "粒子"), lambda: self.engine.burst_once())
        menu.addSeparator()
        pin = menu.addAction(self._text("PetMenuPin", "保持置顶"))
        pin.setCheckable(True)
        pin.setChecked(bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        pin.triggered.connect(self._set_pinned)
        menu.addSeparator()
        menu.addAction(self._text("PetMenuQuit", "退出宠物"), lambda: self.on_quit() if self.on_quit else self.stop())
        return menu

    def _set_state(self, name: str) -> None:
        self.engine.set_mode("hold")
        self.engine.set_state(name)
        if self.on_state_changed:
            self.on_state_changed(name)

    def _set_shape(self, shape_id: str) -> None:
        if self.on_shape_changed is not None:
            self.on_shape_changed(shape_id)
        else:
            self.engine.set_shape(shape_id)

    def _set_color(self, color_id: str) -> None:
        if self.on_color_changed is not None:
            self.on_color_changed(color_id)
        else:
            self.engine.set_color(color_id)

    def _set_pinned(self, pinned: bool) -> None:
        if self.on_pinned_changed is not None:
            self.on_pinned_changed(pinned)
        else:
            self.set_pinned(pinned)
