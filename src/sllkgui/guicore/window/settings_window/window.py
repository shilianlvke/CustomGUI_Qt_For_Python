"""独立设置窗口：基座与插件配置的统一入口。

结构：

- 左侧：搜索 + 分组导航（基座设置 / 插件设置）+ 版本与当前主题；
- 右侧：页面标题、可滚动内容、底部编辑操作栏（有改动时才出现）；
- 页面：由 ``SettingsPage`` 声明生成（外观 / 界面 / 启动与窗口 / 插件），
  以及基座自定义的快捷键页、关于页、插件空状态页。

编辑语义由 ``SettingsSession`` 统一承担：改动先进草稿，保存才落盘；关闭时
若有未保存改动会二次确认。主题 / 材质 / 背景通过 ``previewChanged`` 交给
宿主做实时预览，放弃修改时窗口会用基线值还原。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
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
    SettingsSession,
    ensure_core_pages,
    get_design_tokens,
    get_theme_manager,
    settings_page_bus,
)

from ...acrylic import apply_acrylic
from ...custom_ui.close_button import CCloseButton
from ...custom_ui.line_edit.input_text import CInputText
from ...custom_ui.overlay.confirm import CConfirmDialog
from ...custom_ui.panels.settings import CEditActionBar
from ...custom_ui.panels.side_nav import CSideNav, CSideNavGroup, CSideNavItem
from ...custom_ui.scroll.scroll_area import CScrollArea
from ...styles import overlay_surface_color
from .pages import AboutPage, SchemaPage, ShortcutsPage, build_plugin_empty_page

_PAGE_ABOUT = "__about__"
_PAGE_SHORTCUTS = "__shortcuts__"
_PLUGIN_EMPTY_PREFIX = "__plugin_empty__:"
#: 主题文件名的展示名（default 在界面上叫 Grove）
_THEME_NAMES = {"default": "Grove"}


class _TitleBar(QWidget):
    """标题栏：应用标识、标题、副标题与关闭按钮，可拖动窗口。"""

    def __init__(self, window: CSettingsWindow):
        super().__init__(window)
        self._window = window
        self._press: QPoint | None = None
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 8, 0)
        layout.setSpacing(10)

        self.mark = QLabel("S", self)
        self.mark.setFixedSize(22, 22)
        self.mark.setAlignment(Qt.AlignCenter)
        font = QFont(AppSettings.family)
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Black)
        self.mark.setFont(font)

        self.title = QLabel(self)
        self.subtitle = QLabel(self)
        title_font = QFont(AppSettings.family)
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(title_font)
        sub_font = QFont(AppSettings.family)
        sub_font.setPixelSize(11)
        self.subtitle.setFont(sub_font)

        layout.addWidget(self.mark, 0, Qt.AlignVCenter)
        layout.addWidget(self.title, 0, Qt.AlignVCenter)
        layout.addWidget(self.subtitle, 0, Qt.AlignVCenter)
        layout.addStretch(1)

        self.close_button = CCloseButton(QColor(get_design_tokens().colors.text_primary), size=28, radius=6, parent=self)
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.close_button, 0, Qt.AlignVCenter)

    def update_style(self) -> None:
        tokens = get_design_tokens()
        colors = tokens.colors
        self.mark.setStyleSheet(
            f"background: {colors.accent}; color: {colors.text_on_accent};"
            f" border-radius: 6px; font-weight: 800;"
        )
        self.title.setText(Language.resolve_key("language.UI.ui_SettingsWindowTitle", "设置"))
        self.title.setStyleSheet(f"color: {colors.text_title}; background: transparent;")
        self.subtitle.setText(
            Language.resolve_key("language.UI.ui_SettingsWindowSubtitle", "基座与插件配置，统一保存")
        )
        self.subtitle.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self.close_button.set_color(QColor(colors.text_primary))
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        line = QColor(colors.text_primary)
        line.setAlpha(24)
        painter.setPen(QPen(line, 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._press)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._press = None


class CSettingsWindow(QDialog):
    """独立设置窗口（非模态，可窗口内实时预览）。"""

    #: 实时预览：完整键 + 值（主题 / 透明度 / 质感 / 背景）
    previewChanged = Signal(str, object)
    #: 保存成功：``full_key -> value``，宿主据此应用语言 / 布局等设置
    settingsSaved = Signal(dict)
    #: 窗口关闭（未保存改动已处理）
    closed = Signal()
    #: 页面切换（导航 / 程序化），便于宿主联动
    pageChanged = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        session: SettingsSession | None = None,
        host: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("CSettingsWindow")
        self.setWindowTitle(Language.resolve_key("language.UI.ui_SettingsWindowTitle", "设置"))
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(False)
        self.setMinimumSize(640, 480)
        self.resize(960, 600)

        ensure_core_pages(session.registry if session is not None else None)
        self._session = session if session is not None else SettingsSession()
        self._host = host if host is not None else parent
        self._entries: dict[str, dict] = {}
        self._schema_pages: dict[str, SchemaPage] = {}
        self._previewed: dict[str, object] = {}
        self._confirm_open = False
        self._confirmed_close = False
        self._error_active = False
        self._saved_timer: QTimer | None = None
        self._current_entry = ""
        self._page_unsubscribe = None

        self._build_ui()
        self._populate_pages()
        self._wire()
        self.update_style()
        self._refresh_dirty()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 窗口本身就是唯一表面：不再套内层卡片，避免边框 / 背景 / 阴影 / 外边距
        # 形成「窗口里还有一层面板」的包裹感。
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._title_bar = _TitleBar(self)
        root_layout.addWidget(self._title_bar)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root_layout.addWidget(body, 1)

        # 左侧导航
        nav_column = QWidget(body)
        nav_column.setFixedWidth(242)
        nav_column.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_column)
        nav_layout.setContentsMargins(12, 14, 12, 10)
        nav_layout.setSpacing(10)

        self.search = CInputText(
            "",
            placeholder=Language.resolve_key("language.UI.ui_SettingsSearch", "搜索设置项…"),
            size="sm",
            icon="icon_search",
            icon_pos="left",
            parent=nav_column,
        )
        nav_layout.addWidget(self.search)

        self.nav_scroll = CScrollArea(nav_column, background="transparent")
        self.nav = CSideNav(parent=self.nav_scroll)
        self.nav_scroll.setWidget(self.nav)
        nav_layout.addWidget(self.nav_scroll, 1)

        self.nav_empty = QLabel(
            Language.resolve_key("language.UI.ui_SettingsNavEmpty", "没有匹配的设置页"), nav_column
        )
        self.nav_empty.setAlignment(Qt.AlignCenter)
        self.nav_empty.setVisible(False)
        nav_layout.addWidget(self.nav_empty)

        footer = QWidget(nav_column)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 0)
        footer_layout.setSpacing(8)
        self.version_label = QLabel(f"v{__version__}", footer)
        self.theme_label = QLabel("", footer)
        footer_layout.addWidget(self.version_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.theme_label)
        nav_layout.addWidget(footer)
        body_layout.addWidget(nav_column)

        # 右侧内容
        content = QWidget(body)
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        body_layout.addWidget(content, 1)

        header = QWidget(content)
        # 固定高度与固定字块高度：切换页面 / 脏值变化都不会让头部伸缩或位移。
        header.setFixedHeight(76)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 18, 26, 8)
        header_layout.setSpacing(16)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(4)
        self.page_title = QLabel("", header)
        self.page_title.setFixedHeight(28)
        self.page_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.page_hint = QLabel("", header)
        self.page_hint.setWordWrap(True)
        self.page_hint.setFixedHeight(18)
        self.page_hint.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.page_hint.setMaximumWidth(620)
        self.page_hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title_col.addWidget(self.page_title)
        title_col.addWidget(self.page_hint)
        header_layout.addLayout(title_col, 1)
        content_layout.addWidget(header)

        self.stack = QStackedWidget(content)
        content_layout.addWidget(self.stack, 1)

        self.action_bar = CEditActionBar(content)
        self.action_bar.setVisible(False)
        content_layout.addWidget(self.action_bar)

        self._nav_column = nav_column
        self._content = content
        self._header = header

    def _wire(self) -> None:
        self.search.textChanged.connect(self._filter_nav)
        self.nav.itemClicked.connect(self.show_page)
        self.action_bar.saveRequested.connect(self.save)
        self.action_bar.discardRequested.connect(self.discard)
        self.action_bar.resetRequested.connect(self.reset_current_page)
        get_theme_manager().subscribe(self._on_theme_applied)
        self._page_unsubscribe = settings_page_bus().subscribe_all(self._on_plugin_page_changed)
        self.destroyed.connect(self._detach_page_bus)

    # ------------------------------------------------------------------
    # 页面
    # ------------------------------------------------------------------
    def _populate_pages(self) -> None:
        core_pages = self._session.pages("core")
        core_items: list[CSideNavItem] = []
        for page in core_pages:
            self._add_schema_page(page, prefix=page.page_id)
            keywords = self._page_keywords(page)
            core_items.append(
                CSideNavItem(
                    page.page_id,
                    page.display_title(),
                    page.icon,
                    tooltip=page.display_hint(),
                    keywords=keywords,
                )
            )

        shortcuts = ShortcutsPage(parent=self)
        self._add_custom_page(
            _PAGE_SHORTCUTS,
            shortcuts,
            Language.resolve_key("language.UI.ui_SettingsPageShortcuts", "快捷键"),
            Language.resolve_key(
                "language.UI.ui_SettingsPageShortcutsHint",
                "基座与插件共用同一张快捷键表；插件条目默认优先级更低，冲突时拒绝注册。",
            ),
            "icon_plan",
            keywords="快捷键 shortcut ctrl alt shift",
        )
        core_items.append(
            CSideNavItem(
                _PAGE_SHORTCUTS,
                Language.resolve_key("language.UI.ui_SettingsPageShortcuts", "快捷键"),
                "icon_plan",
                keywords="快捷键 shortcut ctrl alt shift",
            )
        )

        about = AboutPage(parent=self)
        self._add_custom_page(
            _PAGE_ABOUT,
            about,
            Language.resolve_key("language.UI.ui_SettingsPageAbout", "关于"),
            Language.resolve_key(
                "language.UI.ui_SettingsPageAboutHint", "版本、运行环境与数据目录；这里的信息只读。"
            ),
            "icon_me",
            keywords="关于 版本 环境 目录 about version",
        )
        core_items.append(
            CSideNavItem(
                _PAGE_ABOUT,
                Language.resolve_key("language.UI.ui_SettingsPageAbout", "关于"),
                "icon_me",
                keywords="关于 版本 环境 目录 about version",
            )
        )

        plugin_items: list[CSideNavItem] = []
        for plugin_id, record, pages in self._plugin_pages():
            if pages:
                for page in pages:
                    item_id = f"plugin::{plugin_id}::{page.page_id}"
                    title = record.name if record is not None else page.display_title()
                    if len(pages) > 1:
                        title = f"{title} · {page.display_title()}"
                    self._add_schema_page(page, prefix=item_id)
                    plugin_items.append(
                        CSideNavItem(
                            item_id,
                            title,
                            page.icon or "icon_store",
                            tooltip=page.display_hint() or plugin_id,
                            keywords=self._page_keywords(page) + f" {plugin_id}",
                        )
                    )
            else:
                item_id = f"{_PLUGIN_EMPTY_PREFIX}{plugin_id}"
                title = record.name if record is not None else plugin_id
                empty = build_plugin_empty_page(title, self)
                self._add_custom_page(
                    item_id,
                    empty,
                    title,
                    Language.resolve_key(
                        "language.UI.ui_SettingsPluginNoSchema",
                        "该插件没有声明设置页；仍可通过数据目录保存运行时状态。",
                    ),
                    "icon_store",
                    keywords=f"插件 plugin {plugin_id}",
                )
                plugin_items.append(
                    CSideNavItem(item_id, title, "icon_store", badge=Language.resolve_key("language.UI.ui_SettingsUndeclared", "未声明"), keywords=f"插件 {plugin_id}")
                )

        if not plugin_items:
            plugin_items.append(
                CSideNavItem(
                    "__no_plugins__",
                    Language.resolve_key("language.UI.ui_SettingsNoPlugins", "暂无已安装插件"),
                    "icon_store",
                    enabled=False,
                    tooltip=Language.resolve_key(
                        "language.UI.ui_SettingsNoPluginsHint", "安装插件后，其设置页会自动出现在这里。"
                    ),
                )
            )

        groups = [
            CSideNavGroup(Language.resolve_key("language.UI.ui_SettingsNavBase", "基座设置"), tuple(core_items)),
            CSideNavGroup(Language.resolve_key("language.UI.ui_SettingsNavPlugins", "插件设置"), tuple(plugin_items)),
        ]
        self.nav.set_groups(groups)
        if core_items:
            self.show_page(core_items[0].item_id)

    def _add_schema_page(self, page, prefix: str) -> None:
        view = SchemaPage(page, self._session, self, parent=self)
        self._schema_pages[page.full_key("__page__")] = view
        self._entries[prefix] = {
            "widget": self._scroll_page(view),
            "title": page.display_title(),
            "hint": page.display_hint(),
            "schema_page": page,
            "view": view,
        }
        self.stack.addWidget(self._entries[prefix]["widget"])

    def _add_custom_page(
        self,
        item_id: str,
        widget: QWidget,
        title: str,
        hint: str,
        icon: str,
        *,
        keywords: str = "",
    ) -> None:
        self._entries[item_id] = {
            "widget": self._scroll_page(widget),
            "title": title,
            "hint": hint,
            "schema_page": None,
            "view": widget,
            "icon": icon,
            "keywords": keywords,
        }
        self.stack.addWidget(self._entries[item_id]["widget"])

    def _scroll_page(self, content: QWidget) -> QWidget:
        """把页面内容包进带边距的滚动容器（内容自身保留布局）。"""
        scroll = CScrollArea(self, background="transparent")
        scroll.setWidgetResizable(True)
        container = QWidget(scroll)
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(26, 2, 26, 24)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(content)
        scroll.setWidget(container)
        return scroll

    def _page_keywords(self, page) -> str:
        chunks = [page.display_title(), page.display_hint(), page.page_id]
        for section in page.sections:
            chunks.extend([section.display_title(), section.display_hint()])
            for spec in section.items:
                chunks.extend([spec.display_label(), spec.display_hint(), spec.key])
            for info in section.info:
                chunks.extend([info.display_label(), info.display_hint(), info.key])
            for action in section.actions:
                chunks.extend(
                    [
                        action.display_label(),
                        action.display_hint(),
                        action.display_button(),
                        action.key,
                    ]
                )
        return " ".join(chunk for chunk in chunks if chunk)

    def _plugin_pages(self):
        """按插件聚合设置页；同时纳入「已安装但没有设置」的插件。"""
        registry = self._session.registry
        pages_by_plugin: dict[str, list] = {}
        for page in registry.pages():
            if page.namespace == "core":
                continue
            plugin_id = page.namespace.split(".", 1)[1]
            pages_by_plugin.setdefault(plugin_id, []).append(page)
        records = self._plugin_records()
        for plugin_id in records:
            pages_by_plugin.setdefault(plugin_id, [])
        result = []
        for plugin_id in sorted(pages_by_plugin, key=lambda item: (records.get(item).name if records.get(item) else item).lower()):
            result.append((plugin_id, records.get(plugin_id), pages_by_plugin[plugin_id]))
        return result

    @staticmethod
    def _plugin_records() -> dict:
        try:
            from sllkgui.gallery.registry import current_registry

            registry = current_registry()
            if registry is None:
                return {}
            return {record.plugin_id: record for record in registry.plugins()}
        except Exception:  # noqa: BLE001 - 预览/测试环境可能没有插件注册表
            return {}

    # ------------------------------------------------------------------
    # 插件页刷新
    # ------------------------------------------------------------------
    def _on_plugin_page_changed(self, namespace: str) -> None:
        """插件请求重建页面；延到下一轮事件循环，避免在动作回调里销毁自身。"""
        if not self.isVisible():
            return
        QTimer.singleShot(0, lambda ns=namespace: self._rebuild_plugin_page(ns))

    def _rebuild_plugin_page(self, namespace: str) -> None:
        """重建某命名空间下的设置页，保留未保存草稿、当前页与滚动位置。"""
        if not self.isVisible():
            return
        for item_id, entry in list(self._entries.items()):
            page = entry.get("schema_page")
            if page is None or page.namespace != namespace:
                continue
            old_widget = entry["widget"]
            index = self.stack.indexOf(old_widget)
            scroll_value = 0
            if isinstance(old_widget, CScrollArea):
                scroll_value = int(old_widget.verticalScrollBar().value())

            view = SchemaPage(page, self._session, self, parent=self)
            self._schema_pages[page.full_key("__page__")] = view
            new_widget = self._scroll_page(view)
            if index >= 0:
                self.stack.insertWidget(index, new_widget)
            else:
                self.stack.addWidget(new_widget)
            self.stack.removeWidget(old_widget)
            old_widget.setParent(None)
            old_widget.deleteLater()

            entry["widget"] = new_widget
            entry["view"] = view
            entry["title"] = page.display_title()
            entry["hint"] = page.display_hint()
            if item_id == self._current_entry:
                self.stack.setCurrentWidget(new_widget)
                self.page_title.setText(entry["title"])
                hint = entry["hint"] or ""
                self.page_hint.setText(hint)
                self.page_hint.setToolTip(hint)
                if isinstance(new_widget, CScrollArea):
                    new_widget.verticalScrollBar().setValue(scroll_value)

    def _detach_page_bus(self, *_args) -> None:
        unsubscribe = self._page_unsubscribe
        self._page_unsubscribe = None
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception:  # noqa: BLE001 - 退出清理失败不影响关闭
                pass

    # ------------------------------------------------------------------
    # 页面切换
    # ------------------------------------------------------------------
    def show_page(self, item_id: str) -> bool:
        entry = self._entries.get(item_id)
        if entry is None:
            return False
        self._current_entry = item_id
        self.stack.setCurrentWidget(entry["widget"])
        self.nav.set_current(item_id)
        self.page_title.setText(entry["title"])
        hint = entry["hint"] or ""
        self.page_hint.setText(hint)
        self.page_hint.setToolTip(hint)
        self.action_bar.set_reset_visible(entry["schema_page"] is not None)
        scroll = entry["widget"]
        if isinstance(scroll, CScrollArea):
            scroll.verticalScrollBar().setValue(0)
        self.pageChanged.emit(item_id)
        return True

    def current_page_id(self) -> str:
        return self._current_entry

    def refresh_language(self) -> None:
        """语言切换后原地重建设置页，保持窗口打开并回到原页面。

        ``apply_language`` 会重建主窗口页面；设置窗口不能跟着关闭，也不能跳回
        第一页，否则用户保存语言后还要重新找到刚才的配置项。这里只重建设置
        窗口自己的页面树，会话（草稿 / 基线）与窗口位置保持不变。
        """
        current = self._current_entry
        query = self.search.text()
        scroll = 0
        entry = self._entries.get(current)
        if entry is not None and isinstance(entry["widget"], CScrollArea):
            scroll = int(entry["widget"].verticalScrollBar().value())

        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._entries.clear()
        self._schema_pages.clear()

        self._populate_pages()
        if current:
            self.show_page(current)
        self.search.setText(query)
        self._filter_nav(query)
        restored = self._entries.get(current)
        if restored is not None and isinstance(restored["widget"], CScrollArea):
            restored["widget"].verticalScrollBar().setValue(scroll)

        self.setWindowTitle(Language.resolve_key("language.UI.ui_SettingsWindowTitle", "设置"))
        self.search.setPlaceholderText(Language.resolve_key("language.UI.ui_SettingsSearch", "搜索设置项…"))
        self.action_bar.reset_texts()
        self._title_bar.update_style()
        self.update_style()

    def host_window_size(self) -> tuple[int, int] | None:
        """宿主主窗口的当前尺寸（关于页 / 当前窗口信息展示用）。"""
        host = self._host
        if isinstance(host, QWidget) and host.isVisible():
            return int(host.width()), int(host.height())
        return None

    def _filter_nav(self, text: str) -> None:
        self.nav.filter(text)
        self.nav_empty.setVisible(bool(str(text).strip()) and self.nav.visible_count() == 0)

    # ------------------------------------------------------------------
    # 脏值 / 保存
    # ------------------------------------------------------------------
    def session(self) -> SettingsSession:
        return self._session

    def notify_modified(self) -> None:
        self._refresh_dirty()

    def _refresh_dirty(self) -> None:
        count = self._session.dirty_count()
        if count > 0:
            self.action_bar.setVisible(True)
            self.action_bar.set_dirty_count(count)
        elif not self._error_active:
            self.action_bar.setVisible(False)

    def show_error(self, message: str) -> None:
        self._error_active = True
        self.action_bar.setVisible(True)
        self.action_bar.set_error(message)

    def clear_error(self) -> None:
        self._error_active = False
        if not self._session.is_dirty():
            self.action_bar.setVisible(False)
        else:
            self.action_bar.set_dirty_count(self._session.dirty_count())

    def request_preview(self, full_key: str, value) -> None:
        if full_key not in self._previewed:
            try:
                self._previewed[full_key] = self._session.baseline(full_key)
            except Exception:  # noqa: BLE001 - 未注册键忽略
                return
        self.previewChanged.emit(full_key, value)

    def save(self) -> bool:
        if not self._session.is_dirty():
            self.action_bar.setVisible(False)
            return True
        pending = dict(self._session.changes())
        self.action_bar.set_saving(True)
        ok = self._session.save()
        self.action_bar.set_saving(False)
        if not ok:
            self.action_bar.set_error(
                Language.resolve_key(
                    "language.UI.ui_SettingsSaveFailed", "保存失败，请检查配置目录的写入权限。"
                )
            )
            self.action_bar.setVisible(True)
            return False
        self._previewed.clear()
        self._error_active = False
        self._refresh_all_pages()
        self.action_bar.setVisible(True)
        self.action_bar.show_saved()
        self.settingsSaved.emit(pending)
        if self._saved_timer is None:
            self._saved_timer = QTimer(self)
            self._saved_timer.setSingleShot(True)
            self._saved_timer.timeout.connect(self._hide_saved_state)
        self._saved_timer.start(1500)
        return True

    def _hide_saved_state(self) -> None:
        if not self._session.is_dirty():
            self.action_bar.setVisible(False)
            self.action_bar.set_dirty_count(0)

    def discard(self) -> None:
        if not self._session.is_dirty():
            return
        self._error_active = False
        # 先按基线还原实时预览，再丢弃草稿
        for key, original in list(self._previewed.items()):
            self.previewChanged.emit(key, original)
        self._previewed.clear()
        self._session.discard()
        self._refresh_all_pages()
        self._refresh_dirty()
        self.action_bar.setVisible(False)

    def reset_current_page(self) -> None:
        entry = self._entries.get(self._current_entry)
        if entry is None or entry["schema_page"] is None:
            return
        page = entry["schema_page"]
        if not self._session.reset_page(page):
            return
        view = entry["view"]
        if isinstance(view, SchemaPage):
            view.sync_from_session()
        self._refresh_dirty()
        for spec in page.specs():
            if spec.live_preview:
                key = page.full_key(spec.key)
                self.request_preview(key, self._session.value(key))

    def _refresh_all_pages(self) -> None:
        for view in self._schema_pages.values():
            view.sync_from_session()
        self.update_theme_label()

    # ------------------------------------------------------------------
    # 主题 / 外观
    # ------------------------------------------------------------------
    def _on_theme_applied(self) -> None:
        self.update_style()

    def update_style(self) -> None:
        tokens = get_design_tokens()
        colors = tokens.colors
        self._title_bar.update_style()

        title_font = QFont(AppSettings.family)
        title_font.setPixelSize(20)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.page_title.setFont(title_font)
        self.page_title.setStyleSheet(f"color: {colors.text_title}; background: transparent;")
        hint_font = QFont(AppSettings.family)
        hint_font.setPixelSize(12)
        self.page_hint.setFont(hint_font)
        self.page_hint.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")

        footer_font = QFont(AppSettings.family)
        footer_font.setPixelSize(10)
        self.version_label.setFont(footer_font)
        self.version_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self.theme_label.setFont(footer_font)
        self.theme_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self.update_theme_label()

        self.search.setPlaceholderText(Language.resolve_key("language.UI.ui_SettingsSearch", "搜索设置项…"))
        self.nav_empty.setText(Language.resolve_key("language.UI.ui_SettingsNavEmpty", "没有匹配的设置页"))
        self.nav_empty.setStyleSheet(f"color: {colors.text_muted}; background: transparent; padding: 8px;")
        self.nav.update_style()
        self.action_bar.update_style()
        for view in self._schema_pages.values():
            view.update_style()
        for entry in self._entries.values():
            view = entry.get("view")
            update = getattr(view, "update_style", None)
            if callable(update):
                update()
        self.update()

    def update_theme_label(self) -> None:
        name = get_theme_manager().current()
        label = _THEME_NAMES.get(name, name.replace("_", " ").title())
        self.theme_label.setText(
            f"{label} · {Language.resolve_key('language.UI.ui_SettingsCurrentTheme', '当前主题')}"
        )

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        """绘制窗口自身表面；不再有内层卡片或描边。"""
        tokens = get_design_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), tokens.radius.window, tokens.radius.window)
        painter.fillPath(path, overlay_surface_color())
        painter.end()

    # ------------------------------------------------------------------
    # 展示 / 关闭
    # ------------------------------------------------------------------
    def open_settings(self) -> None:
        self._fit_to_parent()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus(Qt.OtherFocusReason)

    def _fit_to_parent(self) -> None:
        """窗口宽高取主界面的 80%，并居中于主界面。"""
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            width = max(1, int(parent.width() * 0.8))
            height = max(1, int(parent.height() * 0.8))
        else:
            screen = self.screen()
            area = screen.availableGeometry() if screen is not None else None
            width = max(1, int(area.width() * 0.8)) if area is not None else 960
            height = max(1, int(area.height() * 0.8)) if area is not None else 600
        self.resize(width, height)
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            frame = parent.frameGeometry()
            self.move(
                frame.center().x() - self.width() // 2,
                frame.center().y() - self.height() // 2,
            )
            return
        screen = self.screen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(
                area.center().x() - self.width() // 2,
                area.center().y() - self.height() // 2,
            )

    def showEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        parent = self.parentWidget()
        if parent is not None:
            parent.installEventFilter(self)
        super().showEvent(event)
        apply_acrylic(self)

    def eventFilter(self, obj, event):  # noqa: N802 - 覆写 Qt 命名
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize and self.isVisible():
            QTimer.singleShot(0, self._fit_to_parent)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self._session.is_dirty() and not self._confirmed_close:
            event.ignore()
            if self._confirm_open:
                return
            self._confirm_open = True
            try:
                dialog = CConfirmDialog(
                    Language.resolve_key("language.UI.ui_SettingsCloseTitle", "未保存的更改"),
                    Language.resolve_key(
                        "language.UI.ui_SettingsCloseText", "关闭设置窗口将丢失未保存的更改。"
                    ),
                    severity="warn",
                    accept_text=Language.resolve_key("language.UI.ui_SettingsCloseDiscard", "放弃并关闭"),
                    reject_text=Language.resolve_key("language.UI.ui_SettingsCancel", "取消"),
                    parent=self,
                )
                accepted = dialog.exec_dialog()
            finally:
                self._confirm_open = False
            if not accepted:
                return
            self.discard()
            self._confirmed_close = True
            QTimer.singleShot(0, self.close)
            return
        parent = self.parentWidget()
        if parent is not None:
            parent.removeEventFilter(self)
        try:
            get_theme_manager().unsubscribe(self._on_theme_applied)
        except Exception:  # noqa: BLE001 - 退订失败不阻塞关闭
            pass
        self.closed.emit()
        super().closeEvent(event)


__all__ = ["CSettingsWindow"]
