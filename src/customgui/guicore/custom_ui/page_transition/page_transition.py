"""栏目（页面）切换过场：擦除 → 按钮接力 → 展开。

时序（时长见 ``window.yaml`` 的 ``page_transition``）：

1. 旧页面从**右侧向左侧**擦除（可见宽度 100% → 0），露出内容区底色；
2. 原栏目按钮高亮 1 → 0；
3. 目标栏目按钮高亮 0 → 1；
4. 新页面从**左侧向右侧**展开（可见宽度 0 → 100%）。

为什么不用交叉淡化：两页同时半透明叠加会让整体亮度先变暗再变亮，
视觉上就是"闪一下"。这里全程只画一页快照，不存在两页叠加的帧，
过渡是"擦掉再画出"。

**过场的画布是整张区域背景卡片**（``stage``），不是内缩后的页面矩形：
遮罩铺满卡片、按卡片圆角裁剪，于是卡片表面和页面内容一起被擦掉、一起
展开，不会出现"内容在动、卡片边框静止"的割裂感。

透明擦除（``stage`` 路径）：遮罩**不铺底色**，只画带 alpha 的页面快照；
擦除/展开时露出的空白直接是卡片自己的玻璃背景（含亚克力与壁纸色调）。
为此过渡期间会临时隐藏 ``QStackedWidget``，避免底下的新页透过空白区。
不传 ``stage`` 的独立用法保留旧的实色打底模型，行为不变。

三条设计约束：

1. **业务不等动画**：``setCurrentWidget`` 在第一段擦除开始时就已完成，
   路由与页面状态照旧同步；
2. **失败即回落**：窗口不可见、总时长为 0、截图失败时退化为瞬时切换；
3. **可打断**：动画期间再次切换会先收尾上一次过场，只保留最新一层遮罩。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QRegion
from PySide6.QtWidgets import QPushButton, QStackedWidget, QWidget

from customgui.appcore import AppSettings, ColorPalette, get_design_tokens


class _WipeLayer(QWidget):
    """过场遮罩：卡片底色 + 旧页/新页截图的裁剪绘制。

    遮罩铺满整张区域背景卡片并按卡片圆角裁剪，因此擦除边界始终落在卡片
    表面之内——卡片不需要另画一圈静止的外框。
    """

    def __init__(self, parent, backdrop: QColor | None, radius: float = 0.0):
        super().__init__(parent)
        self.setObjectName("CPageTransition_Layer")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # 无底色模式必须真正透明：默认子控件在 grab()/重绘时可能带上父级底色，
        # 那会变成白色/灰色闪帧。关掉系统背景并显式关闭自动填充。
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        #: 遮罩底色；``None`` 表示不铺底色，让舞台自身的玻璃背景透出来
        self._backdrop = backdrop
        #: 卡片圆角：0 表示直角舞台（独立使用 ``QStackedWidget`` 时）
        self._radius = max(0.0, float(radius))
        self._old_pixmap = QPixmap()
        self._new_pixmap = QPixmap()
        self._out_progress = 0.0
        self._in_progress = 0.0

    def set_old_pixmap(self, pixmap: QPixmap) -> None:
        self._old_pixmap = pixmap
        self.update()

    def set_new_pixmap(self, pixmap: QPixmap) -> None:
        self._new_pixmap = pixmap
        self.update()

    def set_out_progress(self, progress: float) -> None:
        if progress != self._out_progress:
            self._out_progress = progress
            self.update()

    def set_in_progress(self, progress: float) -> None:
        if progress != self._in_progress:
            self._in_progress = progress
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._radius > 0:
            # 圆角裁剪：遮罩与卡片等大，边角必须收在卡片轮廓内，
            # 否则会把窗口底色补成方块（卡片圆角外被填上卡片色）
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
            painter.setClipPath(path)
        if self._backdrop is not None:
            painter.fillRect(self.rect(), self._backdrop)
        if self._in_progress > 0 and not self._new_pixmap.isNull():
            self._draw_reveal(painter, self._new_pixmap, self._in_progress)
        elif not self._old_pixmap.isNull():
            # 未进入展开阶段时始终显示旧页：进度为 0 就是完整旧页，
            # 否则遮罩第一帧会只剩底色，看起来像原页面闪了一下才消失。
            self._draw_reveal(painter, self._old_pixmap, 1.0 - self._out_progress)

    def _draw_reveal(self, painter: QPainter, pixmap: QPixmap, ratio: float) -> None:
        width = round(self.width() * ratio)
        if width <= 0:
            return
        # 源矩形按比例取左侧一段（兼容高 DPI 截图），目标矩形按逻辑像素绘制
        source = QRectF(0, 0, pixmap.width() * width / max(1, self.width()), pixmap.height())
        painter.drawPixmap(QRectF(0, 0, width, self.height()), pixmap, source)


class _TransitionState:
    """一次过场的运行时状态：遮罩、时间线、参与联动的两个按钮。"""

    __slots__ = (
        "layer",
        "animation",
        "old_button",
        "new_button",
        "timing",
        "total",
        "stack",
        "stack_hidden",
    )

    def __init__(self, layer, animation, old_button, new_button, timing, total, stack=None, stack_hidden=False):
        self.layer = layer
        self.animation = animation
        self.old_button = old_button
        self.new_button = new_button
        self.timing = timing
        self.total = total
        self.stack = stack
        self.stack_hidden = stack_hidden


class CPageTransition:
    """栏目切换动画工具类（无状态，全部 classmethod 调用）。"""

    _STATE_ATTR = "_c_page_transition_state"
    #: 配置不可用时的兜底时间线（毫秒）：擦除 / 按钮出 / 按钮入 / 展开
    _FALLBACK_TIMING = (120, 90, 110, 150)

    # 对外入口
    # ///////////////////////////////////////////////////////////////
    @classmethod
    def switch(cls, stack, page, *, menu=None, button_id=None, previous_button_id=None, stage=None) -> bool:
        """把 ``stack`` 切到 ``page``，播放了过场返回 True。

        ``menu`` / ``button_id`` / ``previous_button_id`` 用于让栏目按钮高亮
        跟随过场时序接力；不传则只做页面擦除。

        ``stage`` 是承载页面的**区域背景卡片**：传了它，过场画布就是整张卡片
        （含卡片底色与圆角），卡片表面随页面一起擦除、一起展开；不传则退化为
        只覆盖 ``stack`` 自身矩形的旧行为。
        """
        if not isinstance(stack, QStackedWidget) or page is None:
            return False
        if stack.currentWidget() is page:
            return False

        # 先收尾上一次过场：透明擦除期间堆叠被隐藏，若此时直接取快照会拿到
        # 一张空白卡片（中断切换时会闪一下）。cancel 会恢复堆叠并撤掉旧遮罩。
        cls.cancel(stack)

        previous = stack.currentWidget()
        timing = cls._timing()
        total = sum(timing[:4])
        if previous is None or total <= 0 or not stack.isVisible():
            stack.setCurrentWidget(page)
            return False

        # 舞台（区域卡片）路径使用**透明擦除**：遮罩不铺任何底色，擦除后的空白
        # 区域直接露出卡片自身的玻璃背景；快照只含内容，卡片原来的透明部分保持
        # alpha=0。这样擦除时不会用一个近似的实色顶替真实玻璃色（壁纸、亚克力
        # 色调都会影响卡片最终颜色），从根上消除切换首帧/末帧的闪色。
        # 不传 stage 的独立用法仍走旧模型（实色打底），保持向后兼容。
        transparent = stage is not None
        backdrop = None if transparent else cls._surface_color(stage)
        snapshot_fill = QColor(Qt.transparent) if transparent else backdrop
        surface = previous if stage is None else stage
        snapshot = cls._snapshot(surface, snapshot_fill)
        if snapshot is None:
            stack.setCurrentWidget(page)
            return False

        old_button = cls._find_button(menu, previous_button_id)
        new_button = cls._find_button(menu, button_id)
        # 转场接管按钮高亮：先冻结到时序起点，避免按钮自带动画抢跑
        cls._set_button_progress(old_button, 1.0)
        cls._set_button_progress(new_button, 0.0)

        layer = cls._build_layer(stack, stage, backdrop, cls._stage_radius(stage))
        layer.set_old_pixmap(snapshot)
        layer.show()
        layer.raise_()
        # 先把旧页画面同步画到屏幕上，再切底层页面，避免切换瞬间透出底色
        layer.repaint()

        # 切换后新页已在布局中，再抓一张用于最后一段展开（此时堆叠仍可见，
        # 新页才能被渲染进快照）
        stack.setCurrentWidget(page)
        layer.raise_()
        layer.set_new_pixmap(cls._snapshot(surface, snapshot_fill) or QPixmap())
        if transparent:
            # 两张快照都拿到后再隐藏堆叠：舞台只剩自己的玻璃背景，擦除/展开的
            # 空白区与卡片完全同色，不会出现"实色板"或"透明黑洞"。
            stack.hide()

        animation = QVariantAnimation(layer)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(total)
        state = _TransitionState(
            layer,
            animation,
            old_button,
            new_button,
            timing,
            total,
            stack=stack,
            stack_hidden=transparent,
        )
        animation.valueChanged.connect(lambda value: cls._apply_frame(state, float(value)))
        # 推迟一帧再收尾：不要在自己的 finished 回调里销毁正在派发信号的动画对象
        animation.finished.connect(lambda: QTimer.singleShot(0, lambda: cls._finish(stack, state)))
        setattr(stack, cls._STATE_ATTR, state)
        animation.start()
        return True

    @classmethod
    def cancel(cls, stack) -> None:
        """立即收尾正在播放的过场（可重复调用）。"""
        state = getattr(stack, cls._STATE_ATTR, None)
        if state is None:
            return
        setattr(stack, cls._STATE_ATTR, None)
        cls._teardown(state)

    # 时间线
    # ///////////////////////////////////////////////////////////////
    @classmethod
    def _apply_frame(cls, state, t: float) -> None:
        page_out, menu_out, menu_in, _, curve = state.timing
        total = max(1, state.total)
        a = page_out / total
        b = a + menu_out / total
        c = b + menu_in / total

        if t < a:
            state.layer.set_out_progress(curve.valueForProgress(t / a))
            return

        state.layer.set_out_progress(1.0)
        if t < b:
            progress = (t - a) / (b - a) if b > a else 1.0
            cls._set_button_progress(state.old_button, 1.0 - curve.valueForProgress(progress))
            return

        cls._set_button_progress(state.old_button, 0.0)
        if t < c:
            progress = (t - b) / (c - b) if c > b else 1.0
            cls._set_button_progress(state.new_button, curve.valueForProgress(progress))
            return

        cls._set_button_progress(state.new_button, 1.0)
        progress = (t - c) / (1.0 - c) if c < 1.0 else 1.0
        state.layer.set_in_progress(curve.valueForProgress(progress))

    @classmethod
    def _finish(cls, stack, state) -> None:
        try:
            if getattr(stack, cls._STATE_ATTR, None) is state:
                setattr(stack, cls._STATE_ATTR, None)
        except RuntimeError:  # 堆叠容器已随窗口销毁
            pass
        cls._teardown(state)

    @classmethod
    def _teardown(cls, state) -> None:
        """停时间线、撤遮罩、把按钮高亮落到终态（对象可能已随窗口销毁）。"""
        # 先恢复堆叠：透明擦除期间它被隐藏，若先删遮罩会在卡片上留一帧空白。
        # 同步 repaint 让新页在遮罩还盖着时就画好，再撤遮罩即无缝衔接。
        stack = getattr(state, "stack", None)
        if getattr(state, "stack_hidden", False) and stack is not None:
            try:
                stack.show()
                stack.repaint()
            except RuntimeError:
                pass
        try:
            state.animation.stop()
            state.animation.deleteLater()
        except RuntimeError:
            return
        cls._set_button_progress(state.old_button, 0.0)
        cls._set_button_progress(state.new_button, 1.0)
        try:
            state.layer.hide()
            state.layer.deleteLater()
        except RuntimeError:
            pass

    # 配置与外部对象
    # ///////////////////////////////////////////////////////////////
    @staticmethod
    def _build_layer(stack, stage, backdrop: QColor | None, radius: float) -> _WipeLayer:
        """遮罩挂在舞台（区域背景卡片）的上一层，并**铺满整张卡片**。

        ``QStackedWidget`` 切换 current 时会把新页 ``raise()``；遮罩若挂在它内部
        会被压到新页下面，同步刷新时就透出一帧新页面。挂到父级后两者不再争 z-order。
        舞台没有父级时（独立使用）退回挂在舞台自身上。
        """
        target = stack if stage is None else stage
        host = target.parentWidget()
        layer = _WipeLayer(host or target, backdrop, radius)
        # geometry() 在父坐标系，rect() 在自身坐标系：无父级时两者等价
        layer.setGeometry(target.rect() if host is None else target.geometry())
        return layer

    @staticmethod
    def _surface_color(stage) -> QColor:
        """旧模型（不传 ``stage``）的过场底色：退回内容区底色。

        主窗口的 stage 路径已改为透明擦除，不再经过这里；此函数只服务独立
        堆叠控件的向后兼容行为。
        """
        if stage is None:
            return QColor(ColorPalette.custom_bg_one)
        try:
            from customgui.guicore.styles import region_card_background
        except ImportError:  # 极简环境（不经 guicore 装配）下退回内容区底色
            return QColor(ColorPalette.custom_bg_one)
        return QColor(region_card_background())

    @staticmethod
    def _stage_radius(stage) -> float:
        """舞台圆角：与 ``#CRegion_Card_Frame`` 的 ``border-radius`` 同源。"""
        if stage is None:
            return 0.0
        return float(get_design_tokens().radius.window)

    @classmethod
    def _timing(cls) -> tuple[int, int, int, int, QEasingCurve]:
        try:
            config = AppSettings.page_transition
            return (
                int(config.page_out),
                int(config.menu_out),
                int(config.menu_in),
                int(config.page_in),
                cls._curve(config.easing),
            )
        except Exception:  # 配置上下文未就绪时退回兜底时间线，动画不应影响导航
            return (*cls._FALLBACK_TIMING, QEasingCurve(QEasingCurve.Type.InOutQuad))

    @staticmethod
    def _curve(name) -> QEasingCurve:
        try:
            return QEasingCurve(QEasingCurve.Type[str(name)])
        except (KeyError, TypeError, ValueError):
            return QEasingCurve(QEasingCurve.Type.InOutQuad)

    @staticmethod
    def _find_button(menu, button_id):
        if menu is None or not button_id:
            return None
        finder = getattr(menu, "findChild", None)
        if not callable(finder):
            return None
        try:
            button = finder(QPushButton, button_id)
        except (TypeError, RuntimeError):
            return None
        return button if hasattr(button, "set_selection_progress") else None

    @staticmethod
    def _set_button_progress(button, progress: float) -> None:
        setter = getattr(button, "set_selection_progress", None)
        if callable(setter):
            setter(progress)

    @staticmethod
    def _snapshot(widget, surface: QColor):
        """抓舞台快照：先铺底色再渲染子控件。

        ``DrawChildren`` 只画子控件、不画控件自身的 QSS 背景，所以先用 ``surface``
        打底。舞台路径传 ``QColor(Qt.transparent)``：快照保持 alpha，透明区域
        让卡片自身的玻璃背景透出来；独立的堆叠控件路径仍铺实色内容区底色，
        行为不变。
        """
        if widget is None:
            return None
        try:
            ratio = widget.devicePixelRatioF()
            size = widget.size()
            pixmap = QPixmap(max(1, round(size.width() * ratio)), max(1, round(size.height() * ratio)))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(surface)
            painter = QPainter(pixmap)
            # 只画子控件：DrawWindowBackground 会用默认调色板把预览涂成白色
            widget.render(painter, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
            painter.end()
        except RuntimeError:
            return None
        return None if pixmap.isNull() else pixmap


__all__ = ["CPageTransition"]
