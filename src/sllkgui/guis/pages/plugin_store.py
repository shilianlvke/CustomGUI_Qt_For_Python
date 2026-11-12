"""插件管理（基座原生页面）：模式导轨 + 工作区。

不再作为 ``core_plugins`` 里的插件分发，而是 ``gallery`` 与 ``run`` 两种
模式都常驻的基座页面；由 :mod:`sllkgui.guis.windows.main_window.native_pages`
注册到左菜单与页面路由。

三段式工作台：已安装 / 发现 / 源。三个面板统一使用 ``CDataView``，支持
网格与列表切换；条目只保留状态开关，详细操作全部收进详情对话框。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sllkgui.appcore import (
    AppSettings,
    ColorPalette,
    Language,
    Logger,
    get_design_tokens,
    get_theme_manager,
    record_event,
    track_timing,
)
from sllkgui.guicore import (
    CButton,
    CConfirmDialog,
    CDataView,
    CDialog,
    CHDiv,
    CInputText,
    CSelectButton,
    CToast,
    CToggleSwitch,
)
from sllkgui.guicore.custom_ui.icon_utils import render_icon
from sllkgui.guicore.custom_ui.panels.style import RADIUS, paint_surface, panel_colors, rounded_path
from sllkgui.guicore.styles import card_surface_color

_MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "monospace"]

#: 原生页面的语言命名空间（语言文件里的 ``plugin_store`` 顶层节点）
_TEXT_NAMESPACE = "language.plugin_store"


class PageContext:
    """原生页面上下文：只覆盖插件管理页用到的基座能力。

    与插件上下文保持同名方法，页面代码无需感知自己已经脱离插件协议。
    """

    def __init__(self, parent_provider: Callable[[], QWidget | None]) -> None:
        self._parent_provider = parent_provider

    def text(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        value = str(Language.resolve_key(f"{_TEXT_NAMESPACE}.{key}", default if default is not None else key))
        if not kwargs:
            return value
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return value

    def log(self, message: str, level: str = "info") -> None:
        writer = {
            "debug": Logger.debug,
            "warning": Logger.warning,
            "warn": Logger.warning,
            "error": Logger.error,
            "critical": Logger.critical,
        }.get(str(level).lower(), Logger.info)
        writer(f"[plugin-store] {message}")

    def event(self, name: str, payload: Any = None, level: str = "info") -> None:
        record_event(str(name), category="ui", level=str(level), payload=dict(payload or {}))

    def timing(self, name: str, payload: Any = None):
        return track_timing(str(name), category="ui", payload=dict(payload or {}))

    def report_error(self, code: str, message: str, detail: str | None = None) -> None:
        self.log(f"{code}: {message}", "error")
        if detail:
            Logger.debug(f"[plugin-store] {code} detail: {detail}")
        try:
            from sllkgui.gallery.runtime import current_runtime

            runtime = current_runtime()
            if runtime is not None:
                runtime.last_error = {"code": code, "message": message, "detail": detail or ""}
        except Exception:  # noqa: BLE001 - 错误记录失败不影响页面
            pass
        self.event("plugin_store.error", {"code": code, "message": message}, level="error")

    def parent_window(self) -> QWidget | None:
        return self._parent_provider()


def build_plugin_store_page(window) -> QWidget:
    """原生页面工厂：由窗口装配层在首次导航时调用。"""
    return StorePage(PageContext(lambda: window))


def _toast_offset(window) -> int:
    """通知条避让标题栏：顶部偏移 = 标题栏高度 + 8。"""
    bar = getattr(getattr(window, "ui", None), "title_bar", None)
    return bar.height() + 8 if bar is not None else 56


# ----------------------------------------------------------------------
# 绘制工具
# ----------------------------------------------------------------------
def _tint(color: str | QColor, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(alpha)
    return value


def _font(base: QFont, size: int, weight: QFont.Weight = QFont.Weight.Normal, *, mono: bool = False) -> QFont:
    font = QFont(base)
    font.setPixelSize(size)
    font.setWeight(weight)
    if mono:
        font.setFamilies(_MONO_FAMILIES)
    return font


def _card_rect(widget: QWidget) -> QRectF:
    return QRectF(widget.rect()).adjusted(0.75, 0.75, -0.75, -0.75)


def _surface_color() -> QColor:
    """外层卡片底色：与 ``CCard`` 的 ``surface_card`` 一致（#44475a）。"""
    return QColor(card_surface_color())


def _line_color() -> QColor:
    """卡片描边：取交互按压层，保证在两种底色上都清晰可见（#595D75）。"""
    return QColor(get_design_tokens().colors.surface_interactive_pressed)


def _hover_color() -> QColor:
    return QColor(ColorPalette.custom_dark_four)


#: 与 py-rm page_kit 对齐的排版角色
_ROLE_SIZES = {"eyebrow": 8, "title": 18, "section": 12, "metric": 24, "body": 10, "muted": 9, "entry": 13, "value": 11}


