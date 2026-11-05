"""外观配置抽屉的控件树构建。

把 ``CAppConfigurator`` 的界面装配拆出来：抽屉骨架（标题栏 + 滚动内容）、
主题 / 材质 / 语言 / 菜单模式四个分区，以及主题卡片与分区专用的小工具方法。
面板本身只保留状态、信号与交互逻辑。

本模块不持有任何状态：``_ConfigSectionsMixin`` 依赖宿主提供的
``_texts`` / ``_theme_cards`` / ``content_layout`` 等属性，方法名与拆分前一致。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, QStandardPaths, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sllkgui.appcore import (
    LANGUAGE_OPTIONS,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_design_tokens,
    load_user_settings,
    save_user_settings,
)

from ..acrylic import acrylic_transparency, glass_strength
from ..custom_ui.button.button import CButton
from ..custom_ui.close_button import CCloseButton
from ..custom_ui.icon_utils import render_icon
from ..custom_ui.line_edit.choice import CToggleSwitch
from ..custom_ui.line_edit.select import CSelect
from ..custom_ui.line_edit.slider import CSlider
from ..custom_ui.line_edit.toggle_button import CSelectButton
from ..custom_ui.panels.collapse import CollapseAnimator
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


#: 背景图适应模式（与 Windows 个性化设置顺序一致）
_BACKGROUND_FIT_CODES = ("fill", "fit", "stretch", "tile", "center")


class _RecentThumb(QWidget):
    """最近使用背景缩略图：圆角裁切、选中描边、点击回调。"""

    clicked = Signal(str)

    def __init__(self, path: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self._path = str(path)
        self._selected = bool(selected)
        self._hover = False
        self._pixmap = QPixmap(self._path)
        self.setFixedSize(64, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self._path)

    def path(self) -> str:
        return self._path

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(64, 40)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(64, 40)

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)
        painter.fillPath(path, QColor(colors.surface_interactive_pressed))
        if not self._pixmap.isNull():
            painter.save()
            painter.setClipPath(path)
            scaled = self._pixmap.scaled(
                rect.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.left() + (rect.width() - scaled.width()) / 2
            y = rect.top() + (rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()
        border = QColor(colors.border_context) if self._selected else QColor(colors.surface_interactive_pressed)
        if self._hover and not self._selected:
            border = QColor(colors.border_context)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 2 if self._selected else 1))
        painter.drawPath(path)
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
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._path)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _ConfigSectionsMixin:
    """把四个配置分区装配到宿主的 ``content_layout`` 上。

    宿主需提供 ``_texts`` / ``_theme_cards`` / ``content_layout`` 三个属性，
    以及各分区的事件处理器与信号（见 ``CAppConfigurator``）。
    """

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
        self._build_background_section(content)
        self._add_divider(content)
        self._build_material_section(content)
        self._add_divider(content)
        self._build_language_section(content)
        self._add_divider(content)
        self._build_menu_mode_section(content)
        self.content_layout.addStretch(1)

        self.content_scroll.setWidget(content)
        root.addWidget(self.content_scroll, 1)

    def _make_label(self, text: str, role: str) -> QLabel:
        """创建一个随主题刷新颜色的标签；role 为 header / title / hint / value。"""
        label = QLabel(text, self)
        font = QFont(AppSettings.family)
        if role == "header":
            font.setPixelSize(16)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "title":
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "value":
            font.setPixelSize(12)
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

    def _build_material_section(self, content: QWidget) -> None:
        """材质与通透度：透明度 / 亚克力质感强度两枚实时滑块。"""
        layout = self._add_section(
            content,
            "language.UI.ui_Material",
            "材质与通透度",
            "language.UI.ui_MaterialHint",
            "实时调整窗口透明度与亚克力质感",
        )
        self.transparency_slider, self.transparency_value = self._add_slider_row(
            layout,
            "language.UI.ui_Transparency",
            "窗口透明度",
            "language.UI.ui_TransparencyHint",
            "数值越大，桌面内容透出越明显",
            acrylic_transparency(),
        )
        self.transparency_slider.valueChanged.connect(self._on_transparency_changed)
        self.transparency_slider.sliderReleased.connect(lambda _value: self.appearanceCommitted.emit())

        self.glass_strength_slider, self.glass_strength_value = self._add_slider_row(
            layout,
            "language.UI.ui_GlassStrength",
            "亚克力质感强度",
            "language.UI.ui_GlassStrengthHint",
            "数值越大，界面上的模糊材质越明显",
            glass_strength(),
        )
        self.glass_strength_slider.valueChanged.connect(self._on_glass_strength_changed)
        self.glass_strength_slider.sliderReleased.connect(lambda _value: self.appearanceCommitted.emit())

    def _add_slider_row(
        self,
        layout: QVBoxLayout,
        title_key: str,
        title_fallback: str,
        hint_key: str,
        hint_fallback: str,
        value: int,
    ) -> tuple[CSlider, QLabel]:
        """一行滑块：标题 + 百分比数值 + 说明 + 控件本身。"""
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        head = QWidget()
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(8)
        head_layout.addWidget(self._register_text(title_key, title_fallback, "title"), 1)
        value_label = self._make_label(f"{int(value)}%", "value")
        head_layout.addWidget(value_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(head)
        row_layout.addWidget(self._register_text(hint_key, hint_fallback, "hint"))

        slider = CSlider(value=int(value), minimum=0, maximum=100, step=1)
        row_layout.addWidget(slider)
        layout.addWidget(row)
        return slider, value_label

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

    def _build_background_section(self, content: QWidget) -> None:
        """个性化背景手风琴：类型选择、最近图片、浏览、适应模式。

        结构对齐 Windows 设置：标题行常驻（图标 + 标题 + 说明 + 类型下拉 +
        展开箭头），内容区由 ``CollapseAnimator`` 控制展开/收起。
        """
        state = load_user_settings()
        fit = state.get("background_fit")
        self._background_fit = fit if fit in _BACKGROUND_FIT_CODES else "fill"
        path = state.get("background_image")
        self._background_path = str(path) if isinstance(path, str) and Path(path).is_file() else ""
        recent = state.get("background_recent")
        self._background_recent = (
            [str(item) for item in recent if isinstance(item, str) and Path(item).is_file()][:5]
            if isinstance(recent, list)
            else []
        )
        if self._background_path and self._background_path not in self._background_recent:
            self._background_recent.insert(0, self._background_path)
            del self._background_recent[5:]
        self._recent_thumbs: list[_RecentThumb] = []

        card = QFrame(content)
        card.setObjectName("CBackgroundAccordion_Frame")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget(card)
        header.setObjectName("CBackgroundAccordionHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(10)
        self.background_icon = QLabel(header)
        self.background_icon.setFixedSize(24, 24)
        header_layout.addWidget(self.background_icon, 0, Qt.AlignVCenter)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self._register_text("language.UI.ui_Background", "个性化设置背景", "title"))
        text_column.addWidget(
            self._register_text(
                "language.UI.ui_BackgroundHint",
                "图片背景仅作用于当前窗口。",
                "hint",
            )
        )
        header_layout.addLayout(text_column, 1)

        self.background_type_select = CSelect(
            options=self._background_type_labels(),
            value=self._background_type_value(),
            size="sm",
        )
        self.background_type_select.setFixedWidth(84)
        self.background_type_select.selectionChanged.connect(self._on_background_type_selected)
        header_layout.addWidget(self.background_type_select, 0, Qt.AlignVCenter)

        self.background_toggle = CButton(
            "",
            icon="icon_arrow_down",
            variant="text",
            size="sm",
            fixed_width=32,
            icon_size=16,
            parent=header,
        )
        self.background_toggle.clicked.connect(self._toggle_background)
        header_layout.addWidget(self.background_toggle, 0, Qt.AlignVCenter)
        outer.addWidget(header)

        content_wrap = QWidget(card)
        content_wrap.setObjectName("CBackgroundAccordionContent")
        content_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        body = QVBoxLayout(content_wrap)
        body.setContentsMargins(12, 0, 12, 12)
        body.setSpacing(10)
        body.addWidget(self._register_text("language.UI.ui_RecentImages", "最近使用的图像", "title"))
        self._recent_box = QWidget(content_wrap)
        self._recent_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._recent_row = QHBoxLayout(self._recent_box)
        self._recent_row.setContentsMargins(0, 0, 0, 0)
        self._recent_row.setSpacing(8)
        body.addWidget(self._recent_box)
        self.background_empty = self._register_text(
            "language.UI.ui_NoRecentImages", "暂无最近使用的图像", "hint"
        )
        self.background_empty.setParent(self._recent_box)
        body.addWidget(self._row_divider(content_wrap))

        choose_row = QWidget(content_wrap)
        choose_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        choose_row.setMinimumHeight(32)
        choose_layout = QHBoxLayout(choose_row)
        choose_layout.setContentsMargins(0, 0, 0, 0)
        choose_layout.setSpacing(8)
        choose_layout.addWidget(self._register_text("language.UI.ui_ChoosePhoto", "选择一张照片", "title"), 1)
        self.background_browse_button = CButton(
            Language.resolve_key("language.UI.ui_BrowsePhoto", "浏览照片"),
            variant="outlined",
            size="sm",
        )
        self.background_browse_button.clicked.connect(self._choose_background_file)
        choose_layout.addWidget(self.background_browse_button)
        self.background_clear_button = CButton(
            Language.resolve_key("language.UI.ui_ClearBackground", "清除背景"),
            variant="text",
            size="sm",
        )
        self.background_clear_button.clicked.connect(self._clear_background)
        choose_layout.addWidget(self.background_clear_button)
        body.addWidget(choose_row)
        body.addWidget(self._row_divider(content_wrap))

        fit_row = QWidget(content_wrap)
        fit_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fit_row.setMinimumHeight(32)
        fit_layout = QHBoxLayout(fit_row)
        fit_layout.setContentsMargins(0, 0, 0, 0)
        fit_layout.setSpacing(8)
        fit_layout.addWidget(self._register_text("language.UI.ui_BackgroundFit", "为桌面图像选择适应模式", "title"), 1)
        self.background_fit_select = CSelect(
            options=self._background_fit_labels(),
            value=self._background_fit_label(self._background_fit),
            size="sm",
        )
        self.background_fit_select.setFixedWidth(120)
        self.background_fit_select.selectionChanged.connect(self._on_background_fit_selected)
        fit_layout.addWidget(self.background_fit_select)
        body.addWidget(fit_row)

        outer.addWidget(content_wrap)
        self._background_content = content_wrap
        self._background_animator = CollapseAnimator(content_wrap, expanded=False, parent=self)
        self._background_animator.finished.connect(self._on_background_animation_finished)
        self._refresh_recent_thumbs()
        self._sync_background_controls()
        self._sync_background_chevron()
        self._refresh_background_icon()
        self.content_layout.addWidget(card)

    @staticmethod
    def _row_divider(parent: QWidget) -> QFrame:
        line = QFrame(parent)
        line.setProperty("role", "divider")
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _background_type_labels() -> list[str]:
        return [
            Language.resolve_key("language.UI.ui_BackgroundNone", "无"),
            Language.resolve_key("language.UI.ui_BackgroundImage", "图片"),
        ]

    def _background_type_value(self) -> str:
        return self._background_type_labels()[1 if self._background_path else 0]

    @staticmethod
    def _background_fit_labels() -> list[str]:
        return [
            Language.resolve_key("language.UI.ui_FitFill", "填充"),
            Language.resolve_key("language.UI.ui_FitFit", "适应"),
            Language.resolve_key("language.UI.ui_FitStretch", "拉伸"),
            Language.resolve_key("language.UI.ui_FitTile", "平铺"),
            Language.resolve_key("language.UI.ui_FitCenter", "居中"),
        ]

    def _background_fit_label(self, code: str) -> str:
        labels = self._background_fit_labels()
        index = _BACKGROUND_FIT_CODES.index(code) if code in _BACKGROUND_FIT_CODES else 0
        return labels[index]

    def background_path(self) -> str:
        """当前背景图路径（空字符串表示纯色背景）。"""
        return self._background_path

    def background_fit(self) -> str:
        """当前背景图适应模式。"""
        return self._background_fit

    def is_background_expanded(self) -> bool:
        """背景手风琴是否处于展开状态。"""
        return self._background_animator.is_expanded()

    def _toggle_background(self) -> None:
        self._set_background_expanded(not self._background_animator.is_expanded())

    def _background_content_height(self) -> int:
        """内容区完整展开所需高度（布局最小高度 + 安全余量）。"""
        layout = self._background_content.layout()
        if layout is not None:
            layout.activate()
            return max(self._background_animator.content_height(), layout.minimumSize().height()) + 8
        return self._background_animator.content_height()

    def _set_background_expanded(self, expanded: bool, animate: bool = True) -> None:
        if not expanded:
            # 收起前先解除最小高度，否则 maximumHeight=0 会被最小高度顶住
            self._background_content.setMinimumHeight(0)
        self._background_animator.set_expanded(bool(expanded), animate)
        if expanded:
            self._background_content.show()
            self._background_content.setMaximumHeight(16777215)
            if not animate:
                self._background_content.setMinimumHeight(self._background_content_height())
            parent = self._background_content.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().activate()
            self._background_content.updateGeometry()
        self._sync_background_chevron()

    def _on_background_animation_finished(self, expanded: bool) -> None:
        # QWidget 的 sizeHint 在隐藏期间可能被缓存为 0；展开结束后显式给最小高度，
        # 确保最近图片行、浏览行与适应模式行都拿到应有的空间。
        self._background_content.setMinimumHeight(self._background_content_height() if expanded else 0)
        self._background_content.updateGeometry()
        self._sync_background_chevron()

    def _sync_background_chevron(self) -> None:
        expanded = self._background_animator.is_expanded()
        self.background_toggle.set_icon("icon_arrow_up" if expanded else "icon_arrow_down")
        key = "language.UI.ui_BackgroundCollapse" if expanded else "language.UI.ui_BackgroundExpand"
        fallback = "收起背景设置" if expanded else "展开背景设置"
        self.background_toggle.setToolTip(Language.resolve_key(key, fallback))

    def _refresh_background_icon(self) -> None:
        pixmap = render_icon(
            "icon_image",
            QColor(get_design_tokens().colors.text_primary),
            22,
            self.devicePixelRatioF(),
        )
        if pixmap is not None:
            self.background_icon.setPixmap(pixmap)

    def _refresh_recent_thumbs(self) -> None:
        for thumb in self._recent_thumbs:
            thumb.setParent(None)
            thumb.deleteLater()
        self._recent_thumbs = []
        while self._recent_row.count():
            item = self._recent_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                if widget is self.background_empty:
                    widget.hide()
                else:
                    widget.setParent(None)
                    widget.deleteLater()
        shown = 0
        for path in self._background_recent:
            if not Path(path).is_file():
                continue
            thumb = _RecentThumb(path, selected=path == self._background_path, parent=self._recent_box)
            thumb.clicked.connect(self._apply_background_path)
            self._recent_row.addWidget(thumb)
            self._recent_thumbs.append(thumb)
            shown += 1
        if shown == 0:
            self.background_empty.show()
            self._recent_row.addWidget(self.background_empty)
            self._recent_box.setMinimumHeight(20)
        else:
            self.background_empty.hide()
            self._recent_box.setMinimumHeight(40)
        self._recent_row.addStretch(1)
        self._recent_box.updateGeometry()

    def _sync_background_controls(self) -> None:
        self.background_type_select.set_value(self._background_type_value(), emit=False)
        self.background_fit_select.set_value(self._background_fit_label(self._background_fit), emit=False)
        has_image = bool(self._background_path)
        self.background_fit_select.setEnabled(has_image)
        self.background_clear_button.setEnabled(has_image)
        self._refresh_recent_thumbs()

    def _on_background_type_selected(self, label) -> None:
        labels = self._background_type_labels()
        if label == labels[0]:
            self._clear_background()
        else:
            self._set_background_expanded(True)

    def _on_background_fit_selected(self, label) -> None:
        labels = self._background_fit_labels()
        if label not in labels:
            return
        code = _BACKGROUND_FIT_CODES[labels.index(label)]
        if code == self._background_fit:
            return
        self._background_fit = code
        save_user_settings(background_fit=code)
        if self._background_path:
            self.backgroundChanged.emit(self._background_path, code)

    def _choose_background_file(self) -> None:
        start = (
            str(Path(self._background_path).parent)
            if self._background_path
            else QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        )
        path, _selected = QFileDialog.getOpenFileName(
            self,
            Language.resolve_key("language.UI.ui_ChoosePhoto", "选择一张照片"),
            start,
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif)",
        )
        if path:
            self._apply_background_path(path)

    def _apply_background_path(self, path: str) -> bool:
        target = str(path)
        if not Path(target).is_file() or QPixmap(target).isNull():
            return False
        self._background_path = target
        self._background_recent = [target] + [item for item in self._background_recent if item != target]
        del self._background_recent[5:]
        save_user_settings(
            background_image=target,
            background_fit=self._background_fit,
            background_recent=self._background_recent,
        )
        self._sync_background_controls()
        self._set_background_expanded(True)
        self.backgroundChanged.emit(target, self._background_fit)
        return True

    def _clear_background(self) -> None:
        if not self._background_path:
            return
        self._background_path = ""
        save_user_settings(background_image="")
        self._sync_background_controls()
        self.backgroundChanged.emit("", self._background_fit)

    def _refresh_background_texts(self) -> None:
        self.background_type_select.set_options(self._background_type_labels(), keep_value=True)
        self.background_fit_select.set_options(self._background_fit_labels(), keep_value=True)
        self.background_browse_button.setText(Language.resolve_key("language.UI.ui_BrowsePhoto", "浏览照片"))
        self.background_clear_button.setText(Language.resolve_key("language.UI.ui_ClearBackground", "清除背景"))
        self._sync_background_controls()
        self._sync_background_chevron()

    @staticmethod
    def _language_options() -> list[tuple[str, str]]:
        return [(code, _LANGUAGE_LABELS.get(code, code)) for code in LANGUAGE_OPTIONS]

    @staticmethod
    def _language_label(code: str) -> str:
        return _LANGUAGE_LABELS.get(code, code)
