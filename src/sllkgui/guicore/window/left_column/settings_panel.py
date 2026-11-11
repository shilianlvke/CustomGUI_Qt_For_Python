"""左抽屉设置页：概览与目录两个单屏子页。

外观配置仍由标题栏色盘入口负责，这里只展示状态与目录，不重复放置
主题/语言/强调色控件。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import PySide6
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from sllkgui import __version__
from sllkgui.appcore import (
    AppSettings,
    ColorPalette,
    Language,
    get_plugin_registry,
    get_theme_manager,
    user_settings_path,
)

from ...custom_ui import CButton, CHDiv, CSelectButton


class CSettingsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CSettingsPanel")
        self._styled: list[tuple[QLabel, str]] = []
        self._keyed: list[tuple[QLabel, str, str]] = []
        self._buttons: list[tuple[QWidget, str, str]] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(6)
        self._build()
        get_theme_manager().subscribe(self._apply_theme)
        Language.subscribe(self._apply_language)
        self._apply_theme()
        self._refresh_status()

    # ------------------------------------------------------------------
    # 对外：宿主应用追加自己的设置区块
    # ------------------------------------------------------------------
    def add_section(self, widget: QWidget, page: str = "overview") -> None:
        target = {
            "environment": self._extra_environment,
            "folders": self._extra_folders,
        }.get(page, self._extra_overview)
        target.addWidget(CHDiv())
        target.addWidget(widget)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self._layout.addWidget(self._label("SLLKGUI", "eyebrow"))
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

        self._extra_overview = QVBoxLayout()
        self._extra_overview.setContentsMargins(0, 0, 0, 0)
        self._extra_overview.setSpacing(6)
        self._extra_environment = QVBoxLayout()
        self._extra_environment.setContentsMargins(0, 0, 0, 0)
        self._extra_environment.setSpacing(6)
        self._extra_folders = QVBoxLayout()
        self._extra_folders.setContentsMargins(0, 0, 0, 0)
        self._extra_folders.setSpacing(6)

        self._build_overview()
        self._build_environment()
        self._build_folders()

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        return page, layout

    @staticmethod
    def _tab_labels() -> list[str]:
        return [
            str(Language.resolve_key("language.UI.ui_SettingsOverview", "概览")),
            str(Language.resolve_key("language.UI.ui_SettingsEnvironment", "环境")),
            str(Language.resolve_key("language.UI.ui_SettingsFolders", "目录")),
        ]

    def _build_overview(self) -> None:
        layout = self._overview_layout
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsSoftware", "软件信息", "title"))
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsVersion", "版本", "caption"))
        layout.addWidget(self._label(__version__, "value"))
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsStatus", "状态", "caption"))
        self._status = self._label("", "value")
        layout.addWidget(self._status)
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsPages", "页面", "caption"))
        self._page_count = self._label("0", "value")
        layout.addWidget(self._page_count)
        layout.addLayout(self._extra_overview)
        layout.addStretch(1)

    def _build_environment(self) -> None:
        layout = self._environment_layout
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsEnvironment", "运行环境", "title"))
        layout.addWidget(self._label(f"Python {platform.python_version()}", "value"))
        layout.addWidget(self._label(f"PySide6 {PySide6.__version__}", "value"))
        layout.addWidget(self._label(f"{platform.system()} {platform.release()}", "value"))
        layout.addLayout(self._extra_environment)
        layout.addStretch(1)

    def _build_folders(self) -> None:
        layout = self._folders_layout
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsFolders", "目录", "title"))
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsDataDir", "数据目录", "caption"))
        layout.addWidget(self._path_label(self._data_root()))
        layout.addWidget(self._keyed_label("language.UI.ui_SettingsLogDir", "日志目录", "caption"))
        layout.addWidget(self._path_label(self._data_root() / "logs"))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 4, 0, 0)
        buttons.setSpacing(6)
        open_data = CButton(
            str(Language.resolve_key("language.UI.ui_SettingsOpenData", "打开数据目录")),
            severity="secondary",
            variant="outlined",
            size="sm",
        )
        open_logs = CButton(
            str(Language.resolve_key("language.UI.ui_SettingsOpenLogs", "打开日志目录")),
            severity="secondary",
            variant="outlined",
            size="sm",
        )
        self._buttons.append((open_data, "language.UI.ui_SettingsOpenData", "打开数据目录"))
        self._buttons.append((open_logs, "language.UI.ui_SettingsOpenLogs", "打开日志目录"))
        open_data.clicked.connect(lambda: self._open(self._data_root()))
        open_logs.clicked.connect(lambda: self._open(self._data_root() / "logs"))
        buttons.addWidget(open_data)
        buttons.addWidget(open_logs)
        layout.addLayout(buttons)
        layout.addWidget(
            self._keyed_label(
                "language.UI.ui_SettingsAppearanceHint",
                "外观配置请使用标题栏色盘",
                "caption",
            )
        )
        layout.addLayout(self._extra_folders)
        layout.addStretch(1)

    def _keyed_text(self, key: str, default: str) -> str:
        return str(Language.resolve_key(key, default))

    def _label(self, text: str, role: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        size = {"eyebrow": 8, "title": 10, "caption": 8, "value": 9}.get(role, 9)
        weight = QFont.Weight.DemiBold if role in {"eyebrow", "title"} else QFont.Weight.Normal
        label.setFont(QFont(AppSettings.family, size, weight))
        self._styled.append((label, role))
        return label

    def _keyed_label(self, key: str, default: str, role: str) -> QLabel:
        label = self._label(self._keyed_text(key, default), role)
        self._keyed.append((label, key, default))
        return label

    def _path_label(self, path: Path) -> QLabel:
        full = str(path)
        label = self._label(self._display_path(path), "value")
        label.setToolTip(full)
        metrics = QFontMetrics(label.font())
        label.setText(metrics.elidedText(label.text(), Qt.TextElideMode.ElideMiddle, 185))
        return label

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
            label.setText(self._keyed_text(key, default))
        for button, key, default in self._buttons:
            button.setText(self._keyed_text(key, default))
        self._tabs.set_options(self._tab_labels(), index=self._tabs.current_index())
        self._refresh_status()

    def _apply_theme(self) -> None:
        colors = {
            "eyebrow": ColorPalette.custom_context_color,
            "title": ColorPalette.custom_text_title,
            "caption": ColorPalette.custom_text_description,
            "value": ColorPalette.custom_text_foreground,
        }
        for label, role in self._styled:
            label.setStyleSheet(f"color: {colors.get(role, ColorPalette.custom_text_foreground)}; background: transparent;")
        self._refresh_status()

    # ------------------------------------------------------------------
    def _data_root(self) -> Path:
        return user_settings_path().parent.parent

    @staticmethod
    def _open(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


__all__ = ["CSettingsPanel"]