class _ThemedLabel(QLabel):
    """按角色取色的文本标签；主题切换时自动刷新颜色。"""

    def __init__(self, text: str = "", role: str = "body", mono: bool = False, parent=None) -> None:
        super().__init__(text, parent)
        self._role = role
        family = _MONO_FAMILIES[0] if mono else AppSettings.family
        weight = QFont.Weight.DemiBold if role in {"eyebrow", "title", "section", "metric", "entry"} else QFont.Weight.Normal
        self.setFont(QFont(family, _ROLE_SIZES.get(role, 10), weight))
        self._apply_theme()
        try:
            get_theme_manager().subscribe(self._apply_theme)
        except Exception:  # noqa: BLE001 - 无主题管理器时保持初始配色
            pass

    def _apply_theme(self) -> None:
        color = {
            "eyebrow": ColorPalette.custom_context_color,
            "title": ColorPalette.custom_text_title,
            "section": ColorPalette.custom_text_title,
            "metric": ColorPalette.custom_text_title,
            "entry": ColorPalette.custom_text_title,
            "muted": ColorPalette.custom_text_description,
            "value": ColorPalette.custom_text_foreground,
            "body": ColorPalette.custom_text_foreground,
        }.get(self._role, ColorPalette.custom_text_foreground)
        self.setStyleSheet(f"color: {color}; background: transparent;")


