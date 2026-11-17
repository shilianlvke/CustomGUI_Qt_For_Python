"""设置页构建：把声明式 ``SettingsPage`` 渲染成控件树。

本模块只依赖组件库与 :class:`~sllkgui.appcore.settings.SettingsSession`：

- 每个 ``SettingsSection`` → 一张 ``CSettingGroup``；
- 每个 ``SettingSpec`` → 一行 ``CSettingRow``，控件按 ``control`` 选择；
- 主题页额外提供主题卡片网格；
- 快捷键 / 关于 / 插件空状态是基座自定义页，和声明页共用同一套组件。

所有取值变化先写入会话（内存草稿），保存 / 放弃由窗口统一的底部操作栏负责。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import PySide6
from PySide6.QtCore import QSignalBlocker, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sllkgui import __version__
from sllkgui.appcore import (
    AppSettings,
    AppThemes,
    Language,
    SettingsSession,
    SettingsValidationError,
    get_design_tokens,
    load_user_settings,
    save_user_settings,
    user_settings_path,
)

from ...custom_ui.button.button import CButton
from ...custom_ui.display.theme_card import CThemeCard
from ...custom_ui.line_edit.choice import CToggleSwitch
from ...custom_ui.line_edit.input_number import CInputNumber
from ...custom_ui.line_edit.input_text import CInputText
from ...custom_ui.line_edit.select import CSelect
from ...custom_ui.line_edit.slider import CSlider
from ...custom_ui.line_edit.toggle_button import CSelectButton
from ...custom_ui.panels.settings import CInfoRow, CSettingGroup, CSettingRow
from ...custom_ui.picture.thumbnail import CThumbnail
from ...shortcuts import shortcut_registry

_THEME_SUBTITLE_KEYS = {
    "default": ("language.UI.ui_SettingsThemeDefault", "默认深色 · 果绿强调"),
    "bright": ("language.UI.ui_SettingsThemeBright", "浅色 · 日光画布"),
    "dracula": ("language.UI.ui_SettingsThemeDracula", "深紫 · 高对比"),
    "eye": ("language.UI.ui_SettingsThemeEye", "低蓝光 · 暖灰"),
}


def _label(text: str, role: str = "", parent=None) -> QLabel:
    label = QLabel(text, parent)
    font = QFont(AppSettings.family)
    font.setPixelSize(13 if role == "title" else 11)
    font.setWeight(QFont.Weight.DemiBold if role == "title" else QFont.Weight.Normal)
    label.setFont(font)
    colors = get_design_tokens().colors
    label.setStyleSheet(
        f"color: {colors.text_title if role == 'title' else colors.text_muted}; background: transparent;"
    )
    label.setWordWrap(role != "title")
    return label


def _action_button(text: str, *, icon: str | None = None) -> CButton:
    return CButton(text, icon=icon, variant="outlined", size="sm")


def _theme_subtitle(name: str) -> str:
    key, fallback = _THEME_SUBTITLE_KEYS.get(name, ("", ""))
    return str(Language.resolve_key(key, fallback)) if key else ""


class SchemaPage(QWidget):
    """由 :class:`SettingsPage` 声明生成的一页。"""

    def __init__(self, page, session: SettingsSession, host, parent=None):
        super().__init__(parent)
        self._page = page
        self._session = session
        self._host = host
        self._rows: dict[str, CSettingRow] = {}
        self._syncing = False
        self._syncers: list = []
        self._groups: list[CSettingGroup] = []
        self._theme_key = ""
        self._theme_cards: list[CThemeCard] = []
        self._thumbs: list[CThumbnail] = []
        self._recent_box: QHBoxLayout | None = None
        self._recent_empty: QLabel | None = None
        self._recent: list[str] = []
        self._notes: list[QLabel] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)
        outer.setAlignment(Qt.AlignTop)

        for section in page.sections:
            group = CSettingGroup(section.display_title(), section.display_hint(), self)
            self._groups.append(group)
            for spec in section.items:
                if spec.resolved_control().value == "theme_gallery":
                    self._theme_key = page.full_key(spec.key)
                    group.add_widget(self._build_theme_gallery(spec), divider=False)
                else:
                    row = self._build_row(spec)
                    if row is not None:
                        group.add_row(row)
                    if (
                        page.namespace == "core"
                        and page.page_id == "appearance"
                        and spec.key == "background_image"
                    ):
                        group.add_row(self._build_recent_row())
            outer.addWidget(group)
        if page.namespace == "core" and page.page_id == "window":
            self._window_info = self._build_window_info()
            outer.addWidget(self._window_info)
            self._groups.append(self._window_info)
        outer.addStretch(1)
        self.sync_from_session()

    # ------------------------------------------------------------------
    def page(self):
        return self._page

    def groups(self) -> tuple[CSettingGroup, ...]:
        return tuple(self._groups)

    def update_style(self) -> None:
        for group in self._groups:
            group.update_style()
        for card in self._theme_cards:
            card.update()
        for thumb in self._thumbs:
            thumb.update()
        for note in self._notes:
            self._style_note(note)
        self.update()

    def _build_window_info(self) -> CSettingGroup:
        group = CSettingGroup(
            Language.resolve_key("language.UI.ui_SettingsSectionCurrentWindow", "当前窗口"),
            Language.resolve_key("language.UI.ui_SettingsCurrentWindowHint", "当前窗口的尺寸信息。"),
            self,
        )
        host = self._host
        size = None
        getter = getattr(host, "host_window_size", None)
        if callable(getter):
            try:
                size = getter()
            except Exception:  # noqa: BLE001 - 宿主尺寸查询失败不影响设置页
                size = None
        current = f"{size[0]} × {size[1]}" if size else "—"
        minimum = AppSettings.minimum_size
        saved_startup = load_user_settings().get("startup_size")
        startup = (
            tuple(saved_startup)
            if isinstance(saved_startup, (list, tuple)) and len(saved_startup) == 2
            else AppSettings.startup_size
        )
        group.add_row(CInfoRow(Language.resolve_key("language.UI.ui_SettingsCurrentWindowSize", "当前尺寸"), current, mono=True, parent=self))
        group.add_row(CInfoRow(Language.resolve_key("language.UI.ui_SettingsMinimumWindowSize", "最小尺寸"), f"{minimum[0]} × {minimum[1]}", mono=True, parent=self))
        group.add_row(CInfoRow(Language.resolve_key("language.UI.ui_SettingsStartupSize", "启动尺寸"), f"{startup[0]} × {startup[1]}", mono=True, parent=self))
        return group

    # ------------------------------------------------------------------
    def _build_row(self, spec) -> CSettingRow | None:
        full_key = self._page.full_key(spec.key)
        control, syncer = self._build_control(spec, full_key)
        if control is None:
            return None
        row = CSettingRow(full_key, spec.display_label(), spec.display_hint(), control, parent=self)
        row.resetRequested.connect(self._on_reset)
        self._rows[full_key] = row
        row.set_reset_available(not self._session.is_default(full_key))
        self._syncers.append(syncer)
        return row

    def _build_control(self, spec, full_key: str):
        control = spec.resolved_control().value
        value = self._session.value(full_key)

        if control == "switch":
            widget = CToggleSwitch("", checked=bool(value), parent=self)
            widget.toggled.connect(lambda checked: self._commit(full_key, bool(checked)))
            return widget, lambda: self._set_switch(widget, bool(self._session.value(full_key)))

        if control in ("select", "segmented"):
            labels = [spec.option_label(item) for item in spec.option_values()]
            values = list(spec.option_values())
            if control == "segmented":
                index = values.index(value) if value in values else 0
                widget = CSelectButton(labels, index=index, size="sm", parent=self)
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                widget.selectionChanged.connect(
                    lambda idx: self._commit(full_key, values[int(idx)] if 0 <= int(idx) < len(values) else value)
                )
                return widget, lambda: widget.set_index(
                    values.index(self._session.value(full_key)) if self._session.value(full_key) in values else 0,
                    emit=False,
                )
            widget = CSelect(options=labels, value=spec.option_label(value), size="sm", parent=self)
            widget.setMinimumWidth(150)
            widget.selectionChanged.connect(
                lambda label: self._commit(
                    full_key,
                    values[labels.index(label)] if label in labels else self._session.value(full_key),
                )
            )
            return widget, lambda: widget.set_value(spec.option_label(self._session.value(full_key)), emit=False)

        if control == "slider":
            minimum = int(spec.minimum if spec.minimum is not None else 0)
            maximum = int(spec.maximum if spec.maximum is not None else 100)
            box = QWidget(self)
            box_layout = QHBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(10)
            slider = CSlider(value=int(value), minimum=minimum, maximum=maximum, step=int(spec.step or 1), parent=box)
            slider.setFixedWidth(210)
            value_label = QLabel(f"{int(value)}{spec.suffix}", box)
            value_label.setMinimumWidth(40)
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setFont(QFont("Cascadia Mono", 10))
            box_layout.addWidget(slider)
            box_layout.addWidget(value_label)

            def on_slider(raw: int) -> None:
                value_label.setText(f"{int(raw)}{spec.suffix}")
                self._commit(full_key, int(raw))

            slider.valueChanged.connect(on_slider)

            def sync_slider() -> None:
                current = int(self._session.value(full_key))
                slider.setValue(current, emit=False)
                value_label.setText(f"{current}{spec.suffix}")

            return box, sync_slider

        if control == "number":
            minimum = float(spec.minimum if spec.minimum is not None else 0)
            maximum = float(spec.maximum if spec.maximum is not None else 999999)
            widget = CInputNumber(
                value=float(value),
                minimum=minimum,
                maximum=maximum,
                step=float(spec.step or 1),
                decimals=int(spec.decimals),
                show_buttons=True,
                size="sm",
                parent=self,
            )
            widget.setFixedWidth(110)
            widget.valueChanged.connect(
                lambda raw: self._commit(
                    full_key,
                    int(raw) if spec.kind.value == "int" else float(raw),
                )
            )
            return widget, lambda: widget.setValue(float(self._session.value(full_key)))

        if control == "text":
            widget = CInputText(str(value), placeholder=spec.placeholder, size="sm", parent=self)
            widget.setMinimumWidth(240)
            widget.textChanged.connect(lambda text: self._commit(full_key, str(text)))
            return widget, lambda: self._set_text(widget, str(self._session.value(full_key)))

        if control == "path":
            box = QWidget(self)
            box_layout = QHBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(8)
            field = CInputText(str(value), placeholder=spec.placeholder, size="sm", parent=box)
            field.setReadOnly(True)
            field.setMinimumWidth(240)
            browse = _action_button(Language.resolve_key("language.UI.ui_SettingsChooseFile", "选择文件…"))
            clear = CButton(
                "",
                icon="icon_trash",
                variant="text",
                size="sm",
                fixed_width=28,
                icon_size=14,
                parent=box,
            )
            clear.setToolTip(Language.resolve_key("language.UI.ui_SettingsClear", "清除"))

            image_picker = self._page.namespace == "core" and spec.key == "background_image"

            def choose() -> None:
                current = str(self._session.value(full_key))
                start = str(Path(current).parent) if current else ""
                if not start:
                    location = (
                        QStandardPaths.StandardLocation.PicturesLocation
                        if image_picker
                        else QStandardPaths.StandardLocation.HomeLocation
                    )
                    start = QStandardPaths.writableLocation(location)
                file_filter = (
                    "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif)"
                    if image_picker
                    else "All files (*)"
                )
                path, _selected = QFileDialog.getOpenFileName(
                    self,
                    Language.resolve_key("language.UI.ui_SettingsChooseFile", "选择文件…"),
                    start,
                    file_filter,
                )
                if path:
                    self._commit(full_key, path)
                    self._remember_background(path)

            browse.clicked.connect(choose)
            clear.clicked.connect(lambda: self._commit(full_key, ""))
            box_layout.addWidget(field)
            box_layout.addWidget(browse)
            box_layout.addWidget(clear)
            return box, lambda: self._set_text(field, str(self._session.value(full_key)))

        return None, lambda: None

    # ------------------------------------------------------------------
    def _build_theme_gallery(self, spec) -> QWidget:
        box = QWidget(self)
        grid = QGridLayout(box)
        grid.setContentsMargins(2, 4, 2, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        names = sorted(AppThemes.keys())
        if "default" in names:
            names.remove("default")
            names.insert(0, "default")
        for index, name in enumerate(names):
            card = CThemeCard(
                name,
                _theme_subtitle(name),
                box,
                title="Grove" if name == "default" else "",
            )
            card.clicked.connect(lambda theme: self._select_theme(theme))
            self._theme_cards.append(card)
            grid.addWidget(card, index // 2, index % 2)
        return box

    def _select_theme(self, theme: str) -> None:
        if not self._theme_key or theme not in AppThemes:
            return
        self._commit(self._theme_key, theme)
        self.sync_theme_state()

    def sync_theme_state(self) -> None:
        current = self._session.value(self._theme_key) if self._theme_key else ""
        for card in self._theme_cards:
            card.set_selected(card.name() == current)

    # ------------------------------------------------------------------
    def _build_recent_row(self) -> CSettingRow:
        self._recent = self._recent_paths()
        wrapper = QWidget(self)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch(1)
        self._recent_box = layout
        row = CSettingRow(
            "__background_recent__",
            Language.resolve_key("language.UI.ui_RecentImages", "最近使用的图像"),
            Language.resolve_key("language.UI.ui_SettingsRecentImagesHint", "点击缩略图即可切换背景。"),
            wrapper,
            resettable=False,
            parent=self,
        )
        self._recent_empty = QLabel(
            Language.resolve_key("language.UI.ui_NoRecentImages", "暂无最近使用的图像"), wrapper
        )
        self._recent_empty.setStyleSheet(f"color: {get_design_tokens().colors.text_muted}; background: transparent;")
        layout.insertWidget(0, self._recent_empty)
        self._refresh_recent()
        return row

    @staticmethod
    def _recent_paths() -> list[str]:
        raw = load_user_settings().get("background_recent")
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if isinstance(item, str) and Path(item).is_file()][:5]

    def _refresh_recent(self) -> None:
        if self._recent_box is None:
            return
        for thumb in self._thumbs:
            thumb.setParent(None)
            thumb.deleteLater()
        self._thumbs.clear()
        current = self._session.value(self._page.full_key("background_image"))
        shown = 0
        for path in self._recent:
            thumb = CThumbnail(path, selected=path == current, parent=self)
            thumb.clicked.connect(lambda item: self._on_recent_clicked(item))
            self._recent_box.insertWidget(max(0, self._recent_box.count() - 1), thumb)
            self._thumbs.append(thumb)
            shown += 1
        if self._recent_empty is not None:
            self._recent_empty.setVisible(shown == 0)

    def _on_recent_clicked(self, path: str) -> None:
        self._commit(self._page.full_key("background_image"), path)
        self._remember_background(path)
        self._refresh_recent()

    def _remember_background(self, path: str) -> None:
        item = str(path)
        if not item:
            return
        recent = [item] + [entry for entry in self._recent if entry != item]
        self._recent = [entry for entry in recent if Path(entry).is_file()][:5]
        save_user_settings(background_recent=self._recent)
        self._refresh_recent()

    # ------------------------------------------------------------------
    def _commit(self, full_key: str, value) -> None:
        if self._syncing:
            return
        try:
            changed = self._session.set(full_key, value)
        except SettingsValidationError as exc:
            row = self._rows.get(full_key)
            self._host.show_error(str(exc))
            # 同步会把控件拉回上次合法值；行内错误必须在同步之后贴回，
            # 否则会被 sync_from_session() 的统一清空覆盖掉。
            self.sync_from_session()
            if row is not None:
                row.set_error(str(exc))
            return
        row = self._rows.get(full_key)
        if row is not None:
            row.set_error(None)
            row.set_modified(self._session.is_modified(full_key))
            row.set_reset_available(not self._session.is_default(full_key))
        if changed and self._theme_key and full_key == self._theme_key:
            self.sync_theme_state()
        self._host.clear_error()
        self._host.notify_modified()
        spec = self._session.registry.spec(full_key)
        if spec is not None and spec.live_preview:
            self._host.request_preview(full_key, self._session.value(full_key))

    def _on_reset(self, full_key: str) -> None:
        if not full_key.startswith(f"{self._page.namespace}."):
            return
        if self._session.registry.spec(full_key) is None:
            return
        self._session.reset(full_key)
        self.sync_from_session()
        self._host.notify_modified()
        spec = self._session.registry.spec(full_key)
        if spec is not None and spec.live_preview:
            self._host.request_preview(full_key, self._session.value(full_key))

    # ------------------------------------------------------------------
    @staticmethod
    def _set_switch(widget: CToggleSwitch, value: bool) -> None:
        blocker = QSignalBlocker(widget)
        widget.setChecked(bool(value))
        del blocker

    @staticmethod
    def _set_text(widget: CInputText, value: str) -> None:
        blocker = QSignalBlocker(widget)
        widget.setText(str(value))
        del blocker

    def sync_from_session(self) -> None:
        self._syncing = True
        try:
            for syncer in self._syncers:
                syncer()
            for full_key, row in self._rows.items():
                row.set_modified(self._session.is_modified(full_key))
                row.set_reset_available(not self._session.is_default(full_key))
                row.set_error(None)
            self.sync_theme_state()
            if self._recent_box is not None:
                self._refresh_recent()
        finally:
            self._syncing = False


# ----------------------------------------------------------------------
# 自定义页：关于 / 快捷键 / 插件空状态
# ----------------------------------------------------------------------
def _data_root() -> Path:
    return user_settings_path().parent.parent


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


def _open_path(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class AboutPage(QWidget):
    """关于页：软件信息、运行环境、目录与配置存储。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: list[CSettingGroup] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        software = CSettingGroup(
            Language.resolve_key("language.UI.ui_SettingsSoftware", "软件信息"),
            "SllkGUI · PySide6 桌面 UI 基座",
            self,
        )
        software.add_row(self._info("language.UI.ui_SettingsVersion", "版本", __version__, mono=True))
        layout.addWidget(software)
        self._groups.append(software)

        environment = CSettingGroup(
            Language.resolve_key("language.UI.ui_SettingsEnvironment", "运行环境"),
            "当前软件运行所需的环境信息。",
            self,
        )
        environment.add_row(CInfoRow("Python", platform.python_version(), parent=self))
        environment.add_row(CInfoRow("Qt", f"PySide6 {PySide6.__version__}", parent=self))
        environment.add_row(CInfoRow("OS", f"{platform.system()} {platform.release()}".strip(), parent=self))
        data_dir = _data_root()
        environment.add_row(self._path_row("language.UI.ui_SettingsDataDir", "数据目录", data_dir))
        environment.add_row(self._path_row("language.UI.ui_SettingsLogDir", "日志目录", data_dir / "logs"))
        layout.addWidget(environment)
        self._groups.append(environment)

        layout.addStretch(1)

    def _info(self, key: str, fallback: str, value: str, *, mono: bool) -> CInfoRow:
        return CInfoRow(Language.resolve_key(key, fallback), value, mono=mono, parent=self)

    def _path_row(self, key: str, fallback: str, path: Path) -> CInfoRow:
        row = CInfoRow(Language.resolve_key(key, fallback), _display_path(path), parent=self)
        button = _action_button(Language.resolve_key("language.UI.ui_Open", "打开"))
        button.clicked.connect(lambda: _open_path(path))
        row.add_action(button)
        return row

    def groups(self) -> tuple[CSettingGroup, ...]:
        return tuple(self._groups)

    def update_style(self) -> None:
        for group in self._groups:
            group.update_style()
            for row in group.rows():
                if isinstance(row, CInfoRow):
                    row.update_style()


