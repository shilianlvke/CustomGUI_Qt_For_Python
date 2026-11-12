"""插件管理（基座原生页面）：模式导轨 + 工作区。

不再作为 ``core_plugins`` 里的插件分发，而是 ``gallery`` 与 ``run`` 两种
模式都常驻的基座页面；由 :mod:`sllkgui.guis.windows.main_window.native_pages`
注册到左菜单与页面路由。

布局沿用三段式工作台（已安装 / 发现 / 源）：

- 左侧导轨负责切换模式并显示计数；
- 已安装：卡片列表 + 详情清单 + 工具栏动作；
- 发现：搜索结果卡片流，每张卡片直接安装；
- 源：紧凑行 + 添加输入，逐行刷新/移除。

自绘表面颜色实时取自 ``panel_colors()``，切换主题无需重建。
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
    QScrollArea,
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
from sllkgui.guicore import CButton, CConfirmDialog, CHDiv, CInputText, CToast
from sllkgui.guicore.custom_ui.panels.style import RADIUS, paint_surface, panel_colors
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


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _card_rect(widget: QWidget) -> QRectF:
    return QRectF(widget.rect()).adjusted(0.75, 0.75, -0.75, -0.75)


def _surface_color() -> QColor:
    """外层卡片底色：与 ``CCard`` 的 ``surface_card`` 一致（#44475a）。"""
    return QColor(card_surface_color())


def _inset_color() -> QColor:
    """内层卡片底色：页面底色，和外层卡片形成明确层级（#333645）。"""
    return QColor(ColorPalette.custom_bg_one)


def _line_color() -> QColor:
    """卡片描边：取交互按压层，保证在两种底色上都清晰可见（#595D75）。"""
    return QColor(get_design_tokens().colors.surface_interactive_pressed)


def _hover_color() -> QColor:
    return QColor(ColorPalette.custom_dark_four)


#: 与 py-rm page_kit 对齐的排版角色
_ROLE_SIZES = {"eyebrow": 8, "title": 18, "section": 12, "metric": 24, "body": 10, "muted": 9}


class _ThemedLabel(QLabel):
    """按角色取色的文本标签；主题切换时自动刷新颜色。"""

    def __init__(self, text: str = "", role: str = "body", mono: bool = False, parent=None) -> None:
        super().__init__(text, parent)
        self._role = role
        family = _MONO_FAMILIES[0] if mono else AppSettings.family
        weight = QFont.Weight.DemiBold if role in {"eyebrow", "title", "section", "metric"} else QFont.Weight.Normal
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
            "muted": ColorPalette.custom_text_description,
            "body": ColorPalette.custom_text_foreground,
        }.get(self._role, ColorPalette.custom_text_foreground)
        self.setStyleSheet(f"color: {color}; background: transparent;")


class _Panel(QFrame):
    """py-rm Card 风格容器：圆角 + 明显描边 + 分层底色。"""

    def __init__(self, level: str = "outer", parent=None) -> None:
        super().__init__(parent)
        self._level = level
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = _surface_color() if self._level == "outer" else _inset_color()
        paint_surface(painter, _card_rect(self), RADIUS, background=background, border=_line_color())
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
    """单行省略文本：用于 ID、commit、URL。"""

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