class _Panel(QFrame):
    """py-rm Card 风格容器：圆角 + 明显描边 + 分层底色。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(painter, _card_rect(self), RADIUS, background=_surface_color(), border=_line_color())
        painter.end()


class _Chip(QWidget):
    """胶囊标签：版本、状态、来源、权限共用。"""

    def __init__(self, text: str, *, accent: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._accent = accent
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._resize_to_text()

    def _font(self) -> QFont:
        return _font(self.font(), 10, QFont.Weight.Medium)

    def _resize_to_text(self) -> None:
        width = QFontMetrics(self._font()).horizontalAdvance(self._text) + 16
        self.setFixedWidth(max(28, width))

    def set_text(self, text: str, *, accent: bool | None = None) -> None:
        self._text = text
        if accent is not None:
            self._accent = accent
        self._resize_to_text()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = _tint(colors["accent"], 38) if self._accent else None
        border = _tint(colors["accent"], 110) if self._accent else QColor(colors["border"])
        paint_surface(painter, rect, 10, background=background, border=border)
        painter.setFont(self._font())
        painter.setPen(QColor(colors["accent"] if self._accent else colors["muted"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class _ElidedLabel(QWidget):
    """单行省略文本：用于 ID、commit、URL 与简介。"""

    def __init__(self, text: str = "", *, mono: bool = False, size: int = 10, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._mono = mono
        self._size = size
        self.setFixedHeight(size + 6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setFont(_font(self.font(), self._size, mono=self._mono))
        painter.setPen(QColor(colors["muted"]))
        metrics = QFontMetrics(painter.font())
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(self._text, Qt.TextElideMode.ElideRight, max(0, self.width())),
        )
        painter.end()


class _IconTile(QWidget):
    """条目/详情页的产品图标：强调色淡底 + 单色图标。"""

    def __init__(self, icon: str, size: int = 38, parent=None) -> None:
        super().__init__(parent)
        self._icon = icon
        self._size = max(24, int(size))
        self.setFixedSize(self._size, self._size)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        accent = QColor(colors["accent"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 12 if self._size >= 48 else 10)
        fill = QColor(accent)
        fill.setAlpha(30)
        painter.fillPath(path, fill)
        border = QColor(accent)
        border.setAlpha(85)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)

        pixmap = render_icon(self._icon, QColor(colors["text"]), self._size - 16, self.devicePixelRatioF())
        if pixmap is not None and not pixmap.isNull():
            dpr = pixmap.devicePixelRatio() or 1.0
            width = pixmap.width() / dpr
            height = pixmap.height() / dpr
            target = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.end()


class _ModeCard(QFrame):
    """左侧模式导轨：自绘图标、标题与计数。"""

    clicked = Signal(str)

    def __init__(self, mode: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.title = title
        self._count = 0
        self._active = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_count(self, count: int) -> None:
        self._count = max(0, int(count))
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.mode)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = None
        border = None
        if self._active:
            background = _tint(colors["accent"], 34)
            border = _tint(colors["accent"], 96)
        elif self._hovered:
            background = _hover_color()
        paint_surface(painter, rect, 10, background=background, border=border)

        if self._active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["accent"]))
            painter.drawRoundedRect(QRectF(rect.left() + 1, rect.top() + 13, 3, rect.height() - 26), 1.5, 1.5)

        glyph = QRectF(rect.left() + 14, rect.center().y() - 9, 18, 18)
        self._draw_glyph(painter, glyph, QColor(colors["accent"] if self._active else colors["muted"]))
        painter.setFont(_font(self.font(), 13, QFont.Weight.DemiBold if self._active else QFont.Weight.Medium))
        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(rect.left() + 42, rect.top(), rect.width() - 84, rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )
        painter.setFont(_font(self.font(), 11))
        painter.setPen(QColor(colors["accent"] if self._active else colors["muted"]))
        painter.drawText(
            QRectF(rect.right() - 44, rect.top(), 32, rect.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            str(self._count),
        )
        painter.end()

    def _draw_glyph(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = rect.left()
        top = rect.top()
        width = rect.width()
        if self.mode == "installed":
            for index in range(3):
                painter.drawRoundedRect(QRectF(left, top + index * 6.4, width, 3.4), 1.7, 1.7)
            return
        if self.mode == "discover":
            painter.drawEllipse(QRectF(left + 1, top + 1, 11, 11))
            handle = QRectF(left + 10, top + 10, 6, 6)
            painter.drawLine(handle.topLeft(), handle.bottomRight())
            return
        for index in range(3):
            painter.drawEllipse(QRectF(left, top + index * 6.2, width, 4.2))


class _StatTile(QFrame):
    """顶部指标卡：参考 py-rm MetricCard（说明在上、数值在下）。"""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.caption = caption
        self._value = "0"
        self.setFixedSize(104, 66)

    def set_value(self, value: int | str) -> None:
        self._value = str(value)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = _card_rect(self)
        paint_surface(painter, rect, RADIUS, background=_surface_color(), border=_line_color())
        painter.setFont(_font(self.font(), 9))
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 10, rect.width() - 28, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.caption,
        )
        painter.setFont(_font(self.font(), 22, QFont.Weight.DemiBold, mono=True))
        painter.setPen(QColor(colors["text"]))
        painter.drawText(
            QRectF(rect.left() + 14, rect.top() + 27, rect.width() - 28, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._value,
        )
        painter.end()


# ----------------------------------------------------------------------
# DataView 条目
# ----------------------------------------------------------------------
def _build_entry(
    record: dict[str, Any],
    mode: str,
    kind: str,
    ctx: PageContext,
    on_toggle: Callable[[str, bool], None],
) -> QWidget:
    """紧凑条目：图标 + 标题/简介 + 状态开关，不承载任何操作按钮。"""
    root = QWidget()
    root.setStyleSheet("background: transparent;")
    item_id = str(record.get("id") or "")
    toggle: CToggleSwitch | None = None
    badges: list[tuple[str, bool]] = []

    if kind == "source":
        title = item_id or str(record.get("url") or "")
        subtitle = str(record.get("url") or "")
        icon = "icon_database"
        trust = str(record.get("trust") or "user")
        trust_text = ctx.text("sources.official", "官方") if trust == "official" else ctx.text("sources.user", "用户")
        badges.append((trust_text, trust == "official"))
    elif kind == "discover":
        title = str(record.get("name") or item_id)
        subtitle = str(record.get("summary") or item_id)
        icon = "icon_store"
        version = str(record.get("version") or "?")
        badges.append((f"v{version}", True))
        if record.get("installed"):
            badges.append((ctx.text("detail.installed", "已安装"), True))
        else:
            badges.append((ctx.text("detail.not_installed", "未安装"), False))
    else:
        title = str(record.get("name") or item_id)
        version = str(record.get("version") or "?")
        subtitle = str(record.get("summary") or f"{record.get('source') or '-'} · v{version}")
        icon = "icon_store"
        badges.append((f"v{version}", True))

    has_toggle = kind in {"installed", "source"} or (kind == "discover" and bool(record.get("installed")))
    if has_toggle:
        toggle = CToggleSwitch("", checked=bool(record.get("enabled", True)))
        toggle.toggled.connect(lambda checked: on_toggle(item_id, checked))

    if mode == "grid":
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_IconTile(icon, 40))
        top.addStretch(1)
        if toggle is not None:
            top.addWidget(toggle, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        title_label = _ThemedLabel(title, "entry")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(_ElidedLabel(subtitle, size=10))
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        for text, accent in badges:
            badge_row.addWidget(_Chip(text, accent=accent))
        badge_row.addStretch(1)
        layout.addLayout(badge_row)
        root.setMinimumHeight(132)
        return root

    layout = QHBoxLayout(root)
    layout.setContentsMargins(2, 2, 2, 2)
    layout.setSpacing(12)
    layout.addWidget(_IconTile(icon, 38), 0, Qt.AlignmentFlag.AlignTop)
    column = QVBoxLayout()
    column.setSpacing(4)
    title_row = QHBoxLayout()
    title_row.setSpacing(6)
    title_row.addWidget(_ThemedLabel(title, "entry"), 1)
    for text, accent in badges:
        title_row.addWidget(_Chip(text, accent=accent))
    column.addLayout(title_row)
    column.addWidget(_ElidedLabel(subtitle, size=10))
    layout.addLayout(column, 1)
    if toggle is not None:
        layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
    return root


# ----------------------------------------------------------------------
# 详情对话框
# ----------------------------------------------------------------------
def _meta_grid(items: list[tuple[str, str, bool]]) -> QWidget:
    box = QWidget()
    grid = QGridLayout(box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    for row, (key, value, mono) in enumerate(items):
        key_label = _ThemedLabel(key, "muted")
        key_label.setFixedWidth(72)
        value_label = _ThemedLabel(value or "—", "value", mono=mono)
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value_label, row, 1)
    grid.setColumnStretch(1, 1)
    return box


def _permission_block(permissions: list[str], ctx: PageContext) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(_ThemedLabel(ctx.text("detail.permissions", "权限"), "section"))
    if not permissions:
        layout.addWidget(_ThemedLabel("—", "muted"))
        return box
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)
    for index, permission in enumerate(permissions):
        grid.addWidget(_Chip(str(permission)), index // 3, index % 3)
    grid.setColumnStretch(3, 1)
    layout.addLayout(grid)
    return box


def _detail_hero(record: dict[str, Any], ctx: PageContext, *, installed: bool, icon: str) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    layout.addWidget(_IconTile(icon, 54), 0, Qt.AlignmentFlag.AlignTop)

    column = QVBoxLayout()
    column.setSpacing(4)
    title = str(record.get("name") or record.get("id") or "")
    title_label = _ThemedLabel(title, "title")
    title_label.setWordWrap(True)
    column.addWidget(title_label)
    column.addWidget(_ThemedLabel(str(record.get("id") or ""), "muted", mono=True))

    chips = QHBoxLayout()
    chips.setSpacing(6)
    chips.addWidget(_Chip(f"v{record.get('version') or '?'}", accent=True))
    if installed:
        chips.addWidget(_Chip(ctx.text("detail.installed", "已安装"), accent=True))
        enabled = bool(record.get("enabled", True))
        key = "installed.enabled" if enabled else "installed.disabled"
        fallback = "已启用" if enabled else "已停用"
        chips.addWidget(_Chip(ctx.text(key, fallback), accent=enabled))
    else:
        chips.addWidget(_Chip(ctx.text("detail.not_installed", "未安装")))
    chips.addStretch(1)
    column.addLayout(chips)
    layout.addLayout(column, 1)
    return box


class _DetailDialogBase:
    """详情对话框基类：统一关闭动画、引用清理与动作执行时机。"""

    def __init__(self, page: StorePage, title: str) -> None:
        self.page = page
        self.ctx = page.ctx
        parent = self.ctx.parent_window() or page.window()
        self.dialog = CDialog(title=title, width="lg", parent=parent)
        self._ran = False
        self._executed = False
        self.dialog.closed.connect(self._release)
        page._detail_dialog = self.dialog

    def _release(self) -> None:
        if self.page._detail_dialog is self.dialog:
            self.page._detail_dialog = None

    def open(self) -> None:
        self.dialog.open_dialog()

    def _run(self, callback: Callable[[], None]) -> None:
        """先收起详情，再执行动作，避免两个浮层同时出现。"""
        if self._ran:
            return
        self._ran = True

        def once() -> None:
            if self._executed:
                return
            self._executed = True
            callback()

        self.dialog.closed.connect(once)
        self.dialog.reject()

    def _action(
        self,
        key: str,
        fallback: str,
        callback: Callable[[], None],
        *,
        severity: str,
        variant: str,
        icon: str,
    ) -> CButton:
        return self.dialog.add_action_button(
            self.ctx.text(key, fallback),
            lambda: self._run(callback),
            severity=severity,
            variant=variant,
            icon=icon,
        )


class _PluginDetailDialog(_DetailDialogBase):
    """插件详情：基础信息、权限与更新/回滚/启停/卸载动作。"""

    def __init__(self, page: StorePage, record: dict[str, Any], *, installed: bool) -> None:
        self.record = dict(record)
        self.installed = bool(installed)
        self.available_version = ""
        if self.installed:
            if record.get("installed"):
                self.available_version = str(record.get("version") or "")
            manager = page._manager()
            if manager is not None:
                current = next(
                    (row for row in manager.installed_rows() if row.get("id") == self.record.get("id")),
                    None,
                )
                if current is not None:
                    for key in ("version", "source", "commit", "path", "permissions", "previous", "enabled", "compliance"):
                        self.record[key] = current.get(key)
        super().__init__(page, page.ctx.text("installed.detail_title", "插件详情"))
        self._build_body()
        self._build_footer()

    def _build_body(self) -> None:
        record = self.record
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(_detail_hero(record, self.ctx, installed=self.installed, icon="icon_store"))
        summary = str(record.get("summary") or self.ctx.text("detail.no_description", "暂无简介"))
        summary_label = _ThemedLabel(summary, "muted")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
        layout.addWidget(CHDiv())
        layout.addWidget(_ThemedLabel(self.ctx.text("detail.meta", "基础信息"), "section"))

        items: list[tuple[str, str, bool]] = []
        version = str(record.get("version") or "?")
        version_label = self.ctx.text("installed.version", "版本") if self.installed else self.ctx.text("detail.available", "可用版本")
        items.append((version_label, f"v{version}", False))
        if self.available_version and self.available_version != version:
            items.append((self.ctx.text("detail.available", "可用版本"), f"v{self.available_version}", False))
        source = str(record.get("source") or "")
        if source:
            items.append((self.ctx.text("installed.source", "来源"), source, False))
        commit = str(record.get("commit") or "")
        if commit:
            items.append((self.ctx.text("installed.commit", "提交"), commit[:12], True))
        path = str(record.get("path") or "")
        if path:
            items.append((self.ctx.text("installed.path", "目录"), path, True))
        previous = record.get("previous") or {}
        if isinstance(previous, dict) and previous.get("version"):
            items.append((self.ctx.text("detail.previous", "上一版本"), f"v{previous.get('version')}", False))
        compliance = record.get("compliance")
        if compliance not in (None, ""):
            items.append((self.ctx.text("detail.compliance", "合规级别"), str(compliance), False))
        author = str(record.get("author") or "")
        if author:
            items.append((self.ctx.text("detail.author", "作者"), author, False))
        categories = record.get("categories") or []
        if categories:
            items.append(
                (self.ctx.text("detail.categories", "分类"), " / ".join(str(item) for item in categories), False)
            )
        repository = str(record.get("repository") or "")
        if repository:
            items.append((self.ctx.text("detail.repository", "仓库"), repository, True))

        layout.addWidget(_meta_grid(items))
        layout.addWidget(_permission_block(list(record.get("permissions") or []), self.ctx))
        self.dialog.add_widget(body)

    def _build_footer(self) -> None:
        record = self.record
        plugin_id = str(record.get("id") or "")
        if not self.installed:
            self._action(
                "discover.install",
                "安装",
                lambda: self.page._install_plugin(record),
                severity="primary",
                variant="solid",
                icon="icon_add",
            )
            return

        previous = record.get("previous") or {}
        has_previous = isinstance(previous, dict) and bool(previous.get("version"))
        enabled = bool(record.get("enabled", True))
        self._action(
            "installed.remove",
            "卸载",
            lambda: self.page._remove_plugin(plugin_id),
            severity="danger",
            variant="outlined",
            icon="icon_trash",
        )
        self._action(
            "installed.disable" if enabled else "installed.enable",
            "停用" if enabled else "启用",
            lambda: self.page._set_plugin_enabled(plugin_id, not enabled),
            severity="warn",
            variant="outlined",
            icon="icon_close" if enabled else "icon_check",
        )
        rollback = self._action(
            "installed.rollback",
            "回滚",
            lambda: self.page._rollback_plugin(plugin_id),
            severity="secondary",
            variant="outlined",
            icon="icon_restore",
        )
        rollback.setEnabled(has_previous)
        self._action(
            "installed.update",
            "更新",
            lambda: self.page._update_plugin(plugin_id),
            severity="primary",
            variant="solid",
            icon="icon_refresh",
        )


class _SourceDetailDialog(_DetailDialogBase):
    """源详情：地址、信任级别、刷新与移除。"""

    def __init__(self, page: StorePage, record: dict[str, Any]) -> None:
        self.record = dict(record)
        super().__init__(page, page.ctx.text("sources.detail_title", "源详情"))
        self._build_body()
        self._build_footer()

    def _build_body(self) -> None:
        record = self.record
        enabled = bool(record.get("enabled", True))
        trust = str(record.get("trust") or "user")
        trust_text = self.ctx.text("sources.official", "官方") if trust == "official" else self.ctx.text("sources.user", "用户")

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        key = "installed.enabled" if enabled else "installed.disabled"
        hero = QWidget()
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(14)
        hero_row.addWidget(_IconTile("icon_database", 54), 0, Qt.AlignmentFlag.AlignTop)
        column = QVBoxLayout()
        column.setSpacing(4)
        title = _ThemedLabel(str(record.get("id") or ""), "title")
        title.setWordWrap(True)
        column.addWidget(title)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(_Chip(trust_text, accent=trust == "official"))
        chips.addWidget(_Chip(self.ctx.text(key, "已启用" if enabled else "已停用"), accent=enabled))
        chips.addStretch(1)
        column.addLayout(chips)
        hero_row.addLayout(column, 1)
        layout.addWidget(hero)

        url_label = _ThemedLabel(str(record.get("url") or ""), "muted", mono=True)
        url_label.setWordWrap(True)
        layout.addWidget(url_label)
        layout.addWidget(CHDiv())
        layout.addWidget(_ThemedLabel(self.ctx.text("detail.meta", "基础信息"), "section"))
        layout.addWidget(
            _meta_grid(
                [
                    (self.ctx.text("detail.source_id", "源 ID"), str(record.get("id") or ""), True),
                    (self.ctx.text("detail.url", "地址"), str(record.get("url") or ""), True),
                    (self.ctx.text("detail.trust", "信任级别"), trust_text, False),
                    (self.ctx.text("detail.status", "状态"), self.ctx.text(key, "已启用" if enabled else "已停用"), False),
                    (self.ctx.text("installed.commit", "提交"), str(record.get("commit") or "-")[:12], True),
                    (self.ctx.text("detail.last_refresh", "最近刷新"), str(record.get("last_refresh") or "-"), False),
                ]
            )
        )
        self.dialog.add_widget(body)

    def _build_footer(self) -> None:
        source_id = str(self.record.get("id") or "")
        self._action(
            "sources.remove",
            "移除",
            lambda: self.page._remove_source(source_id),
            severity="danger",
            variant="outlined",
            icon="icon_trash",
        )
        self._action(
            "sources.refresh",
            "刷新",
            lambda: self.page._refresh_source(source_id),
            severity="primary",
            variant="solid",
            icon="icon_refresh",
        )


# ----------------------------------------------------------------------
# 三个数据面板
# ----------------------------------------------------------------------
class _StorePanel(QWidget):
    """DataView 面板基类：统一工具栏、视图切换与数据视图。"""

    def __init__(self, page: StorePage, empty_text: str, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._view_mode = "list"
        self.data_view = CDataView(
            [],
            self._template,
            layout="list",
            columns=2,
            empty_text=empty_text,
            parent=self,
        )
        self._build()
        self.refresh()

    def _build(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _template(self, record: dict[str, Any]) -> QWidget:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def refresh(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _manager(self):
        return self.page._manager()

    def _sources(self):
        return self.page._sources()

    def _add_view_toggle(self, toolbar: QHBoxLayout) -> None:
        options = [self.ctx.text("view.grid", "网格"), self.ctx.text("view.list", "列表")]
        self.view_toggle = CSelectButton(options, index=1, size="sm")
        self.view_toggle.setFixedWidth(120)
        self.view_toggle.selectionChanged.connect(self._on_view_index)
        toolbar.addWidget(self.view_toggle)

    def _on_view_index(self, index: int) -> None:
        self._view_mode = "grid" if index == 0 else "list"
        self.data_view.set_layout(self._view_mode)


class _InstalledPanel(_StorePanel):
    """已安装：过滤 + DataView；条目开关直接启停，详情承载其余操作。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        self._rows: list[dict[str, Any]] = []
        super().__init__(page, page.ctx.text("installed.empty", "还没有安装插件，去「发现」看看"), parent)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filter = CInputText(placeholder=self.ctx.text("installed.filter", "过滤插件…"), icon="icon_search")
        self.filter.setFixedWidth(240)
        toolbar.addWidget(self.filter)
        toolbar.addStretch(1)
        self._add_view_toggle(toolbar)
        root.addLayout(toolbar)
        root.addWidget(self.data_view, 1)

        self.filter.textChanged.connect(self._apply_filter)
        self.data_view.itemClicked.connect(self._open_detail)

    def _template(self, record: dict[str, Any]) -> QWidget:
        return _build_entry(record, self._view_mode, "installed", self.ctx, self._on_toggle)

    def _on_toggle(self, plugin_id: str, enabled: bool) -> None:
        self.page._set_plugin_enabled(plugin_id, enabled)

    def _apply_filter(self) -> None:
        needle = self.filter.text().strip().lower()
        rows = [
            row
            for row in self._rows
            if not needle
            or needle in f"{row.get('id')} {row.get('name')} {row.get('source')}".lower()
        ]
        self.data_view.set_rows(rows)

    def refresh(self) -> None:
        manager = self._manager()
        self._rows = list(manager.installed_rows()) if manager is not None else []
        self._apply_filter()

    def _open_detail(self, record: dict[str, Any]) -> None:
        _PluginDetailDialog(self.page, record, installed=True).open()