class ShortcutsPage(QWidget):
    """快捷键页：基座与插件绑定按 owner 分组展示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: list[CSettingGroup] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        try:
            infos = shortcut_registry().describe()
            conflicts = shortcut_registry().conflicts()
        except Exception:  # noqa: BLE001 - 无 Qt 应用时降级为空表
            infos, conflicts = (), ()

        base = [item for item in infos if item.owner == "sllkgui.base"]
        grouped: dict[str, list] = {}
        for item in infos:
            if item.owner == "sllkgui.base":
                continue
            grouped.setdefault(item.owner, []).append(item)

        layout.addWidget(self._build_group("language.UI.ui_SettingsSectionBaseShortcuts", "基座快捷键", base, "常用操作的系统快捷键。"))
        for owner, items in sorted(grouped.items()):
            layout.addWidget(self._build_group("", owner, items, "插件提供的快捷键。"))

        summary = CSettingGroup(
            Language.resolve_key("language.UI.ui_SettingsShortcutStatus", "快捷键冲突"),
            Language.resolve_key("language.UI.ui_SettingsShortcutStatusHint", "重复占用的按键数量。"),
            self,
        )
        summary.add_row(
            CInfoRow(
                Language.resolve_key("language.UI.ui_SettingsShortcutConflicts", "冲突"),
                str(len(conflicts)),
                mono=True,
                parent=self,
            )
        )
        layout.addWidget(summary)
        self._groups.append(summary)
        layout.addStretch(1)

    def _build_group(self, key: str, fallback: str, items, hint: str) -> CSettingGroup:
        title = str(Language.resolve_key(key, fallback)) if key else fallback
        group = CSettingGroup(title, hint, self)
        if not items:
            group.add_row(
                CInfoRow(
                    Language.resolve_key("language.UI.ui_SettingsShortcutsNone", "无绑定"),
                    "",
                    mono=False,
                    parent=self,
                )
            )
        for item in items:
            row = CSettingRow(
                item.shortcut_id,
                item.description or item.shortcut_id,
                item.shortcut_id,
                self._keys_widget(item),
                badge=Language.resolve_key("language.UI.ui_SettingsLocked", "锁定") if item.locked else "",
                resettable=False,
                parent=self,
            )
            group.add_row(row)
        self._groups.append(group)
        return group

    @staticmethod
    def _keys_widget(item) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        for part in str(item.display).replace("+", " + ").split():
            if part == "+":
                label = QLabel("+")
                label.setStyleSheet(f"color: {get_design_tokens().colors.text_muted}; background: transparent;")
                layout.addWidget(label)
                continue
            cap = QLabel(part)
            cap.setFont(QFont("Cascadia Mono", 10, QFont.Weight.DemiBold))
            cap.setStyleSheet(
                f"color: {get_design_tokens().colors.text_primary};"
                f" border: 1px solid {get_design_tokens().colors.border_soft};"
                f" border-radius: 5px; padding: 2px 6px; background: transparent;"
            )
            layout.addWidget(cap)
        return box

    def groups(self) -> tuple[CSettingGroup, ...]:
        return tuple(self._groups)

    def update_style(self) -> None:
        for group in self._groups:
            group.update_style()


def build_plugin_empty_page(plugin_name: str, parent=None) -> QWidget:
    """插件未声明设置页时的空状态。"""
    page = QWidget(parent)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    layout.setAlignment(Qt.AlignTop)

    card = CSettingGroup("", "", page)
    body = QWidget(card)
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(18, 30, 18, 30)
    body_layout.setSpacing(8)
    title = _label(
        Language.resolve_key("language.UI.ui_SettingsPluginEmpty", "这个插件没有可配置项"),
        "title",
        body,
    )
    title.setAlignment(Qt.AlignCenter)
    hint = _label(
        Language.resolve_key(
            "language.UI.ui_SettingsPluginEmptyHint",
            "该插件暂未提供可配置项。",
        ),
        "",
        body,
    )
    hint.setAlignment(Qt.AlignCenter)
    hint.setWordWrap(True)
    body_layout.addWidget(title)
    body_layout.addWidget(hint)
    card.add_widget(body, divider=False)
    layout.addWidget(card)
    layout.addStretch(1)
    return page


__all__ = ["AboutPage", "SchemaPage", "ShortcutsPage", "build_plugin_empty_page"]
