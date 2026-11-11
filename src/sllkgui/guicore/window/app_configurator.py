"""外观配置抽屉：主题、材质、背景与界面四个单屏子页。

右侧滑入的浮层面板，所有配色在绘制或刷新时实时读取设计令牌与调色板，
切换主题后重绘即生效；语言以目标语言直接选择，不再循环轮替。

控件树（标题栏、分段导航与四个配置子页）由
:mod:`sllkgui.guicore.window.app_configurator_sections` 提供，本模块只负责
状态、信号、主题/语言/菜单模式的运行期逻辑与抽屉开合动画。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy

from sllkgui.appcore import (
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_design_tokens,
    get_theme_manager,
)

from ..acrylic import set_acrylic_transparency, set_glass_strength
from .app_configurator_sections import _ConfigSectionsMixin, _ThemeCard


class CAppConfigurator(_ConfigSectionsMixin, QFrame):
    """右侧滑入的外观配置抽屉。

    用法::

        panel = CAppConfigurator(host_widget)
        panel.themeChanged.connect(on_theme)
        panel.open()

    信号 ``themeChanged`` 只在通过本面板切换主题时发出；外部调用
    ``ThemeManager.apply`` 时面板会静默同步选中态。``languageChanged`` 由
    宿主负责调用 ``apply_language``（本面板只负责选择，不做页面重建）。
    """

    themeChanged = Signal(str)
    languageChanged = Signal(str)
    menuModeChanged = Signal(str)
    darkModeChanged = Signal(bool)
    #: 实时预览：透明度（0-100）与亚克力质感强度（0-100）变化
    transparencyChanged = Signal(int)
    glassStrengthChanged = Signal(int)
    #: 背景图变更：(路径, 适应模式)；路径为空表示恢复主题纯色
    backgroundChanged = Signal(str, str)
    #: 滑块拖动结束：宿主可在此一次性落盘，避免拖动过程中频繁写文件
    appearanceCommitted = Signal()
    closed = Signal()
    #: 嵌入右侧抽屉时，标题栏关闭按钮请求外层收起抽屉。
    closeRequested = Signal()

    #: 抽屉默认宽度
    DEFAULT_WIDTH = 360
    #: 配置未就绪时的滑动时长（毫秒）
    FALLBACK_DURATION = 200

    def __init__(self, parent=None, width: int = DEFAULT_WIDTH, embedded: bool = False):
        super().__init__(parent)
        self.setObjectName("CAppConfigurator_Frame")
        #: 嵌入模式：作为右侧抽屉里的普通页面使用，不再做固定宽度、滑入动画与
        #: 自身背景绘制；标题/关闭按钮也由外层抽屉控制。
        self._embedded = bool(embedded)
        self._width = max(280, int(width))
        self._open = False
        self._closing = False
        self._animation: QPropertyAnimation | None = None
        self._menu_mode = "static"
        self._suppress_dark_sync = False
        self._theme_cards: list[_ThemeCard] = []
        #: 需要随语言刷新的标签：资源键 -> (标签, 默认文案)
        self._texts: dict[str, tuple[QLabel, str]] = {}

        if self._embedded:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedWidth(self._width)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._setup_ui()
        self._sync_theme_state()
        self.update_style()

        get_theme_manager().subscribe(self._on_theme_applied)
        Language.subscribe(self._refresh_texts)
        if parent is not None and not self._embedded:
            parent.installEventFilter(self)
        if not self._embedded:
            self.hide()

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def set_theme(self, name: str) -> bool:
        """应用指定主题并发出 ``themeChanged``；未知主题返回 False。"""
        if name not in AppThemes:
            return False
        get_theme_manager().apply(name)
        self._sync_theme_state()
        self.themeChanged.emit(name)
        return True

    def current_theme(self) -> str:
        return get_theme_manager().current()

    def _on_theme_applied(self) -> None:
        self._sync_theme_state()
        self.update_style()

    def _sync_theme_state(self) -> None:
        current = get_theme_manager().current()
        for card in self._theme_cards:
            card.set_selected(card.name() == current)
        if not self._suppress_dark_sync:
            dark = QColor(ColorPalette.custom_bg_one).lightness() < 128
            # 不屏蔽信号：CToggleSwitch 只有在信号驱动下才会把滑块动画到正确
            # 位置；期间用 _suppress_dark_sync 拦掉本面板的 toggled 回写，
            # 避免「同步开关」再次触发主题切换。
            self._suppress_dark_sync = True
            try:
                self.dark_switch.setChecked(dark)
            finally:
                self._suppress_dark_sync = False

    @staticmethod
    def _first_dark_theme() -> str | None:
        names = sorted(AppThemes.keys())
        for preferred in ("dracula", "default"):
            if preferred in names:
                return preferred
        for name in names:
            try:
                if QColor(AppThemes[name].data.custom_bg_one).lightness() < 128:
                    return name
            except AttributeError:
                continue
        return None

    @staticmethod
    def _light_theme() -> str | None:
        """关闭深色模式时回退的浅色主题。

        不能直接回 ``AppSettings.theme_name``：默认主题本身是暗色，关掉开关后
        画面仍是暗色，开关状态与主题就会对不上。这里优先沿用配置里**已经是
        浅色**的主题，否则按 bright / eye 的顺序挑一套浅色。
        """
        names = sorted(AppThemes.keys())
        try:
            configured = AppSettings.theme_name
        except Exception:
            configured = None
        if configured in names:
            try:
                if QColor(AppThemes[configured].data.custom_bg_one).lightness() >= 128:
                    return configured
            except AttributeError:
                pass
        for preferred in ("bright", "eye"):
            if preferred in names:
                return preferred
        for name in names:
            try:
                if QColor(AppThemes[name].data.custom_bg_one).lightness() >= 128:
                    return name
            except AttributeError:
                continue
        return "default" if "default" in names else (names[0] if names else None)

    def _on_dark_toggled(self, checked: bool) -> None:
        if self._suppress_dark_sync:
            return
        target = self._first_dark_theme() if checked else self._light_theme()
        self._suppress_dark_sync = True
        try:
            if target is not None:
                self.set_theme(target)
        finally:
            self._suppress_dark_sync = False
        self.darkModeChanged.emit(bool(checked))

    # ------------------------------------------------------------------
    # 材质与通透度
    # ------------------------------------------------------------------
    def transparency(self) -> int:
        """当前窗口透明度（0-100）。"""
        return self.transparency_slider.value()

    def appearance_strength(self) -> int:
        """当前亚克力质感强度（0-100）。"""
        return self.glass_strength_slider.value()

    def set_appearance(self, transparency: int | None = None, strength: int | None = None) -> None:
        """静默同步滑块与运行期外观值（启动恢复 / 外部调用）。"""
        if transparency is not None:
            value = set_acrylic_transparency(int(transparency))
            self.transparency_slider.setValue(value, emit=False)
            self.transparency_value.setText(f"{value}%")
        if strength is not None:
            value = set_glass_strength(int(strength))
            self.glass_strength_slider.setValue(value, emit=False)
            self.glass_strength_value.setText(f"{value}%")

    def _on_transparency_changed(self, value: int) -> None:
        set_acrylic_transparency(value)
        self.transparency_value.setText(f"{int(value)}%")
        self.transparencyChanged.emit(int(value))

    def _on_glass_strength_changed(self, value: int) -> None:
        set_glass_strength(value)
        self.glass_strength_value.setText(f"{int(value)}%")
        self.glassStrengthChanged.emit(int(value))

    # ------------------------------------------------------------------
    # 语言
    # ------------------------------------------------------------------
    def language(self) -> str:
        return Language.current()

    def _on_language_selected(self, label: str) -> None:
        target = next((code for code, text in self._language_options() if text == label), None)
        if target is None or target == Language.current():
            return
        self.languageChanged.emit(target)
        # 宿主没有应用（独立浮层或未接线）时回到实际语言，避免选择器与界面不一致
        if Language.current() != target:
            self._sync_language()

    def _sync_language(self) -> None:
        current = Language.current()
        label = next((text for code, text in self._language_options() if code == current), None)
        if label is not None and hasattr(self, "language_select"):
            self.language_select.set_value(label, emit=False)

    # ------------------------------------------------------------------
    # 菜单模式
    # ------------------------------------------------------------------
    def menu_mode(self) -> str:
        return self._menu_mode

    def set_menu_mode(self, mode: str) -> None:
        value = "overlay" if str(mode).lower() == "overlay" else "static"
        self.menu_mode_select.set_index(1 if value == "overlay" else 0, emit=False)
        if value == self._menu_mode:
            return
        self._menu_mode = value
        self.menuModeChanged.emit(value)

    def _on_menu_mode_selected(self, index: int) -> None:
        self.set_menu_mode("overlay" if index == 1 else "static")

    @staticmethod
    def _menu_mode_labels() -> list[str]:
        return [
            Language.resolve_key("language.UI.ui_ModeStatic", "固定"),
            Language.resolve_key("language.UI.ui_ModeOverlay", "浮层"),
        ]

    def _refresh_texts(self) -> None:
        """语言切换后刷新标题、分区与选项文案（控件树不重建）。"""
        for key, (label, fallback) in self._texts.items():
            label.setText(Language.resolve_key(key, fallback))
        self.tabs.set_options(self._tab_labels(), index=self.tabs.current_index(), emit=False)
        self.menu_mode_select.set_options(self._menu_mode_labels(), index=self.menu_mode_select.current_index(), emit=False)
        self._refresh_background_texts()
        self._sync_language()
        self.update()

    # ------------------------------------------------------------------
    # 开关
    # ------------------------------------------------------------------
    def open(self) -> None:
        """从右侧滑入并展开面板（嵌入模式下无动作，由右侧抽屉负责开合）。"""
        if self._embedded:
            return
        self._closing = False
        self._open = True
        self._place(self._start_x())
        self.show()
        self.raise_()
        self._animate_to(QPoint(self._end_x(), 0), None)

    def _request_close(self) -> None:
        """关闭按钮：独立浮层直接收起，嵌入抽屉时交给外层控制器。"""
        if self._embedded:
            self.closeRequested.emit()
            return
        self.close()

    def close(self) -> None:
        """滑出并隐藏面板，动画结束后发出 ``closed``（嵌入模式下无动作）。"""
        if self._embedded:
            return
        if self._closing:
            return
        if not self._open and not self.isVisible():
            return
        self._open = False
        self._closing = True
        self._animate_to(QPoint(self._parent_width(), 0), self._finish_close)

    def toggle(self) -> None:
        if self._open:
            self.close()
        else:
            self.open()

    def is_open(self) -> bool:
        return self._open

    def _finish_close(self) -> None:
        self._closing = False
        self.hide()
        self.closed.emit()

    def _parent_width(self) -> int:
        parent = self.parentWidget()
        return parent.width() if parent is not None else self._width

    def _start_x(self) -> int:
        return self._parent_width()

    def _end_x(self) -> int:
        return max(0, self._parent_width() - self._width)

    def _place(self, x: int) -> None:
        parent = self.parentWidget()
        height = parent.height() if parent is not None else self.height()
        self.setGeometry(int(x), 0, self._width, max(1, int(height)))

    def _duration(self) -> int:
        try:
            return int(AppSettings.overlay.drawer_duration)
        except Exception:
            return self.FALLBACK_DURATION

    def _animate_to(self, end: QPoint, finished) -> None:
        self._stop_animation()
        if self._duration() <= 0 or not self.isVisible():
            self.move(end)
            if finished is not None:
                finished()
            return
        animation = QPropertyAnimation(self, b"pos", self)
        animation.setDuration(self._duration())
        animation.setStartValue(self.pos())
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        if finished is not None:
            animation.finished.connect(finished)
        self._animation = animation
        animation.start()

    def _stop_animation(self) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation = None

    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if (
            not self._embedded
            and obj is self.parentWidget()
            and event.type() == QEvent.Resize
            and self._open
        ):
            self._place(self._end_x())
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def update_style(self) -> None:
        """主题切换后刷新标签颜色与全部自绘控件（不重建控件树）。

        标签颜色用**一条面板级样式表**统一下发：逐个 ``QLabel.setStyleSheet``
        会触发每个标签各一次样式重算，主题切换时累计上百毫秒。
        """
        colors = get_design_tokens().colors
        self.close_button.set_color(QColor(colors.text_primary))
        self.setStyleSheet(
            f"QLabel {{ color: {colors.text_primary}; background: transparent; }}"
            f'QLabel[role="hint"] {{ color: {colors.text_muted}; }}'
            f'QFrame[role="divider"] {{ background: {colors.surface_interactive_pressed}; border: none; }}'
        )
        for card in self._theme_cards:
            card.update()
        self.tabs.update()
        self.language_select.update()
        self.menu_mode_select.update()
        self.dark_switch.update()
        self.transparency_slider.update()
        self.glass_strength_slider.update()
        self.background_type_select.update()
        self.background_fit_select.update()
        self.background_toggle.update()
        for thumb in self._recent_thumbs:
            thumb.update()
        self._refresh_background_icon()
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._embedded:
            # 嵌入右侧抽屉时背景由抽屉的 CRegion_Card_Frame 提供，这里不再
            # 画一层自己的面板底色，避免又出现"面板里再套一块背景"。
            return
        tokens = get_design_tokens()
        colors = tokens.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        radius = float(tokens.radius.window)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.moveTo(rect.left() + radius, rect.top())
        path.lineTo(rect.right(), rect.top())
        path.lineTo(rect.right(), rect.bottom())
        path.lineTo(rect.left() + radius, rect.bottom())
        path.arcTo(QRectF(rect.left(), rect.bottom() - 2 * radius, 2 * radius, 2 * radius), 270, -90)
        path.lineTo(rect.left(), rect.top() + radius)
        path.arcTo(QRectF(rect.left(), rect.top(), 2 * radius, 2 * radius), 180, -90)
        path.closeSubpath()

        painter.fillPath(path, QColor(colors.surface_panel))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(colors.surface_interactive_pressed), 1))
        painter.drawPath(path)
        painter.end()


__all__ = ["CAppConfigurator"]