class _EmptyCard(QFrame):
    """空态：虚线圆角卡片 + 居中提示。"""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self.setMinimumHeight(84)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = _card_rect(self)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_line_color(), 1, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(rect, RADIUS, RADIUS)
        painter.setFont(_font(self.font(), 10))
        painter.setPen(QColor(panel_colors()["muted"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
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


class _PluginCard(QFrame):
    """已安装插件卡片：名称、版本、状态与权限。"""

    selected = Signal(str)

    def __init__(self, record: dict[str, Any], enabled_text: str, disabled_text: str, parent=None) -> None:
        super().__init__(parent)
        self.record = record
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self._selected = False
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def plugin_id(self) -> str:
        return str(self.record.get("id") or "")

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
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
            self.selected.emit(self.plugin_id)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = _card_rect(self)
        background = _hover_color() if self._hovered and not self._selected else _inset_color()
        border = QColor(colors["accent"]) if self._selected else _line_color()
        paint_surface(painter, rect, RADIUS, background=background, border=border)

        name = str(self.record.get("name") or self.record.get("id") or "")
        version = f"v{self.record.get('version') or '?'}"
        enabled = bool(self.record.get("enabled"))
        painter.setFont(_font(self.font(), 12, QFont.Weight.DemiBold))
        painter.setPen(QColor(colors["text"]))
        metrics = QFontMetrics(painter.font())
        name_width = max(60, int(rect.width()) - 210)
        painter.drawText(
            QRectF(rect.left() + 16, rect.top() + 10, name_width, 22),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_width),
        )

        pill_font = _font(self.font(), 10, QFont.Weight.DemiBold)
        painter.setFont(pill_font)
        version_width = QFontMetrics(pill_font).horizontalAdvance(version) + 16
        pill = QRectF(rect.right() - version_width - 14, rect.top() + 10, version_width, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["accent"]))
        painter.drawRoundedRect(pill, 10, 10)
        painter.setPen(QColor(colors["on_accent"]))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, version)

        status_color = QColor(colors["accent"] if enabled else colors["muted"])
        painter.setBrush(status_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(pill.left() - 14, pill.center().y() - 3, 6, 6))
        painter.setFont(_font(self.font(), 10))
        painter.setPen(status_color)
        painter.drawText(
            QRectF(pill.left() - 74, pill.top(), 56, pill.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._enabled_text if enabled else self._disabled_text,
        )

        painter.setFont(_font(self.font(), 10, mono=True))
        painter.setPen(QColor(colors["muted"]))
        sample = f"{self.record.get('id')} · {str(self.record.get('commit') or '')[:10]}"
        painter.drawText(
            QRectF(rect.left() + 16, rect.top() + 34, rect.width() - 32, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(painter.font()).elidedText(sample, Qt.TextElideMode.ElideRight, int(rect.width()) - 28),
        )

        x = rect.left() + 16
        y = rect.top() + 60
        x += self._draw_pill(painter, x, y, str(self.record.get("source") or "-"), colors)
        permissions = [str(item) for item in self.record.get("permissions") or []]
        for permission in permissions[:3]:
            x += self._draw_pill(painter, x, y, permission, colors)
        if len(permissions) > 3:
            self._draw_pill(painter, x, y, f"+{len(permissions) - 3}", colors)
        painter.end()

    @staticmethod
    def _draw_pill(painter: QPainter, x: float, y: float, text: str, colors: dict) -> float:
        font = _font(painter.font(), 10)
        painter.setFont(font)
        width = QFontMetrics(font).horizontalAdvance(text) + 16
        rect = QRectF(x, y, width, 20)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QColor(colors["text"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        return width + 6


class _ResultCard(QFrame):
    """发现：搜索结果卡片，直接安装。"""

    def __init__(
        self,
        record: dict[str, Any],
        install_text: str,
        permission_text: str,
        on_install: Callable[[dict[str, Any]], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(122)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = str(record.get("name") or record.get("id") or "")
        top.addWidget(_ThemedLabel(name, "section"))
        top.addWidget(_Chip(f"v{record.get('version') or '?'}", accent=True))
        top.addStretch(1)
        layout.addLayout(top)

        summary_label = _ThemedLabel(str(record.get("summary") or record.get("id") or ""), "muted")
        summary_label.setWordWrap(True)
        summary_label.setFixedHeight(32)
        layout.addWidget(summary_label)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addWidget(_Chip(str(record.get("source") or "-")))
        permissions = list(record.get("permissions") or [])
        if permissions:
            bottom.addWidget(_Chip(permission_text.format(count=len(permissions))))
        bottom.addStretch(1)
        install = CButton(install_text, size="sm", severity="success", fixed_width=64)
        install.clicked.connect(lambda: on_install(self.record))
        bottom.addWidget(install)
        layout.addLayout(bottom)

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        colors = panel_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(
            painter,
            _card_rect(self),
            RADIUS,
            background=_hover_color() if self._hovered else _inset_color(),
            border=_tint(colors["accent"], 120) if self._hovered else _line_color(),
        )
        painter.end()


class _SourceRow(QFrame):
    """来源：紧凑行 + 逐行刷新/移除。"""

    def __init__(
        self,
        record: dict[str, Any],
        trust_texts: dict[str, str],
        refresh_text: str,
        remove_text: str,
        on_refresh: Callable[[str], None],
        on_remove: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(10)
        trust = str(record.get("trust") or "user")
        layout.addWidget(_Chip(trust_texts.get(trust, trust), accent=trust == "official"))

        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(_ThemedLabel(str(record.get("id") or ""), "body"))
        info.addWidget(_ElidedLabel(str(record.get("url") or ""), mono=True))
        layout.addLayout(info, 1)

        source_id = str(record.get("id") or "")
        refresh = CButton(refresh_text, size="sm", severity="secondary", variant="text", fixed_width=48)
        refresh.clicked.connect(lambda: on_refresh(source_id))
        remove = CButton(remove_text, size="sm", severity="danger", variant="text", fixed_width=48)
        remove.clicked.connect(lambda: on_remove(source_id))
        layout.addWidget(refresh)
        layout.addWidget(remove)

    def enterEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_surface(
            painter,
            _card_rect(self),
            RADIUS,
            background=_hover_color() if self._hovered else _inset_color(),
            border=_line_color(),
        )
        painter.end()


class _InstalledPanel(QWidget):
    """已安装：过滤、卡片、详情与操作。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._rows: list[dict[str, Any]] = []
        self._cards: list[_PluginCard] = []
        self._selected_id = ""
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filter = CInputText(placeholder=self.ctx.text("installed.filter", "过滤插件…"), icon="icon_search")
        self.filter.setFixedWidth(220)
        self.update_btn = CButton(self.ctx.text("installed.update", "更新"), size="sm")
        self.rollback_btn = CButton(
            self.ctx.text("installed.rollback", "回滚"), size="sm", severity="secondary", variant="outlined"
        )
        self.toggle_btn = CButton(
            self.ctx.text("installed.disable", "停用"), size="sm", severity="warn", variant="outlined"
        )
        self.remove_btn = CButton(
            self.ctx.text("installed.remove", "卸载"), size="sm", severity="danger", variant="outlined"
        )
        toolbar.addWidget(self.filter)
        toolbar.addStretch(1)
        for button in (self.update_btn, self.rollback_btn, self.toggle_btn, self.remove_btn):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }"
        )
        self.cards_host = QWidget()
        self.cards_host.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 6, 0)
        self.cards_layout.setSpacing(8)
        self.scroll.setWidget(self.cards_host)
        body.addWidget(self.scroll, 1)
        body.addWidget(self._build_detail())
        layout.addLayout(body, 1)

        self.filter.textChanged.connect(self._rebuild_cards)
        self.update_btn.clicked.connect(lambda: self._run("update"))
        self.rollback_btn.clicked.connect(lambda: self._run("rollback"))
        self.toggle_btn.clicked.connect(self._toggle)
        self.remove_btn.clicked.connect(self._remove)
        self._update_actions()

    def _build_detail(self) -> QWidget:
        card = _Panel("inner")
        card.setFixedWidth(310)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(10)
        box.addWidget(_ThemedLabel(self.ctx.text("installed.detail_title", "插件详情"), "section"))
        box.addWidget(CHDiv())
        self.detail_hint = _ThemedLabel(self.ctx.text("installed.select_hint", "选择一个插件查看详情"), "muted")
        self.detail_hint.setWordWrap(True)
        box.addWidget(self.detail_hint)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        box.addLayout(grid)
        self.detail_values: dict[str, QLabel] = {}
        for row, (key, caption) in enumerate(
            (
                ("version", self.ctx.text("installed.version", "版本")),
                ("source", self.ctx.text("installed.source", "来源")),
                ("commit", self.ctx.text("installed.commit", "提交")),
                ("path", self.ctx.text("installed.path", "目录")),
                ("permissions", self.ctx.text("installed.permissions", "权限")),
            )
        ):
            grid.addWidget(_ThemedLabel(caption, "muted"), row, 0, Qt.AlignmentFlag.AlignTop)
            value = _ThemedLabel("-", "body")
            value.setWordWrap(True)
            grid.addWidget(value, row, 1)
            self.detail_values[key] = value
        box.addStretch(1)
        return card

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _manager(self):
        return getattr(self.page.runtime, "manager", None)

    def refresh(self) -> None:
        manager = self._manager()
        self._rows = list(manager.installed_rows()) if manager is not None else []
        if self._selected_id not in {row["id"] for row in self._rows}:
            self._selected_id = self._rows[0]["id"] if self._rows else ""
        self._rebuild_cards()
        self._show_detail()
        self._update_actions()

    def _rebuild_cards(self) -> None:
        needle = self.filter.text().strip().lower() if hasattr(self, "filter") else ""
        _clear_layout(self.cards_layout)
        self._cards = []
        rows = [row for row in self._rows if not needle or needle in f"{row.get('id')} {row.get('source')}".lower()]
        if not rows:
            self.cards_layout.addWidget(_EmptyCard(self.ctx.text("installed.empty", "还没有安装插件")))
        for row in rows:
            card = _PluginCard(
                row,
                self.ctx.text("installed.enabled", "已启用"),
                self.ctx.text("installed.disabled", "已停用"),
            )
            card.set_selected(card.plugin_id == self._selected_id)
            card.selected.connect(self._select)
            self.cards_layout.addWidget(card)
            self._cards.append(card)
        self.cards_layout.addStretch(1)
        self._show_detail()

    def _select(self, plugin_id: str) -> None:
        self._selected_id = plugin_id
        for card in self._cards:
            card.set_selected(card.plugin_id == plugin_id)
        self._show_detail()
        self._update_actions()

    def _selected(self) -> dict[str, Any] | None:
        return next((row for row in self._rows if row.get("id") == self._selected_id), None)

    def _show_detail(self) -> None:
        row = self._selected()
        has_row = row is not None
        self.detail_hint.setVisible(not has_row)
        for value in self.detail_values.values():
            value.setVisible(has_row)
        if not row:
            return
        self.detail_values["version"].setText(str(row.get("version") or "-"))
        self.detail_values["source"].setText(str(row.get("source") or "-"))
        self.detail_values["commit"].setText(str(row.get("commit") or "-")[:12])
        self.detail_values["path"].setText(str(row.get("path") or "-"))
        self.detail_values["permissions"].setText(", ".join(row.get("permissions") or []) or "-")

    def _update_actions(self) -> None:
        row = self._selected()
        enabled = bool(row and row.get("enabled"))
        self.toggle_btn.setText(
            self.ctx.text("installed.disable", "停用") if enabled else self.ctx.text("installed.enable", "启用")
        )
        for button in (self.update_btn, self.rollback_btn, self.toggle_btn, self.remove_btn):
            button.setEnabled(row is not None)

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------
    def _run(self, name: str) -> None:
        manager = self._manager()
        if manager is None or not self._selected_id:
            return
        plugin_id = self._selected_id
        try:
            with self.ctx.timing(f"plugin_store.{name}"):
                result = getattr(manager, name)(plugin_id)
            self.ctx.log(f"{name}: {result}")
            self.ctx.event(f"plugin_store.{name}", {"result": str(result)})
            self.page.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001 - 页面必须保持可用
            self.ctx.report_error("CORE_STORE_ACTION_FAILED", f"{name} 失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)
        self.page.schedule_reload()

    def _toggle(self) -> None:
        row = self._selected()
        manager = self._manager()
        if row is None or manager is None:
            return
        manager.set_enabled(str(row["id"]), not bool(row.get("enabled")))
        QTimer.singleShot(0, self.page.refresh_all)
        self.page.schedule_reload()

    def _remove(self) -> None:
        if not self._selected_id:
            return
        plugin_id = self._selected_id
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("installed.remove", "卸载"),
            message=self.ctx.text("confirm.remove", "确定卸载该插件？数据目录默认保留。"),
            severity="danger",
        )
        manager = self._manager()
        if not ok or manager is None:
            return
        try:
            manager.remove(plugin_id)
            self.page.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_REMOVE_FAILED", f"卸载失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        self._selected_id = ""
        QTimer.singleShot(0, self.page.refresh_all)
        self.page.schedule_reload()


class _DiscoverPanel(QWidget):
    """发现：搜索结果卡片流，直接安装。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._build()
        self.search()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.query = CInputText(
            placeholder=self.ctx.text("discover.placeholder", "搜索插件名称、ID 或简介…"),
            icon="icon_search",
        )
        self.search_btn = CButton(self.ctx.text("discover.search", "搜索"), size="sm")
        self.refresh_btn = CButton(
            self.ctx.text("discover.refresh_sources", "刷新源"),
            size="sm",
            severity="secondary",
            variant="outlined",
        )
        toolbar.addWidget(self.query, 1)
        toolbar.addWidget(self.search_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }"
        )
        self.results_host = QWidget()
        self.results_host.setStyleSheet("background: transparent;")
        self.results_grid = QGridLayout(self.results_host)
        self.results_grid.setContentsMargins(0, 0, 6, 0)
        self.results_grid.setHorizontalSpacing(10)
        self.results_grid.setVerticalSpacing(10)
        self.results_grid.setColumnStretch(0, 1)
        self.results_grid.setColumnStretch(1, 1)
        self.scroll.setWidget(self.results_host)
        layout.addWidget(self.scroll, 1)

        self.search_btn.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        self.refresh_btn.clicked.connect(self._refresh_sources)

    def _manager(self):
        return getattr(self.page.runtime, "manager", None)

    def _sources(self):
        return getattr(self.page.runtime, "sources", None)

    def search(self) -> None:
        _clear_layout(self.results_grid)
        self.results: list[dict[str, Any]] = []
        manager = self._manager()
        if manager is None:
            return
        installed = set(getattr(getattr(manager, "state", None), "plugins", {}) or {})
        seen: set[str] = set()
        for row in manager.search(self.query.text().strip()):
            plugin_id = str(row.get("id") or "")
            if not plugin_id or plugin_id in installed or plugin_id in seen:
                continue
            seen.add(plugin_id)
            self.results.append(row)
        if not self.results:
            self.results_grid.addWidget(
                _EmptyCard(self.ctx.text("discover.empty", "没有匹配的可安装插件")), 0, 0, 1, 2
            )
        for index, record in enumerate(self.results):
            card = _ResultCard(
                record,
                self.ctx.text("discover.install", "安装"),
                self.ctx.text("discover.permissions", "{count} 项权限"),
                self._install,
            )
            self.results_grid.addWidget(card, index // 2, index % 2)
        self.ctx.log(f"search plugins: {len(self.results)}")
        self.ctx.event("plugin_store.search", {"count": len(self.results)})

    def _refresh_sources(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self.page.set_status(self.ctx.text("status.refreshing", "正在刷新源…"))
        try:
            with self.ctx.timing("plugin_store.source_refresh"):
                sources.refresh_all()
            self.ctx.event("plugin_store.sources_refreshed")
            self.page.set_status(self.ctx.text("status.refresh_done", "源刷新完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)

    def _install(self, record: dict[str, Any]) -> None:
        plugin_id = str(record.get("id") or "")
        permissions = ", ".join(record.get("permissions") or []) or "-"
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
        manager = self._manager()
        if not ok or manager is None:
            return
        try:
            with self.ctx.timing("plugin_store.install"):
                result = manager.install(plugin_id, source_id=str(record.get("source") or ""))
            self.ctx.log(f"installed: {result}")
            self.ctx.event("plugin_store.install", {"id": plugin_id, "version": result.get("version")})
            self.page.set_status(
                self.ctx.text("status.install_done", "已安装 {count} 个插件").format(count=1), "success"
            )
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_INSTALL_FAILED", f"安装失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)
        self.page.schedule_reload()


class _SourcesPanel(QWidget):
    """源：列表 + 添加输入 + 逐行刷新/移除。"""

    def __init__(self, page: StorePage, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.ctx = page.ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.url = CInputText(placeholder=self.ctx.text("sources.placeholder", "Git 仓库地址"))
        self.add_btn = CButton(self.ctx.text("sources.add", "添加"), size="sm")
        self.refresh_all_btn = CButton(
            self.ctx.text("sources.refresh_all", "全部刷新"),
            size="sm",
            severity="secondary",
            variant="outlined",
        )
        add_row.addWidget(self.url, 1)
        add_row.addWidget(self.add_btn)
        add_row.addWidget(self.refresh_all_btn)
        layout.addLayout(add_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }"
        )
        self.rows_host = QWidget()
        self.rows_host.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 6, 0)
        self.rows_layout.setSpacing(8)
        self.scroll.setWidget(self.rows_host)
        layout.addWidget(self.scroll, 1)

        self.add_btn.clicked.connect(self._add)
        self.url.returnPressed.connect(self._add)
        self.refresh_all_btn.clicked.connect(self._refresh_all)

    def _sources(self):
        return getattr(self.page.runtime, "sources", None)

    def refresh(self) -> None:
        _clear_layout(self.rows_layout)
        sources = self._sources()
        records = [
            {"id": record.source_id, "url": record.url, "trust": record.trust}
            for record in sources.list()
        ] if sources is not None else []
        if not records:
            self.rows_layout.addWidget(_EmptyCard(self.ctx.text("sources.empty", "还没有配置插件源")))
            return
        trust_texts = {
            "official": self.ctx.text("sources.official", "官方"),
            "user": self.ctx.text("sources.user", "用户"),
        }
        for record in records:
            self.rows_layout.addWidget(
                _SourceRow(
                    record,
                    trust_texts,
                    self.ctx.text("sources.refresh", "刷新"),
                    self.ctx.text("sources.remove", "移除"),
                    self._refresh_one,
                    self._remove_one,
                )
            )
        self.rows_layout.addStretch(1)

    def _add(self) -> None:
        sources = self._sources()
        url = self.url.text().strip()
        if sources is None or not url:
            return
        try:
            record = sources.add(url, refresh=True)
            self.ctx.event("plugin_store.source_added", {"id": record.source_id})
            self.url.setText("")
            self.page.set_status(
                self.ctx.text("sources.added", "已添加源 {id}").format(id=record.source_id), "success"
            )
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_ADD_FAILED", f"添加源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)

    def _refresh_one(self, source_id: str) -> None:
        sources = self._sources()
        if sources is None:
            return
        try:
            with self.ctx.timing("plugin_store.source_refresh"):
                sources.refresh(source_id)
            self.ctx.event("plugin_store.source_refreshed", {"id": source_id})
            self.page.set_status(self.ctx.text("status.refresh_done", "源刷新完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_REFRESH_FAILED", f"刷新源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)

    def _refresh_all(self) -> None:
        sources = self._sources()
        if sources is None:
            return
        self.page.set_status(self.ctx.text("status.refreshing", "正在刷新源…"))
        try:
            with self.ctx.timing("plugin_store.source_refresh_all"):
                sources.refresh_all()
            self.ctx.event("plugin_store.sources_refreshed")
            self.page.set_status(self.ctx.text("status.refresh_done", "源刷新完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_FAILED", f"刷新源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)

    def _remove_one(self, source_id: str) -> None:
        ok = CConfirmDialog.ask(
            self,
            title=self.ctx.text("sources.remove", "移除"),
            message=self.ctx.text("sources.confirm_remove", "移除源 {id}？已安装插件不受影响。").format(id=source_id),
            severity="warn",
        )
        sources = self._sources()
        if not ok or sources is None:
            return
        try:
            sources.remove(source_id)
            self.ctx.event("plugin_store.source_removed", {"id": source_id})
            self.page.set_status(self.ctx.text("status.action_done", "操作完成"), "success")
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_error("CORE_STORE_SOURCE_REMOVE_FAILED", f"移除源失败: {exc}", str(exc))
            self.page.set_status(self.ctx.text("status.action_failed", "操作失败: {error}").format(error=exc), "error")
        QTimer.singleShot(0, self.page.refresh_all)


class StorePage(QWidget):
    """插件管理工作台。"""

    def __init__(self, ctx: PageContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        from sllkgui.gallery.runtime import current_runtime

        self.runtime = current_runtime()
        self._mode_cards: dict[str, _ModeCard] = {}
        self._build()
        self.switch_mode("installed")
        self.refresh_stats()
        get_theme_manager().subscribe(self._theme_changed)

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
        self.refresh_btn = CButton(
            self.ctx.text("store.refresh", "全部刷新"),
            size="sm",
            severity="secondary",
            variant="outlined",
        )
        hero.addWidget(self.stat_installed)
        hero.addWidget(self.stat_enabled)
        hero.addWidget(self.stat_sources)
        hero.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignBottom)
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
        self.refresh_btn.clicked.connect(self.refresh_all)

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
        manager = getattr(self.runtime, "manager", None)
        rows = list(manager.installed_rows()) if manager is not None else []
        sources = getattr(self.runtime, "sources", None)
        source_count = len(sources.list()) if sources is not None else 0
        self.stat_installed.set_value(len(rows))
        self.stat_enabled.set_value(sum(1 for row in rows if row.get("enabled")))
        self.stat_sources.set_value(source_count)
        self._mode_cards["installed"].set_count(len(rows))
        self._mode_cards["sources"].set_count(source_count)

    def refresh_all(self) -> None:
        self.refresh_stats()
        self.installed_panel.refresh()
        self.discover_panel.search()
        self.sources_panel.refresh()

    def schedule_reload(self) -> None:
        window = self.ctx.parent_window()
        if window is not None and hasattr(window, "reload_plugins"):
            QTimer.singleShot(120, window.reload_plugins)

    def _theme_changed(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.update()


__all__ = ["PageContext", "StorePage", "build_plugin_store_page"]