class _DiscoverPanel(_StorePanel):
    """发现：搜索结果（含已安装）与安装/启停详情。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(page, page.ctx.text("discover.empty", "没有匹配的可安装插件"), parent)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.query = CInputText(
            placeholder=self.ctx.text("discover.placeholder", "搜索插件名称、ID 或简介…"),
            icon="icon_search",
        )
        self.refresh_btn = CButton(
            "",
            icon="icon_refresh",
            variant="text",
            size="sm",
            fixed_width=34,
            icon_size=20,
        )
        self.refresh_btn.setToolTip(self.ctx.text("discover.refresh_sources", "刷新源"))
        toolbar.addWidget(self.query, 1)
        toolbar.addWidget(self.refresh_btn)
        self._add_view_toggle(toolbar)
        root.addLayout(toolbar)
        root.addWidget(self.data_view, 1)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self.search)
        self.query.textChanged.connect(lambda: self._search_timer.start())
        self.query.returnPressed.connect(self.search)
        self.refresh_btn.clicked.connect(self._refresh_sources)
        self.data_view.itemClicked.connect(self._open_detail)

    def _template(self, record: dict[str, Any]) -> QWidget:
        return _build_entry(record, self._view_mode, "discover", self.ctx, self._on_toggle)

    def refresh(self) -> None:
        self.search()

    def search(self) -> None:
        manager = self._manager()
        if manager is None:
            self.data_view.set_rows([])
            self.page.update_discover_count(0)
            return
        needle = self.query.text().strip().lower()
        installed = {str(row.get("id") or ""): row for row in manager.installed_rows()}
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in manager.search(needle):
            plugin_id = str(row.get("id") or "")
            if plugin_id in seen:
                continue
            seen.add(plugin_id)
            current = installed.get(plugin_id)
            row["installed"] = current is not None
            row["enabled"] = bool(current.get("enabled")) if current is not None else False
            row["installed_version"] = str(current.get("version") or "") if current is not None else ""
            rows.append(row)

        # 已安装但源索引暂时没有的插件仍要出现在发现页，并标记「已安装」。
        for plugin_id, current in installed.items():
            if plugin_id in seen:
                continue
            name = str(current.get("name") or plugin_id)
            summary = str(current.get("summary") or "")
            if needle and needle not in f"{plugin_id} {name} {summary}".lower():
                continue
            rows.append(
                {
                    "id": plugin_id,
                    "name": name,
                    "summary": summary,
                    "version": str(current.get("version") or "?"),
                    "source": str(current.get("source") or ""),
                    "permissions": list(current.get("permissions") or []),
                    "compliance": current.get("compliance"),
                    "repository": str(current.get("repository") or ""),
                    "installed": True,
                    "enabled": bool(current.get("enabled")),
                    "installed_version": str(current.get("version") or ""),
                }
            )
        self.data_view.set_rows(rows)
        self.page.update_discover_count(len(rows))

    def _on_toggle(self, plugin_id: str, enabled: bool) -> None:
        self.page._set_plugin_enabled(plugin_id, enabled)

    def _open_detail(self, record: dict[str, Any]) -> None:
        _PluginDetailDialog(self.page, record, installed=bool(record.get("installed"))).open()

    def _refresh_sources(self) -> None:
        self.page._refresh_sources()


class _SourcesPanel(_StorePanel):
    """源：添加输入 + DataView；开关控制源是否参与索引。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(page, page.ctx.text("sources.empty", "还没有配置插件源"), parent)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.url = CInputText(placeholder=self.ctx.text("sources.placeholder", "Git 仓库地址"))
        self.add_btn = CButton(self.ctx.text("sources.add", "添加"), size="sm")
        toolbar.addWidget(self.url, 1)
        toolbar.addWidget(self.add_btn)
        self._add_view_toggle(toolbar)
        root.addLayout(toolbar)
        root.addWidget(self.data_view, 1)

        self.add_btn.clicked.connect(self._add)
        self.url.returnPressed.connect(self._add)
        self.data_view.itemClicked.connect(self._open_detail)

    def _template(self, record: dict[str, Any]) -> QWidget:
        return _build_entry(record, self._view_mode, "source", self.ctx, self._on_toggle)

    def refresh(self) -> None:
        sources = self._sources()
        rows = (
            [
                {
                    "id": record.source_id,
                    "url": record.url,
                    "trust": record.trust,
                    "enabled": record.enabled,
                    "commit": record.commit,
                    "last_refresh": record.last_refresh,
                }
                for record in sources.list()
            ]
            if sources is not None
            else []
        )
        self.data_view.set_rows(rows)

    def _add(self) -> None:
        if self.page._add_source(self.url.text().strip()):
            self.url.setText("")

    def _on_toggle(self, source_id: str, enabled: bool) -> None:
        self.page._set_source_enabled(source_id, enabled)

    def _open_detail(self, record: dict[str, Any]) -> None:
        _SourceDetailDialog(self.page, record).open()


