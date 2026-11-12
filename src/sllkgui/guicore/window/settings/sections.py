"""设置抽屉的控件树构建。

把 ``CSettingsDrawer`` 的界面装配拆出来：抽屉骨架（标题栏 + 分段导航 +
软件信息 / 外观 / 界面对应子页）、各设置分区，以及主题卡片与专用小工具方法。
面板本身只保留状态、信号与交互逻辑。

本模块不持有跨页状态：``_SettingsSectionsMixin`` 依赖宿主提供的
``_texts`` / ``_theme_cards`` 等属性。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import PySide6
from PySide6.QtCore import QRectF, QSize, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QImageReader,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sllkgui import __version__
from sllkgui.appcore import (
    LANGUAGE_OPTIONS,
    AppSettings,
    AppThemes,
    ColorPalette,
    Language,
    get_design_tokens,
    get_theme_manager,
    load_user_settings,
    save_user_settings,
    user_settings_path,
)

from ...acrylic import acrylic_transparency, glass_strength
from ...custom_ui.button.button import CButton
from ...custom_ui.close_button import CCloseButton
from ...custom_ui.icon_utils import render_icon
from ...custom_ui.line_edit.choice import CToggleSwitch
from ...custom_ui.line_edit.select import CSelect
from ...custom_ui.line_edit.slider import CSlider
from ...custom_ui.line_edit.toggle_button import CSelectButton
from ...custom_ui.panels.collapse import CollapseAnimator

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
            surface = colors.surface_interactive_hover if self._hover else colors.surface_card
            painter.fillPath(path, QColor(surface))
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
            chip_border = QColor(ColorPalette.custom_white)
            chip_border.setAlpha(22)
            painter.setPen(QPen(chip_border, 1))
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


def _load_thumbnail(path: str) -> QPixmap:
    """按缩略图目标尺寸解码图片，避免把整张 4K 壁纸读进内存。

    直接 ``QPixmap(path)`` 会完整解码原图：5 张最近背景就可能常驻上百 MB。
    这里用 ``QImageReader`` 在解码阶段就缩放；按 2 倍目标尺寸读取，兼顾
    高 DPI 清晰度。
    """
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    natural = reader.size()
    if natural.isValid() and natural.width() > 0 and natural.height() > 0:
        target = QSize(64 * 2, 40 * 2)
        reader.setScaledSize(natural.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding))
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


class _RecentThumb(QWidget):
    """最近使用背景缩略图：圆角裁切、选中描边、点击回调。"""

    clicked = Signal(str)

    def __init__(self, path: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self._path = str(path)
        self._selected = bool(selected)
        self._hover = False
        self._pixmap = _load_thumbnail(self._path)
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


class _ElidedPathLabel(QLabel):
    """按实际宽度中部省略的路径值；tooltip 保留全文。"""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "value")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = QFont(AppSettings.family)
        font.setPixelSize(11)
        self.setFont(font)
        self._full_text = ""
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._apply_elide()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        self.setText(
            self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, max(0, self.width()))
        )


class _SettingsSectionsMixin:
    """把设置分区装配成「软件信息 / 外观 / 界面」三个子页。

    宿主需提供 ``_texts`` / ``_theme_cards`` 两个属性，以及各分区的
    事件处理器与信号（见 ``CSettingsDrawer``）。
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
        self.header_title = self._register_text("language.UI.ui_Settings", "设置", "header")
        self.header_subtitle = self._register_text(
            "language.UI.ui_SettingsSubtitle", "软件、外观与界面", "hint"
        )
        title_column.addWidget(self.header_title)
        title_column.addWidget(self.header_subtitle)
        header_layout.addLayout(title_column, 1)

        self.close_button = CCloseButton(QColor(get_design_tokens().colors.text_primary), size=28, radius=6, parent=header)
        self.close_button.clicked.connect(self._request_close)
        header_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)
        root.addWidget(header)

        tabs_wrap = QWidget(self)
        tabs_layout = QHBoxLayout(tabs_wrap)
        tabs_layout.setContentsMargins(20, 0, 20, 10)
        tabs_layout.setSpacing(0)
        self.tabs = CSelectButton(self._tab_labels(), index=0, size="sm")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tabs.selectionChanged.connect(self._switch_page)
        tabs_layout.addWidget(self.tabs)
        root.addWidget(tabs_wrap)

        self.stack = QStackedWidget(self)
        software_page, software_layout = self._new_scroll_page()
        appearance_page, appearance_layout = self._new_scroll_page()
        interface_page, interface_layout = self._new_page()

        self._build_software_sections(software_layout)
        software_layout.addStretch(1)

        self._build_theme_section(appearance_layout)
        self._add_divider(appearance_layout)
        self._build_material_section(appearance_layout)
        self._add_divider(appearance_layout)
        self._build_background_section(appearance_layout)
        appearance_layout.addStretch(1)

        self._build_language_section(interface_layout)
        self._add_divider(interface_layout)
        self._build_menu_mode_section(interface_layout)
        self._add_divider(interface_layout)
        self._build_drawer_mode_section(interface_layout)
        interface_layout.addStretch(1)

        for page in (software_page, appearance_page, interface_page):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)
        self._refresh_software_info()

    def _new_page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 8, 20, 20)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)
        return page, layout

    def _new_scroll_page(self) -> tuple[QWidget, QVBoxLayout]:
        """可滚动的单屏子页：内容高于抽屉时滚动，不压缩分区间距。"""
        page = QWidget(self)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            " QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 8, 20, 20)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        return page, layout

    @staticmethod
    def _tab_labels() -> list[str]:
        return [
            str(Language.resolve_key("language.UI.ui_SettingsSoftware", "软件信息")),
            str(Language.resolve_key("language.UI.ui_TabAppearance", "外观")),
            str(Language.resolve_key("language.UI.ui_TabInterface", "界面")),
        ]

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(max(0, min(self.stack.count() - 1, int(index))))

    def _make_label(self, text: str, role: str) -> QLabel:
        """创建一个随主题刷新颜色的标签；role 为 header / title / card_title / key / hint / value。"""
        label = QLabel(text, self)
        font = QFont(AppSettings.family)
        if role == "header":
            font.setPixelSize(16)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "title":
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "card_title":
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "value":
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.DemiBold)
        elif role == "key":
            font.setPixelSize(11)
            label.setProperty("role", "key")
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

    def _add_section(self, target: QVBoxLayout, title_key: str, title_fallback: str, hint_key: str, hint_fallback: str):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._register_text(title_key, title_fallback, "title"))
        layout.addWidget(self._register_text(hint_key, hint_fallback, "hint"))
        target.addWidget(box)
        return layout

    def _add_divider(self, target: QVBoxLayout) -> None:
        divider = QFrame()
        divider.setProperty("role", "divider")
        divider.setFixedHeight(1)
        target.addWidget(divider)

    # ------------------------------------------------------------------
    # 软件信息
    # ------------------------------------------------------------------
    def _build_software_sections(self, target: QVBoxLayout) -> None:
        software = self._settings_card(target, None, "SLLKGUI")
        self._software_version = self._value_label(__version__)
        self._software_status = self._value_label("")
        self._software_pages = self._value_label("0")
        self._add_info_row(
            software,
            self._key_label("language.UI.ui_SettingsVersion", "版本"),
            self._software_version,
        )
        self._add_info_row(
            software,
            self._key_label("language.UI.ui_SettingsStatus", "状态"),
            self._software_status,
        )
        self._add_info_row(
            software,
            self._key_label("language.UI.ui_SettingsPages", "页面"),
            self._software_pages,
        )

        environment = self._settings_card(target, "language.UI.ui_SettingsEnvironment", "运行环境")
        self._add_info_row(environment, self._key_label(None, "Python"), self._value_label(platform.python_version()))
        self._add_info_row(
            environment,
            self._key_label(None, "Qt"),
            self._value_label(f"PySide6 {PySide6.__version__}"),
        )
        self._add_info_row(
            environment,
            self._key_label(None, "OS"),
            self._value_label(f"{platform.system()} {platform.release()}".strip()),
        )

        folders = self._settings_card(target, "language.UI.ui_SettingsFolders", "目录")
        self._software_data_dir = _ElidedPathLabel(self._display_path(self._data_root()))
        self._software_log_dir = _ElidedPathLabel(self._display_path(self._data_root() / "logs"))
        self._add_info_row(
            folders,
            self._key_label("language.UI.ui_SettingsDataDir", "数据目录"),
            self._software_data_dir,
        )
        self._add_info_row(
            folders,
            self._key_label("language.UI.ui_SettingsLogDir", "日志目录"),
            self._software_log_dir,
        )

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setSpacing(6)
        actions.addStretch(1)
        open_data = self._action_button("language.UI.ui_SettingsOpenData", "打开数据目录")
        open_logs = self._action_button("language.UI.ui_SettingsOpenLogs", "打开日志目录")
        open_data.clicked.connect(lambda: self._open_path(self._data_root()))
        open_logs.clicked.connect(lambda: self._open_path(self._data_root() / "logs"))
        actions.addWidget(open_data)
        actions.addWidget(open_logs)
        folders.addLayout(actions)

    def _settings_card(self, target: QVBoxLayout, title_key: str | None, title_fallback: str) -> QVBoxLayout:
        card = QFrame()
        card.setObjectName("CSettingsCard_Frame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        title = self._register_text(title_key, title_fallback, "card_title") if title_key else self._make_label(
            title_fallback, "card_title"
        )
        layout.addWidget(title)
        target.addWidget(card)
        return layout

    def _add_info_row(self, target: QVBoxLayout, key: QLabel, value: QWidget) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(key, 0, Qt.AlignTop)
        row.addWidget(value, 1)
        target.addLayout(row)

    def _key_label(self, key: str | None, fallback: str) -> QLabel:
        label = self._register_text(key, fallback, "key") if key else self._make_label(fallback, "key")
        label.setFixedWidth(64)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _value_label(self, text: str) -> QLabel:
        label = self._make_label(text, "value")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        return label

    def _action_button(self, key: str, fallback: str) -> CButton:
        button = CButton(
            str(Language.resolve_key(key, fallback)),
            severity="secondary",
            variant="outlined",
            size="sm",
        )
        self._buttons.append((button, key, fallback))
        return button

    def _refresh_software_info(self) -> None:
        if not hasattr(self, "_software_status"):
            return
        self._software_status.setText(f"{get_theme_manager().current()} · {Language.current()}")
        try:
            from sllkgui.gallery.registry import current_registry

            registry = current_registry()
            count = registry.surface_count() if registry is not None else 0
        except Exception:  # noqa: BLE001 - 状态栏失败不影响设置页
            count = 0
        self._software_pages.setText(str(count))

    def _build_theme_section(self, target: QVBoxLayout) -> None:
        layout = self._add_section(
            target,
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

    def _build_material_section(self, target: QVBoxLayout) -> None:
        """材质与通透度：透明度 / 亚克力质感强度两枚实时滑块。"""
        layout = self._add_section(
            target,
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

    def _build_language_section(self, target: QVBoxLayout) -> None:
        layout = self._add_section(
            target,
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

    def _build_menu_mode_section(self, target: QVBoxLayout) -> None:
        layout = self._add_section(
            target,
            "language.UI.ui_MenuMode",
            "菜单模式",
            "language.UI.ui_MenuModeHint",
            "固定展示在内容区旁，浮层覆盖在当前页面之上",
        )
        self.menu_mode_select = CSelectButton(self._menu_mode_labels(), index=0, size="sm")
        self.menu_mode_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.menu_mode_select.selectionChanged.connect(self._on_menu_mode_selected)
        layout.addWidget(self.menu_mode_select)

    def _build_drawer_mode_section(self, target: QVBoxLayout) -> None:
        """四向抽屉（左 / 右 / 上 / 下）共用的布局模式：固定占位或浮层覆盖。"""
        layout = self._add_section(
            target,
            "language.UI.ui_DrawerMode",
            "抽屉模式",
            "language.UI.ui_DrawerModeHint",
            "四个方向的抽屉统一固定占位，或浮层覆盖在当前页面之上",
        )
        self.drawer_mode_select = CSelectButton(self._drawer_mode_labels(), index=0, size="sm")
        self.drawer_mode_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.drawer_mode_select.selectionChanged.connect(self._on_drawer_mode_selected)
        layout.addWidget(self.drawer_mode_select)

    def _build_background_section(self, target: QVBoxLayout) -> None:
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

        card = QFrame()
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
        target.addWidget(card)

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
    def _data_root() -> Path:
        return user_settings_path().parent.parent

    @staticmethod
    def _display_path(path: Path) -> str:
        for env_name, prefix in (("APPDATA", "%APPDATA%"), ("LOCALAPPDATA", "%LOCALAPPDATA%")):
            base = os.getenv(env_name, "").strip()
            if not base:
                continue
            try:
                return f"{prefix}\\{path.relative_to(Path(base))}"
            except ValueError:
                continue
        try:
            return f"~\\{path.relative_to(Path.home())}"
        except ValueError:
            return str(path)

    @staticmethod
    def _open_path(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @staticmethod
    def _language_options() -> list[tuple[str, str]]:
        return [(code, _LANGUAGE_LABELS.get(code, code)) for code in LANGUAGE_OPTIONS]

    @staticmethod
    def _language_label(code: str) -> str:
        return _LANGUAGE_LABELS.get(code, code)
