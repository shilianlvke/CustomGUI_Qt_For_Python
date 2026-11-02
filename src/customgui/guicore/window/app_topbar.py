"""Sakai 风格应用顶栏。

左侧 logo / 菜单开关 / 标题，中部搜索框，右侧操作按钮、通知与用户头像。
图标与文字颜色在绘制或刷新时读取设计令牌，切换主题后重绘即生效。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from customgui.appcore import AppSettings, ColorPalette, PathFactory, get_design_tokens, get_theme_manager

from ..custom_ui.button.button import CButton
from ..custom_ui.display.avatar import CAvatar
from ..custom_ui.display.badge import CBadge
from ..custom_ui.icon_utils import render_icon
from ..custom_ui.line_edit.input_text import CInputText
from ..custom_ui.menu.menu import CMenu


class _ElidingLabel(QLabel):
    """顶栏标题/文字 logo：按可用宽度右侧省略，避免把搜索框挤出顶栏。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = str(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        QLabel.setText(self, self._full_text)
        self.setToolTip(self._full_text)

    def setText(self, text: str) -> None:  # noqa: N802 - 覆写 Qt 命名
        self._full_text = str(text)
        self._refresh()
        self.setToolTip(self._full_text)

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.ElideRight, max(0, self.width())
        )
        QLabel.setText(self, elided)


class _IconButton(QPushButton):
    """顶栏用的纯图标按钮（悬停淡底 + 实时着色）。"""

    def __init__(self, icon: str, tooltip: str = "", size: int = 32, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._button_size = size
        self._hover = False
        self._pressed = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)

    def sizeHint(self) -> QSize:  # noqa: N802 - 覆写 Qt 命名
        return QSize(self._button_size, self._button_size)

    def set_icon(self, icon: str) -> None:
        self._icon = icon
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        if self._pressed:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors.surface_interactive_pressed))
            painter.drawRoundedRect(rect, 6, 6)
        elif self._hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors.surface_interactive_hover))
            painter.drawRoundedRect(rect, 6, 6)

        color = QColor(colors.text_active if (self._hover or self._pressed) else colors.text_primary)
        pixmap = render_icon(self._icon, color, 18, self.devicePixelRatioF())
        if pixmap is not None:
            painter.drawPixmap(
                int(rect.center().x() - pixmap.deviceIndependentSize().width() / 2),
                int(rect.center().y() - pixmap.deviceIndependentSize().height() / 2),
                pixmap,
            )
        painter.end()

    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)