# ----------------------------------------------------------------------
# 页面
# ----------------------------------------------------------------------
class StorePage(QWidget):
    """插件管理工作台。"""

    def __init__(self, ctx: PageContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        from sllkgui.gallery.runtime import current_runtime

        self.runtime = current_runtime()
        self._mode_cards: dict[str, _ModeCard] = {}
        self._detail_dialog: CDialog | None = None
        self._build()
        self.switch_mode("installed")
        self.refresh_stats()
        get_theme_manager().subscribe(self._theme_changed)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(12)

        hero = QHBoxLayout()
        hero.setSpacing(14)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_ThemedLabel("SLLKGUI / PLUGINS", "eyebrow"))
        titles.addWidget(_ThemedLabel(self.ctx.text("store.title", "插件管理"), "title"))
        subtitle = _ThemedLabel(self.ctx.text("store.subtitle", "已安装、发现与来源，在一页内完成"), "muted")
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        hero.addLayout(titles, 1)

        self.stat_installed = _StatTile(self.ctx.text("stats.installed", "已安装"))
        self.stat_enabled = _StatTile(self.ctx.text("stats.enabled", "启用中"))
        self.stat_sources = _StatTile(self.ctx.text("stats.sources", "来源"))
        hero.addWidget(self.stat_installed)
        hero.addWidget(self.stat_enabled)
        hero.addWidget(self.stat_sources)
        root.addLayout(hero)

        body = QHBoxLayout()
        body.setSpacing(12)

        rail = QVBoxLayout()
        rail.setContentsMargins(10, 10, 10, 10)
        rail.setSpacing(4)
        for mode, key, caption in (
            ("installed", "modes.installed", "已安装"),
            ("discover", "modes.discover", "发现"),
            ("sources", "modes.sources", "源"),
        ):
            card = _ModeCard(mode, self.ctx.text(key, caption))
            card.clicked.connect(self.switch_mode)
            self._mode_cards[mode] = card
            rail.addWidget(card)
        rail.addStretch(1)
        rail_host = _Panel()
        rail_host.setLayout(rail)
        rail_host.setFixedWidth(232)
        body.addWidget(rail_host)

        self.stack = QStackedWidget()
        self.installed_panel = _InstalledPanel(self)
        self.discover_panel = _DiscoverPanel(self)
        self.sources_panel = _SourcesPanel(self)
        self.stack.addWidget(self.installed_panel)
        self.stack.addWidget(self.discover_panel)
        self.stack.addWidget(self.sources_panel)
        workspace = _Panel()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 14, 16, 14)
        workspace_layout.setSpacing(10)
        workspace_layout.addWidget(self.stack)
        body.addWidget(workspace, 1)
        root.addLayout(body, 1)

    # ------------------------------------------------------------------
    # 模式
    # ------------------------------------------------------------------
    def switch_mode(self, mode: str) -> None:
        mapping = {
            "installed": self.installed_panel,
            "discover": self.discover_panel,
            "sources": self.sources_panel,
        }
        panel = mapping.get(mode)
        if panel is None:
            return
        self.stack.setCurrentWidget(panel)
        for key, card in self._mode_cards.items():
            card.set_active(key == mode)
        if mode == "installed":
            self.installed_panel.refresh()
        elif mode == "discover":
            self.discover_panel.search()
        else:
            self.sources_panel.refresh()
        self.refresh_stats()

    # ------------------------------------------------------------------
    # 数据源
    # ------------------------------------------------------------------
    def _manager(self):
        return getattr(self.runtime, "manager", None)

    def _sources(self):
        return getattr(self.runtime, "sources", None)

    # ------------------------------------------------------------------
    # 状态 / 刷新
    # ------------------------------------------------------------------
    def set_status(self, message: str, level: str = "info") -> None:
        """用基座通知条反馈操作结果：浮在页面上，不占布局，自动堆叠与消失。"""
        if not message:
            return
        window = self.ctx.parent_window()
        if window is None:
            return
        severity = {"error": "error", "warning": "warn"}.get(level, level)
        life = 6000 if level in {"error", "warning"} else 3000
        CToast.show_message(
            window,
            message,
            self.ctx.text("store.title", "插件管理"),
            severity,
            life=life,
            offset_top=_toast_offset(window),
        )

    def refresh_stats(self) -> None:
        manager = self._manager()
        rows = list(manager.installed_rows()) if manager is not None else []
        sources = self._sources()
        source_count = len(sources.list()) if sources is not None else 0
        discover = getattr(self, "discover_panel", None)
        discover_count = len(discover.data_view.rows()) if discover is not None else 0
        self.stat_installed.set_value(len(rows))
        self.stat_enabled.set_value(sum(1 for row in rows if row.get("enabled")))
        self.stat_sources.set_value(source_count)
        self._mode_cards["installed"].set_count(len(rows))
        self._mode_cards["discover"].set_count(discover_count)
        self._mode_cards["sources"].set_count(source_count)

    def update_discover_count(self, count: int) -> None:
        self._mode_cards["discover"].set_count(max(0, int(count)))

    def refresh_all(self) -> None:
        self.installed_panel.refresh()
        self.discover_panel.search()
        self.sources_panel.refresh()
        self.refresh_stats()

    def schedule_reload(self) -> None:
        window = self.ctx.parent_window()
        if window is not None and hasattr(window, "reload_plugins"):
            QTimer.singleShot(120, window.reload_plugins)

    def _theme_changed(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.update()

    # ------------------------------------------------------------------
    # 插件动作
    # ------------------------------------------------------------------
    def _fail(self, code: str, message: str, exc: Exception) -> None:
        self.ctx.report_error(code, message, str(exc))
        self.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")

    def _set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        manager = self._manager()
        if manager is None:
            return
        try:
            manager.set_enabled(plugin_id, enabled)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001 - 页面必须保持可用
            self._fail("PLUGIN_STORE_TOGGLE_FAILED", f"切换插件状态失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)
        self.schedule_reload()

    def _update_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        try:
            with self.ctx.timing("plugin_store.update"):
                result = manager.update(plugin_id)
            if result.get("updated"):
                message = self.ctx.text("status.update_done", "已更新到 v{version}").format(
                    version=result.get("version") or ""
                )
            else:
                message = self.ctx.text("status.up_to_date", "已是最新版本")
            self.set_status(message, "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_UPDATE_FAILED", f"更新失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)
        self.schedule_reload()

    def _rollback_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        try:
            with self.ctx.timing("plugin_store.rollback"):
                manager.rollback(plugin_id)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_ROLLBACK_FAILED", f"回滚失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)
        self.schedule_reload()

    def _remove_plugin(self, plugin_id: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("installed.remove", "卸载"),
            message=self.ctx.text("confirm.remove", "确定卸载该插件？数据目录默认保留。"),
            severity="danger",
        )
        if not ok:
            return
        try:
            with self.ctx.timing("plugin_store.remove"):
                manager.remove(plugin_id)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_REMOVE_FAILED", f"卸载失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)
        self.schedule_reload()

    def _install_plugin(self, record: dict[str, Any]) -> None:
        manager = self._manager()
        if manager is None:
            return
        plugin_id = str(record.get("id") or "")
        permissions = ", ".join(str(item) for item in record.get("permissions") or []) or "-"
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("discover.install", "安装"),
            message=self.ctx.text("confirm.install", "安装 {id} v{version}？权限：{permissions}").format(
                id=plugin_id,
                version=record.get("version") or "?",
                permissions=permissions,
            ),
            severity="info",
        )
        if not ok:
            return
        try:
            with self.ctx.timing("plugin_store.install"):
                manager.install(plugin_id, source_id=str(record.get("source") or ""))
            self.set_status(
                self.ctx.text("status.install_done", "已安装 {count} 个插件").format(count=1), "success"
            )
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_INSTALL_FAILED", f"安装失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)
        self.schedule_reload()

    # ------------------------------------------------------------------
    # 源动作
    # ------------------------------------------------------------------
    def _add_source(self, url: str) -> bool:
        sources = self._sources()
        if sources is None or not url:
            return False
        try:
            record = sources.add(url, refresh=True)
            self.set_status(
                self.ctx.text("sources.added", "已添加源 {id}").format(id=record.source_id), "success"
            )
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_ADD_FAILED", f"添加源失败: {exc}", exc)
            return False
        QTimer.singleShot(0, self.refresh_all)
        return True

    def _refresh_source(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None:
            return
        try:
            with self.ctx.timing("plugin_store.source_refresh"):
                sources.refresh(source_id)
            self.set_status(self.ctx.text("status.refresh_done", "源刷新完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_REFRESH_FAILED", f"刷新源失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        try:
            with self.ctx.timing("plugin_store.source_refresh_all"):
                sources.refresh_all()
            self.set_status(self.ctx.text("status.refresh_done", "源刷新完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)

    def _remove_source(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None:
            return
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("sources.remove", "移除"),
            message=self.ctx.text("sources.confirm_remove", "移除源 {id}？已安装插件不受影响。").format(
                id=source_id
            ),
            severity="warn",
        )
        if not ok:
            return
        try:
            sources.remove(source_id)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_REMOVE_FAILED", f"移除源失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)

    def _set_source_enabled(self, source_id: str, enabled: bool) -> None:
        sources = self._sources()
        if sources is None:
            return
        try:
            sources.set_enabled(source_id, enabled)
            self.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self._fail("PLUGIN_STORE_SOURCE_TOGGLE_FAILED", f"切换源状态失败: {exc}", exc)
        QTimer.singleShot(0, self.refresh_all)


__all__ = ["PageContext", "StorePage", "build_plugin_store_page"]
