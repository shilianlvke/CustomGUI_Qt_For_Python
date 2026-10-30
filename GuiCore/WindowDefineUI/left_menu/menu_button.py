from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    Slot,
)
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QPushButton
from AppCore import AppSettings, ColorPalette, PathFactory

from ...CustomUI import CToolTip


def _mix_color(start_color, end_color, progress) -> QColor:
    """按进度在两色之间插值（选中态过渡用）。"""
    start = QColor(start_color)
    end = QColor(end_color)
    if progress <= 0:
        return start
    if progress >= 1:
        return end
    return QColor(
        round(start.red() + (end.red() - start.red()) * progress),
        round(start.green() + (end.green() - start.green()) * progress),
        round(start.blue() + (end.blue() - start.blue()) * progress),
        round(start.alpha() + (end.alpha() - start.alpha()) * progress),
    )


class CLeftMenuButton(QPushButton):
    style_change = Slot("style_change")

    #: 配置不可用时的兜底时长（毫秒）
    FALLBACK_ANIMATION = 120

    def __init__(
        self,
        app_parent,
        text,
        btn_id=None,
        tooltip_text="",
        margin=4,
        icon_path="icon_add_user",
        icon_active_menu="active_menu",
        is_active=False,
        is_active_tab=False,
        is_toggle_active=False,
        minimum_width=50,
        maximum_width=240,
        font_family=None,
    ):
        super().__init__()
        self.setText(text)
        self.setFont(font_family)
        self.setCursor(Qt.PointingHandCursor)
        self.setMaximumHeight(50)
        self.setMinimumHeight(50)
        self.setObjectName(btn_id)
        # APP PATH
        self._icon_path = PathFactory.resolve_svg(icon_path)
        self._icon_active_menu = PathFactory.set_svg_icon(icon_active_menu)
        self._icon_cache: dict[str, QPixmap] = {}
        # PROPERTIES（只存状态名，颜色在绘制时实时读调色板，主题切换自动生效）
        self._margin = margin
        self._state = "normal"  # normal / hover / pressed
        self._parent = app_parent
        self._is_active = is_active
        self._is_active_tab = is_active_tab
        self._is_toggle_active = is_toggle_active
        self._minimum_width = minimum_width
        self._maximum_width = maximum_width
        # 选中态过渡：0 = 普通，1 = 选中；构造时直接到位，不播放入场动画
        self._active_progress = 1.0 if (is_active or is_active_tab) else 0.0
        self._active_kind = "tab" if is_active_tab else "page"
        self._active_animation = None
        # TOOLTIP
        self._tooltip_text = tooltip_text
        self.tooltip = CToolTip(app_parent, tooltip_text, accent="left")
        self.tooltip.hide()

    # 选中态进度：由 QPropertyAnimation 驱动，paintEvent 按进度插值
    def _get_active_progress(self):
        return self._active_progress

    def _set_active_progress(self, progress):
        self._active_progress = progress
        self.update()

    activeProgress = Property(float, _get_active_progress, _set_active_progress)

    # 绘制事件
    def paintEvent(self, event):
        # PAINTER
        p = QPainter()
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setFont(self.font())

        # RECTANGLES
        rect_inside = QRect(4, 5, self.width() - 8, self.height() - 10)
        rect_icon = QRect(0, 0, 50, self.height())
        rect_blue = QRect(4, 5, 20, self.height() - 10)
        rect_inside_active = QRect(7, 5, self.width(), self.height() - 10)
        rect_text = QRect(45, 0, self.width() - 50, self.height())

        progress = self._active_progress
        is_tab = self._active_kind == "tab"

        # NORMAL BG：先铺普通底，选中块画在其上（两者同色系，边角不会露出色差）
        p.setBrush(QColor(self._normal_bg_color()))
        p.drawRoundedRect(rect_inside, 8, 8)

        # ACTIVE BG：用剪裁从左向右展开，比透明度叠色更干净
        if progress > 0:
            p.save()
            p.setClipRect(QRect(0, 0, round(self.width() * progress), self.height()))
            p.setBrush(QColor(ColorPalette.custom_dark_four if is_tab else ColorPalette.custom_context_color))
            p.drawRoundedRect(rect_blue, 8, 8)
            p.setBrush(QColor(ColorPalette.custom_bg_one))
            p.drawRoundedRect(rect_inside_active, 8, 8)
            p.restore()

        # DRAW TEXT：普通色 -> 活动色
        p.setPen(_mix_color(ColorPalette.custom_text_foreground, ColorPalette.custom_text_active, progress))
        p.drawText(rect_text, Qt.AlignVCenter, self.text())

        # DRAW ICONS：普通色 -> 选中色（页面选中偏蓝，导航 tab 偏亮）
        if self._is_toggle_active and progress <= 0:
            icon_color = ColorPalette.custom_context_color
        else:
            target = ColorPalette.custom_icon_active if is_tab else ColorPalette.custom_context_color
            icon_color = _mix_color(self._normal_icon_color(), target, progress)
        self.icon_paint(p, self._icon_path, rect_icon, icon_color)

        # DRAW ACTIVE MARK：右侧活动标记随进度淡入
        if progress > 0:
            p.save()
            p.setOpacity(progress)
            self.icon_active(p, self._icon_active_menu, self.width())
            p.restore()

        p.end()

    # 设置活跃的界面
    def set_active(self, is_active):
        self._is_active = is_active
        if not is_active and not self._is_active_tab:
            # 退出选中时归位为普通态，避免残留悬停/按下的底色
            self._state = "normal"
        self._sync_active_progress()

    # 设置活跃的导航栏
    def set_active_tab(self, is_active):
        self._is_active_tab = is_active
        if not is_active and not self._is_active:
            self._state = "normal"
        self._sync_active_progress()

    # 普通态底色（按下/悬停各有对应层级，颜色实时取，主题切换后重绘即更新）
    def _normal_bg_color(self):
        if self._is_toggle_active or self._state == "hover":
            return ColorPalette.custom_dark_three
        if self._state == "pressed":
            return ColorPalette.custom_dark_four
        return ColorPalette.custom_dark_one

    # 普通态图标色
    def _normal_icon_color(self):
        if self._state == "hover":
            return ColorPalette.custom_icon_hover
        if self._state == "pressed":
            return ColorPalette.custom_context_color
        return ColorPalette.custom_icon_color

    # 归一化选中进度：页面选中与导航 tab 共用同一套过渡
    def _sync_active_progress(self):
        selected = self._is_active or self._is_active_tab
        if selected:
            self._active_kind = "tab" if self._is_active_tab else "page"
        self._animate_active(1.0 if selected else 0.0)

    # 选中态过渡动画
    def _animate_active(self, target):
        if self._active_animation is None:
            self._active_animation = QPropertyAnimation(self, b"activeProgress", self)
            self._active_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._active_animation.stop()
        if abs(self._active_progress - target) < 1e-3:
            self._set_active_progress(target)
            return
        self._active_animation.setDuration(self._resolve_duration(target))
        self._active_animation.setStartValue(self._active_progress)
        self._active_animation.setEndValue(target)
        self._active_animation.start()

    # 时长取自 window.yaml 的 page_transition（进入用 menu_in，退出用 menu_out）
    @staticmethod
    def _resolve_duration(target) -> int:
        try:
            config = AppSettings.page_transition
            return int(config.menu_in if target >= 1.0 else config.menu_out)
        except Exception:  # 配置上下文未就绪时用兜底时长，动画不应影响交互
            return CLeftMenuButton.FALLBACK_ANIMATION

    # 外部时间线（栏目切换过场）直接驱动选中进度，会打断自身动画
    def set_selection_progress(self, progress):
        if self._active_animation is not None:
            self._active_animation.stop()
        self._set_active_progress(max(0.0, min(1.0, float(progress))))

    # 返回是否是活跃界面
    def is_active(self):
        return self._is_active

    # 返回是否是活跃导航
    def is_active_tab(self):
        return self._is_active_tab

    # 设置活动切换
    def set_active_toggle(self, is_active):
        self._is_toggle_active = is_active
        self.update()

    # 设置图标
    def set_icon(self, icon_path):
        self._icon_path = icon_path
        self.update()

    # 更新提示文本（语言切换时使用）
    def set_tooltip(self, text):
        self._tooltip_text = text
        self.tooltip.setText(text)
        self.tooltip.adjustSize()

    # 用颜色绘制图标
    def _base_icon(self, image) -> QPixmap:
        if not isinstance(image, str):
            return image
        cached = self._icon_cache.get(image)
        if cached is None:
            cached = QPixmap(image)
            self._icon_cache[image] = cached
        return cached

    def icon_paint(self, qp, image, rect, color):
        icon = QPixmap(self._base_icon(image))
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(icon.rect(), color)
        qp.drawPixmap((rect.width() - icon.width()) / 2, (rect.height() - icon.height()) / 2, icon)
        painter.end()

    # 绘制活动图标/右侧
    def icon_active(self, qp, image, width):
        icon = QPixmap(self._base_icon(image))
        painter = QPainter(icon)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(icon.rect(), ColorPalette.custom_bg_one)
        qp.drawPixmap(width - 5, 0, icon)
        painter.end()

    # 更改样式
    # 具有自定义样式的函数
    def change_style(self, event):
        if self._is_active:
            return
        if event == QEvent.Enter:
            self._state = "hover"
        elif event == QEvent.Leave:
            self._state = "normal"
        elif event == QEvent.MouseButtonPress:
            self._state = "pressed"
        elif event == QEvent.MouseButtonRelease:
            self._state = "hover"
        self.update()

    # 鼠标悬停
    # 当鼠标位于BTN上时触发的事件
    def enterEvent(self, event):
        self.change_style(QEvent.Enter)
        if self.width() in range(self._minimum_width - 5, self._minimum_width + 5) and self._tooltip_text:
            self.move_tooltip()
            self.tooltip.show()

    # 鼠标离开
    # 鼠标离开BTN时触发的事件
    def leaveEvent(self, event):
        self.change_style(QEvent.Leave)
        self.tooltip.hide()

    # 鼠标按下
    # 按下左键时触发的事件
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.tooltip.hide()
            self.clicked.emit()
            self.change_style(QEvent.MouseButtonPress)

    # 鼠标释放
    # 松开鼠标按钮后触发的事件
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.change_style(QEvent.MouseButtonRelease)
            self.released.emit()

    # 移动工具提示
    def move_tooltip(self):
        # 获取主窗口父窗口
        gp = self.mapToGlobal(QPoint(0, 0))

        # 设置小部件以获取位置
        # 返回小部件在应用程序中的绝对位置
        pos = self._parent.mapFromGlobal(gp)

        # 格式位置
        # 使用偏移调整工具提示位置
        pos_x = pos.x() + self.width() + 5
        pos_y = pos.y() + (self.width() - self.tooltip.height()) // 2

        # 为小部件设置位置
        # 移动工具提示位置
        self.tooltip.move(pos_x, pos_y)