class _UserButton(QWidget):
    """圆形用户头像按钮：点击发出 ``clicked``。"""

    clicked = Signal()

    def __init__(self, name: str = "", size: int = 34, parent=None):
        super().__init__(parent)
        self._user_name = ""
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.avatar = CAvatar(label="", size="sm", parent=self)
        self.avatar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.set_user(name)

    def set_user(self, name: str) -> None:
        self._user_name = str(name or "")
        initial = self._user_name.strip()[:1].upper() or "?"
        self.avatar.set_label(initial)
        self.setToolTip(self._user_name)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self._hover:
            painter.fillRect(rect, QColor(colors.surface_interactive_hover))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(colors.border_context), 1))
            painter.drawEllipse(rect)
        painter.end()

    def resizeEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        side = self.avatar.width()
        self.avatar.move((self.width() - side) // 2, (self.height() - side) // 2)
        super().resizeEvent(event)

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
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CAppTopbar(QWidget):
    """Sakai 风格应用顶栏。

    高度跟随 ``AppSettings.right_title_bar_height``；logo 支持 SVG 路径 / 文字，
    搜索文本变化、通知点击、用户菜单请求与自定义操作均由信号回传。
    """

    menuToggled = Signal()
    searchChanged = Signal(str)
    notificationsClicked = Signal()
    userMenuRequested = Signal()
    actionTriggered = Signal(str)

    #: 顶栏高度（配置不可用时兜底）
    FALLBACK_HEIGHT = 40
    #: logo 显示区域最大边长
    LOGO_LIMIT = 28

    def __init__(self, parent=None, title: str = "", logo=None):
        super().__init__(parent)
        self.setObjectName("CAppTopbar_Widget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        try:
            height = int(AppSettings.right_title_bar_height)
        except Exception:
            height = self.FALLBACK_HEIGHT
        self.setFixedHeight(max(36, height))

        self._title = title
        self._logo_source = logo if logo is not None else self._default_logo()
        self._user_name = ""
        self.action_buttons: dict[str, CButton] = {}
        self._unread_count = 0

        self._setup_ui()
        self.set_logo(self._logo_source)
        self.set_title(title)
        self._build_user_menu()
        self.update_style()
        get_theme_manager().subscribe(self.update_style)

    @staticmethod
    def _default_logo() -> str | None:
        """默认 logo 取配置中的 ``logo_title``（解析为 SVG 图片路径）。"""
        try:
            path = PathFactory.set_svg_image(AppSettings.logo_title)
        except Exception:
            return None
        resolved = Path(path)
        if resolved.is_file() and resolved.name != "icon_pic_not_found.svg":
            return str(resolved)
        return None

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        self.logo_svg = QSvgWidget(self)
        self.logo_svg.setFixedSize(self.LOGO_LIMIT, self.LOGO_LIMIT)
        layout.addWidget(self.logo_svg, 0, Qt.AlignVCenter)

        self.logo_label = _ElidingLabel(parent=self)
        self.logo_label.setFont(self._font(16, QFont.Weight.Bold))
        layout.addWidget(self.logo_label, 0, Qt.AlignVCenter)

        self.menu_button = _IconButton("icon_menu", "菜单", parent=self)
        self.menu_button.clicked.connect(self.menuToggled.emit)
        layout.addWidget(self.menu_button, 0, Qt.AlignVCenter)

        self.title_label = _ElidingLabel(parent=self)
        self.title_label.setFont(self._font(15, QFont.Weight.DemiBold))
        layout.addWidget(self.title_label, 1, Qt.AlignVCenter)

        layout.addStretch(1)

        self.search_box = CInputText(placeholder="搜索...", icon="icon_search", size="sm", parent=self)
        self.search_box.setMinimumWidth(180)
        self.search_box.setMaximumWidth(420)
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_box.textChanged.connect(self.searchChanged.emit)
        layout.addWidget(self.search_box, 2, Qt.AlignVCenter)

        layout.addStretch(1)

        self.actions_container = QWidget(self)
        self.actions_layout = QHBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(4)
        layout.addWidget(self.actions_container, 0, Qt.AlignVCenter)

        self.notification_button = _IconButton("icon_bell", "通知", parent=self)
        self.notification_button.clicked.connect(self.notificationsClicked.emit)
        layout.addWidget(self.notification_button, 0, Qt.AlignVCenter)

        self.notification_badge = CBadge.attach(self.notification_button, "", severity="danger", size="sm")
        self.notification_badge.hide()

        self.user_button = _UserButton(parent=self)
        self.user_button.clicked.connect(self._on_user_clicked)
        layout.addWidget(self.user_button, 0, Qt.AlignVCenter)

    @staticmethod
    def _font(pixel_size: int, weight: QFont.Weight) -> QFont:
        font = QFont(AppSettings.family)
        font.setPixelSize(pixel_size)
        font.setWeight(weight)
        return font

    def _build_user_menu(self) -> None:
        self._user_menu = CMenu(parent=self, width=180)
        self._populate_user_menu(None)

    def _populate_user_menu(self, items) -> None:
        self._user_menu.clear()
        if items is None:
            items = [
                {"label": "个人资料", "key": "profile"},
                {"label": "账户设置", "key": "settings"},
                {"label": "退出登录", "key": "logout"},
            ]
        for entry in items:
            if isinstance(entry, dict):
                if entry.get("separator"):
                    self._user_menu.addSeparator()
                    continue
                label = str(entry.get("label", ""))
                icon = entry.get("icon")
                command = entry.get("command")
            else:
                label = str(entry)
                icon = None
                command = None
            action = QAction(label, self._user_menu)
            if icon is not None:
                action.setIcon(QIcon(render_icon(icon, QColor(ColorPalette.custom_icon_color), 16)))
            if callable(command):
                action.triggered.connect(command)
            self._user_menu.addAction(action)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def set_title(self, title: str) -> None:
        """设置顶栏标题（空字符串隐藏标题）。"""
        self._title = str(title or "")
        self.title_label.setText(self._title)
        self.title_label.setVisible(bool(self._title))

    def set_logo(self, logo) -> None:
        """设置 logo：SVG 文件 / 资源路径按图形显示，其余字符串按文字显示。"""
        self._logo_source = logo
        if logo is None:
            self.logo_svg.hide()
            self.logo_label.hide()
            return

        text = str(logo)
        candidate = Path(text)
        if candidate.is_file():
            self._show_svg(str(candidate))
            return
        if text.lower().endswith(".svg"):
            self._show_svg(PathFactory.resolve_svg(text))
            return
        self.logo_svg.hide()
        self.logo_label.setText(text)
        self.logo_label.show()

    def _show_svg(self, source: str) -> None:
        self.logo_svg.load(source)
        renderer = self.logo_svg.renderer()
        natural = renderer.defaultSize() if renderer is not None else QSize()
        if natural.isValid() and natural.width() > 0 and natural.height() > 0:
            size = natural.scaled(self.LOGO_LIMIT, self.LOGO_LIMIT, Qt.KeepAspectRatio)
        else:
            size = QSize(self.LOGO_LIMIT, self.LOGO_LIMIT)
        self.logo_svg.setFixedSize(size)
        self.logo_svg.show()
        self.logo_label.hide()

    def set_unread_count(self, count: int) -> None:
        """更新未读通知数；0 时隐藏徽标，超过 99 显示 ``99+``。"""
        self._unread_count = max(0, int(count))
        if self._unread_count <= 0:
            self.notification_badge.set_text("")
            self.notification_badge.hide()
            return
        text = str(self._unread_count) if self._unread_count < 100 else "99+"
        self.notification_badge.set_text(text)
        self.notification_badge.show()
        self.notification_badge.raise_()

    def unread_count(self) -> int:
        return self._unread_count

    def set_user(self, user=None, avatar=None, items=None) -> None:
        """设置用户头像与菜单项。

        ``user`` 可以是名字字符串，也可以是 ``{"name": ..., "avatar": ...,
        "items": [...]}`` 形式的字典；``items`` 显式传入时覆盖字典中的菜单项。
        """
        name = ""
        image = avatar
        if isinstance(user, dict):
            name = str(user.get("name") or user.get("label") or "")
            if image is None:
                image = user.get("avatar") or user.get("image")
            if items is None:
                items = user.get("items")
        elif user is not None:
            name = str(user)

        self._user_name = name
        self.user_button.set_user(name)
        self.user_button.avatar.set_image(image)
        self._populate_user_menu(items)

    def user_name(self) -> str:
        return self._user_name

    def add_action_button(self, text: str, key: str | None = None, icon=None, tooltip: str | None = None) -> CButton:
        """在通知按钮左侧追加一个操作按钮，点击发出 ``actionTriggered``。"""
        button = CButton(text=text, icon=icon, severity="secondary", variant="text", size="sm", parent=self)
        if tooltip:
            button.setToolTip(tooltip)
        identity = key if key is not None else text
        button.clicked.connect(lambda _checked=False, value=identity: self.actionTriggered.emit(value))
        self.actions_layout.addWidget(button)
        self.action_buttons[identity] = button
        return button

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _on_user_clicked(self) -> None:
        self.userMenuRequested.emit()
        if not self._user_menu.actions():
            return
        position = self.user_button.mapToGlobal(QPoint(0, self.user_button.height() + 4))
        self._user_menu.popup(position)

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def update_style(self) -> None:
        """主题切换后刷新标签颜色并重绘图标按钮。"""
        colors = get_design_tokens().colors
        self.title_label.setStyleSheet(f"color: {colors.text_active}; background: transparent;")
        self.logo_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        for button in (self.menu_button, self.notification_button):
            button.update()
        self.user_button.update()
        self.search_box.update()
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(colors.surface_panel))
        painter.setPen(QPen(QColor(colors.surface_interactive_pressed), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()


__all__ = ["CAppTopbar"]
