"""外观配置抽屉：主题、语言、菜单模式与深色模式。

右侧滑入的浮层面板，所有配色在绘制或刷新时实时读取设计令牌与调色板，
切换主题后重绘即生效；语言以目标语言直接选择，不再循环轮替。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from customgui.appcore import (
    LANGUAGE_OPTIONS,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_design_tokens,
    get_theme_manager,
)

from ..custom_ui.close_button import CCloseButton
from ..custom_ui.line_edit.choice import CToggleSwitch
from ..custom_ui.line_edit.select import CSelect
from ..custom_ui.line_edit.toggle_button import CSelectButton
from ..custom_ui.scroll.scroll_area import CScrollArea

#: 主题卡片预览所用的调色板键
_PREVIEW_KEYS = ("custom_dark_one", "custom_bg_one", "custom_context_color", "custom_text_title")
#: 语言选择器显示的原生名称（未列出的语言直接显示语言代码）
_LANGUAGE_LABELS = {
    "zh_cn": "简体中文",
    "zh_tw": "繁體中文",
    "en_us": "English",
    "ja_jp": "日本語",
}


class _ThemeCard(QWidget):
    """可点击的主题卡片：名称 + 四个调色块预览。"""

    clicked = Signal(str)

    def __init__(self, theme_name: str, parent=None):
        super().__init__(parent)
        self._name = theme_name
        self._selected = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(66)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def name(self) -> str:
        return self._name

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        if self._selected != bool(selected):
            self._selected = bool(selected)
            self.update()

    def _preview_colors(self) -> list[str]:
        config = AppThemes.get(self._name)
        data = getattr(config, "data", None)
        if data is None:
            return []
        colors = []
        for key in _PREVIEW_KEYS:
            try:
                colors.append(str(getattr(data, key)))
            except AttributeError:
                continue
        return colors

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        accent = QColor(colors.border_context)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        if self._selected:
            fill = QColor(accent)
            fill.setAlpha(28)
            painter.fillPath(path, fill)
            painter.setPen(QPen(accent, 1.5))
        else:
            painter.fillPath(path, QColor(ColorPalette.custom_dark_two if self._hover else ColorPalette.custom_dark_one))
            painter.setPen(QPen(QColor(colors.surface_interactive_pressed), 1))
        painter.drawPath(path)

        font = QFont(AppSettings.family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(colors.text_active if self._selected else colors.text_primary))
        preview = self._preview_colors()
        text_rect = QRectF(rect.left() + 10, rect.top() + 6, rect.width() - 20, 20)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self._name.replace("_", " ").title())

        # 调色块预览：底色按卡片宽度均分，未取到颜色的槽位留空
        left = rect.left() + 10
        width = max(8.0, (rect.width() - 20) / 4)
        for index, value in enumerate(preview[:4]):
            chip = QRectF(left + index * width, rect.top() + 32, width - 3, 22)
            chip_path = QPainterPath()
            chip_path.addRoundedRect(chip, 4, 4)
            painter.fillPath(chip_path, QColor(value))
            painter.setPen(QPen(QColor(255, 255, 255, 22), 1))
            painter.drawPath(chip_path)
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._name)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CAppConfigurator(QFrame):
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
    # 构建
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self)
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 8, 12, 8)
        header_layout.setSpacing(8)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(2)
        self.header_title = self._register_text("language.UI.ui_Appearance", "外观配置", "header")
        self.header_subtitle = self._register_text("language.UI.ui_AppearanceHint", "主题、语言与界面布局", "hint")
        title_column.addWidget(self.header_title)
        title_column.addWidget(self.header_subtitle)
        header_layout.addLayout(title_column, 1)

        self.close_button = CCloseButton(QColor(get_design_tokens().colors.text_primary), size=28, radius=6, parent=header)
        self.close_button.clicked.connect(self._request_close)
        header_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)
        root.addWidget(header)

        self.content_scroll = CScrollArea(background="transparent", parent=self)
        # 抽屉高度不足时需要明确的滚动位置提示，否则底部配置项不可发现。
        self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(20, 12, 20, 20)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignTop)

        self._build_theme_section(content)
        self._add_divider(content)
        self._build_language_section(content)
        self._add_divider(content)
        self._build_menu_mode_section(content)
        self.content_layout.addStretch(1)

        self.content_scroll.setWidget(content)
        root.addWidget(self.content_scroll, 1)

    def _make_label(self, text: str, role: str) -> QLabel:
        """创建一个随主题刷新颜色的标签；role 为 header / title / hint。"""
        label = QLabel(text, self)
        font = QFont(AppSettings.family)
        if role == "header":
            font.setPixelSize(16)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "title":
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.DemiBold)
        else:
            font.setPixelSize(12)
            label.setProperty("role", "hint")
        label.setFont(font)
        label.setWordWrap(role == "hint")
        return label

    def _register_text(self, key: str, fallback: str, role: str) -> QLabel:
        """创建随语言与主题刷新的标签，并登记资源键。"""
        label = self._make_label(Language.resolve_key(key, fallback), role)
        self._texts[key] = (label, fallback)
        return label

    def _add_section(self, content: QWidget, title_key: str, title_fallback: str, hint_key: str, hint_fallback: str):
        box = QWidget(content)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._register_text(title_key, title_fallback, "title"))
        layout.addWidget(self._register_text(hint_key, hint_fallback, "hint"))
        self.content_layout.addWidget(box)
        return layout

    def _add_divider(self, content: QWidget) -> None:
        divider = QFrame(content)
        divider.setProperty("role", "divider")
        divider.setFixedHeight(1)
        self.content_layout.addWidget(divider)

    def _build_theme_section(self, content: QWidget) -> None:
        layout = self._add_section(
            content,
            "language.UI.ui_Theme",
            "主题",
            "language.UI.ui_ThemeHint",
            "选择一套内置配色方案",
        )
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        names = sorted(AppThemes.keys())
        if "default" in names:
            names.remove("default")
            names.insert(0, "default")
        for index, name in enumerate(names):
            card = _ThemeCard(name)
            card.clicked.connect(self.set_theme)
            self._theme_cards.append(card)
            grid.addWidget(card, index // 2, index % 2)
        layout.addLayout(grid)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 0)
        row_layout.setSpacing(12)
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)
        text_column.addWidget(self._register_text("language.UI.ui_DarkMode", "深色模式", "title"))
        text_column.addWidget(self._register_text("language.UI.ui_DarkModeHint", "开启后使用暗色主题", "hint"))
        row_layout.addLayout(text_column, 1)

        self.dark_switch = CToggleSwitch("")
        self.dark_switch.toggled.connect(self._on_dark_toggled)
        row_layout.addWidget(self.dark_switch, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(row)

    def _build_language_section(self, content: QWidget) -> None:
        layout = self._add_section(
            content,
            "language.UI.ui_Language",
            "语言",
            "language.UI.ui_LanguageHint",
            "选择界面显示语言",
        )
        options = self._language_options()
        labels = [label for _code, label in options]
        current = Language.current()
        value = next((label for code, label in options if code == current), labels[0] if labels else None)
        self.language_select = CSelect(options=labels, value=value, size="sm")
        self.language_select.selectionChanged.connect(self._on_language_selected)
        layout.addWidget(self.language_select)

    def _build_menu_mode_section(self, content: QWidget) -> None:
        layout = self._add_section(
            content,
            "language.UI.ui_MenuMode",
            "菜单模式",
            "language.UI.ui_MenuModeHint",
            "固定展示在内容区旁，浮层覆盖在当前页面之上",
        )
        self.menu_mode_select = CSelectButton(self._menu_mode_labels(), index=0, size="sm")
        self.menu_mode_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.menu_mode_select.selectionChanged.connect(self._on_menu_mode_selected)
        layout.addWidget(self.menu_mode_select)

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
    # 语言
    # ------------------------------------------------------------------
    @staticmethod
    def _language_options() -> list[tuple[str, str]]:
        return [(code, _LANGUAGE_LABELS.get(code, code)) for code in LANGUAGE_OPTIONS]

    @staticmethod
    def _language_label(code: str) -> str:
        return _LANGUAGE_LABELS.get(code, code)

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
        self.menu_mode_select.set_options(self._menu_mode_labels(), index=self.menu_mode_select.current_index(), emit=False)
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
        self.language_select.update()
        self.menu_mode_select.update()
        self.dark_switch.update()
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
