"""外观配置抽屉的控件树构建。

把 ``CAppConfigurator`` 的界面装配拆出来：抽屉骨架（标题栏 + 滚动内容）、
主题 / 材质 / 语言 / 菜单模式四个分区，以及主题卡片与分区专用的小工具方法。
面板本身只保留状态、信号与交互逻辑。

本模块不持有任何状态：``_ConfigSectionsMixin`` 依赖宿主提供的
``_texts`` / ``_theme_cards`` / ``content_layout`` 等属性，方法名与拆分前一致。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from customgui.appcore import (
    LANGUAGE_OPTIONS,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_design_tokens,
)

from ..acrylic import acrylic_transparency, glass_strength
from ..custom_ui.close_button import CCloseButton
from ..custom_ui.line_edit.choice import CToggleSwitch
from ..custom_ui.line_edit.select import CSelect
from ..custom_ui.line_edit.slider import CSlider
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

    @staticmethod
    def _language_options() -> list[tuple[str, str]]:
        return [(code, _LANGUAGE_LABELS.get(code, code)) for code in LANGUAGE_OPTIONS]

    @staticmethod
    def _language_label(code: str) -> str:
        return _LANGUAGE_LABELS.get(code, code)
