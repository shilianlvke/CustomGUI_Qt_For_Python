"""左抽屉设置页：概览 / 运行环境 / 目录三个单屏子页。

排版按 Fluent 设置卡片组织：每页是一张圆角卡片，卡片内是「键（弱化）—值」
信息行；分段控件已经表达当前页，页面内不再重复写大标题。外观配置仍由标题栏
色盘入口负责，这里只展示状态与目录。

宿主应用追加的区块（``add_section``）同样包进一张同款卡片，保证视觉一致。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import PySide6
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sllkgui import __version__
from sllkgui.appcore import (
    AppSettings,
    Language,
    get_design_tokens,
    get_plugin_registry,
    get_theme_manager,
    user_settings_path,
)

from ...custom_ui import CButton, CSelectButton
from ...styles import card_stroke_color, card_surface_color, qss_color

#: 信息行键列宽度：四种语言的最长键（「运行环境」等）都放得下
_KEY_WIDTH = 76
#: 卡片内边距（左、上、右、下）与行距
_CARD_MARGINS = (12, 10, 12, 10)
_CARD_SPACING = 8
#: 主面板与页面间距
_PANEL_MARGINS = (16, 12, 16, 16)
_PANEL_SPACING = 12
_ROW_SPACING = 6


class _ElidedLabel(QLabel):
    """按实际宽度中部省略的值标签，tooltip 保留全文。"""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        # 水平方向忽略 sizeHint：否则长路径会撑破信息行、把值列顶出卡片
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        width = max(0, self.width())
        self.setText(self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, width))


class CSettingsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CSettingsPanel")
        self._keyed: list[tuple[QLabel, str, str]] = []
        self._buttons: list[tuple[QWidget, str, str]] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*_PANEL_MARGINS)
        self._layout.setSpacing(_PANEL_SPACING)
        self._build()
        get_theme_manager().subscribe(self._apply_theme)
        Language.subscribe(self._apply_language)
        self._apply_theme()
        self._refresh_status()

    # ------------------------------------------------------------------
    # 对外：宿主应用追加自己的设置区块
    # ------------------------------------------------------------------
    def add_section(self, widget: QWidget, page: str = "overview") -> None:
        """把宿主区块包进一张设置卡片后追加到指定子页。"""
        target = {
            "environment": self._extra_environment,
            "folders": self._extra_folders,
        }.get(page, self._extra_overview)
        card, layout = self._new_card()
        layout.addWidget(widget)
        target.addWidget(card)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self._tabs = CSelectButton(self._tab_labels(), index=0, size="sm")
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._layout.addWidget(self._tabs)

        self._stack = QStackedWidget()
        self._overview, self._overview_layout = self._page()
        self._environment, self._environment_layout = self._page()
        self._folders, self._folders_layout = self._page()
        for page in (self._overview, self._environment, self._folders):
            self._stack.addWidget(page)
        self._layout.addWidget(self._stack, 1)
        self._tabs.selectionChanged.connect(self._stack.setCurrentIndex)

        self._build_overview()
        self._build_environment()
        self._build_folders()

        # 宿主区块的插入位建在内置内容之后，保证卡片顺序与底部弹性空间正确
        self._extra_overview = self._extra_slot(self._overview_layout)
        self._extra_environment = self._extra_slot(self._environment_layout)
        self._extra_folders = self._extra_slot(self._folders_layout)

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_PANEL_SPACING)
        return page, layout

    def _extra_slot(self, page_layout: QVBoxLayout) -> QVBoxLayout:
        """宿主区块的插入位：位于内置卡片之后、底部弹性空间之前。"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_PANEL_SPACING)
        page_layout.addLayout(layout)
        page_layout.addStretch(1)
        return layout

    def _new_card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("CSettingsCard_Frame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*_CARD_MARGINS)
        layout.setSpacing(_CARD_SPACING)
        return card, layout

    def _card(self, page_layout: QVBoxLayout) -> QVBoxLayout:
        card, layout = self._new_card()
        page_layout.addWidget(card)
        return layout

    @staticmethod
    def _tab_labels() -> list[str]:
        return [
            str(Language.resolve_key("language.UI.ui_SettingsOverview", "概览")),
            str(Language.resolve_key("language.UI.ui_SettingsEnvironment", "环境")),
            str(Language.resolve_key("language.UI.ui_SettingsFolders", "目录")),
        ]

    def _build_overview(self) -> None:
        card = self._card(self._overview_layout)
        self._add_row(card, self._key_label("language.UI.ui_SettingsVersion", "版本"), self._value(__version__))

        self._status = self._value("")
        self._add_row(card, self._key_label("language.UI.ui_SettingsStatus", "状态"), self._status)

        self._page_count = self._value("0")
        self._add_row(card, self._key_label("language.UI.ui_SettingsPages", "页面"), self._page_count)

    def _build_environment(self) -> None:
        card = self._card(self._environment_layout)
        self._add_row(card, self._key_label(None, "Python"), self._value(platform.python_version()))
        self._add_row(card, self._key_label(None, "Qt"), self._value(f"PySide6 {PySide6.__version__}"))
        system = f"{platform.system()} {platform.release()}".strip()
        self._add_row(card, self._key_label(None, "OS"), self._value(system))

    def _build_folders(self) -> None:
        card = self._card(self._folders_layout)
        self._add_row(
            card,
            self._key_label("language.UI.ui_SettingsDataDir", "数据目录"),
            self._path_label(self._data_root()),
        )
        self._add_row(
            card,
            self._key_label("language.UI.ui_SettingsLogDir", "日志目录"),
            self._path_label(self._data_root() / "logs"),
        )

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(6)
        open_data = self._button("language.UI.ui_SettingsOpenData", "打开数据目录")
        open_logs = self._button("language.UI.ui_SettingsOpenLogs", "打开日志目录")
        open_data.clicked.connect(lambda: self._open(self._data_root()))
        open_logs.clicked.connect(lambda: self._open(self._data_root() / "logs"))
        buttons.addStretch(1)
        buttons.addWidget(open_data)
        buttons.addWidget(open_logs)
        card.addLayout(buttons)

        self._folders_layout.addWidget(
            self._hint_label("language.UI.ui_SettingsAppearanceHint", "外观配置请使用标题栏色盘")
        )

    # ------------------------------------------------------------------
    # 小部件
    # ------------------------------------------------------------------
    def _label(self, text: str, role: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", role)
        label.setWordWrap(role == "hint")
        font = QFont(AppSettings.family)
        font.setPointSize(8 if role in {"key", "hint"} else 9)
        label.setFont(font)
        return label

    def _value(self, text: str) -> QLabel:
        label = self._label(text, "value")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _key_label(self, key: str | None, default: str) -> QLabel:
        text = str(Language.resolve_key(key, default)) if key else default
        label = self._label(text, "key")
        label.setFixedWidth(_KEY_WIDTH)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        if key:
            self._keyed.append((label, key, default))
        return label

    def _hint_label(self, key: str, default: str) -> QLabel:
        label = self._label(str(Language.resolve_key(key, default)), "hint")
        self._keyed.append((label, key, default))
        return label

    def _button(self, key: str, default: str) -> CButton:
        button = CButton(
            str(Language.resolve_key(key, default)),
            severity="secondary",
            variant="outlined",
            size="sm",
        )
        self._buttons.append((button, key, default))
        return button

    def _path_label(self, path: Path) -> _ElidedLabel:
        label = _ElidedLabel(self._display_path(path))
        label.setProperty("role", "value")
        font = QFont(AppSettings.family)
        font.setPointSize(9)
        label.setFont(font)
        return label

    def _add_row(self, card_layout: QVBoxLayout, key_widget: QLabel, value_widget: QWidget) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_ROW_SPACING)
        row.addWidget(key_widget, 0, Qt.AlignTop)
        row.addWidget(value_widget, 1)
        card_layout.addLayout(row)

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

    # ------------------------------------------------------------------
    # 状态与主题
    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        super().showEvent(event)
        self._refresh_status()

    def _refresh_status(self) -> None:
        theme = get_theme_manager().current()
        language = Language.current()
        self._status.setText(f"{theme} · {language}")
        try:
            count = len(get_plugin_registry().page_plugins())
        except Exception:
            count = 0
        self._page_count.setText(str(count))

    def _apply_language(self) -> None:
        for label, key, default in self._keyed:
            label.setText(str(Language.resolve_key(key, default)))
        for button, key, default in self._buttons:
            button.setText(str(Language.resolve_key(key, default)))
        self._tabs.set_options(self._tab_labels(), index=self._tabs.current_index())
        self._refresh_status()

    def _apply_theme(self) -> None:
        """一条面板级样式表统一下发卡片与三种文字角色色（不逐个标签设样式）。"""
        tokens = get_design_tokens()
        colors = tokens.colors
        self.setStyleSheet(
            f"#CSettingsCard_Frame {{"
            f" background-color: {qss_color(card_surface_color())};"
            f" border: 1px solid {qss_color(card_stroke_color())};"
            f" border-radius: {tokens.radius.control}px; }}"
            f'#CSettingsPanel QLabel[role="key"] {{ color: {colors.text_muted}; background: transparent; }}'
            f'#CSettingsPanel QLabel[role="value"] {{ color: {colors.text_primary}; background: transparent; }}'
            f'#CSettingsPanel QLabel[role="hint"] {{ color: {colors.text_muted}; background: transparent; }}'
        )
        self._refresh_status()

    # ------------------------------------------------------------------
    def _data_root(self) -> Path:
        return user_settings_path().parent.parent

    @staticmethod
    def _open(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


__all__ = ["CSettingsPanel"]
