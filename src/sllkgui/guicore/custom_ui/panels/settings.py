"""设置界面基础组件：分组卡片、设置行、只读信息行、编辑操作栏。

这些组件只负责版式与状态（已修改 / 错误 / 保存中），不持有配置值；具体
取值与持久化由 ``SettingsSession`` 承担。因此基座页面与插件页面可以完全
复用同一套视觉，不会出现两套「设置行」各自漂移。

主题切换后由页面调用 ``update_style()`` 统一下发颜色；卡片底色用自绘，
避免每行都挂一份样式表造成主题切换卡顿。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, Language, get_design_tokens

from ...styles import card_stroke_color, card_surface_color, qss_color
from ..button.button import CButton


class _StatusDot(QWidget):
    """状态圆点：颜色由状态决定（脏值 / 错误 / 成功）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._color = QColor(get_design_tokens().colors.state_warning)

    def set_color(self, color: str | QColor) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(0, 0, 8, 8))
        painter.end()


class CSettingRow(QWidget):
    """一行设置：标题 + 说明 + 右侧控件 + 已修改标记 / 恢复默认。"""

    resetRequested = Signal(str)

    def __init__(
        self,
        key: str,
        title: str,
        hint: str = "",
        control: QWidget | None = None,
        *,
        badge: str = "",
        resettable: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._key = str(key)
        self._modified = False
        self._resettable = bool(resettable)
        self._reset_available = False
        self._badge_text = badge
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 11, 0, 11)
        layout.setSpacing(20)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(7)
        self._dot = _StatusDot(self)
        self._dot.set_color(get_design_tokens().colors.state_warning)
        self._dot.hide()
        title_row.addWidget(self._dot, 0, Qt.AlignVCenter)
        self._title = QLabel(title, self)
        self._title.setObjectName("CSettingRow_Title")
        title_row.addWidget(self._title, 0, Qt.AlignVCenter)
        self._badge = QLabel(badge, self)
        self._badge.setObjectName("CSettingRow_Badge")
        self._badge.hide()
        title_row.addWidget(self._badge, 0, Qt.AlignVCenter)
        title_row.addStretch(1)
        left.addLayout(title_row)

        self._hint = QLabel(hint, self)
        self._hint.setObjectName("CSettingRow_Hint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(bool(hint))
        left.addWidget(self._hint)

        self._error = QLabel("", self)
        self._error.setObjectName("CSettingRow_Error")
        self._error.setWordWrap(True)
        self._error.hide()
        left.addWidget(self._error)

        layout.addLayout(left, 1)

        self._controls = QWidget(self)
        controls_layout = QHBoxLayout(self._controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addStretch(1)
        self._controls_layout = controls_layout
        if control is not None:
            controls_layout.addWidget(control, 0, Qt.AlignVCenter)

        self._reset = CButton(
            "",
            icon="icon_restore",
            variant="text",
            size="sm",
            fixed_width=28,
            icon_size=14,
            parent=self._controls,
        )
        self._reset.setToolTip(Language.resolve_key("language.UI.ui_SettingsResetItem", "恢复默认"))
        self._reset.clicked.connect(lambda: self.resetRequested.emit(self._key))
        # 恢复默认始终占位：可用时高亮，不可用时置灰，避免鼠标移动导致显隐/位移
        self._reset.setVisible(self._resettable)
        self._reset.setEnabled(False)
        controls_layout.addWidget(self._reset, 0, Qt.AlignVCenter)

        layout.addWidget(self._controls, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.update_style()

    # ------------------------------------------------------------------
    def key(self) -> str:
        return self._key

    def add_control(self, widget: QWidget) -> None:
        self._controls_layout.insertWidget(self._controls_layout.count() - 2, widget, 0, Qt.AlignVCenter)

    def set_control(self, widget: QWidget) -> None:
        """替换主控件（保留恢复按钮）。"""
        while self._controls_layout.count() > 2:
            item = self._controls_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                # 先 hide()：可见控件 setParent(None) 后会变成顶层窗口并闪现。
                child.hide()
                child.setParent(None)
                child.deleteLater()
        self._controls_layout.insertWidget(0, widget, 0, Qt.AlignVCenter)

    def set_badge(self, text: str) -> None:
        self._badge_text = str(text)
        self._badge.setText(self._badge_text)
        self._badge.setVisible(bool(self._badge_text))

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_hint(self, text: str) -> None:
        self._hint.setText(text)
        self._hint.setVisible(bool(text))

    def set_modified(self, modified: bool) -> None:
        value = bool(modified)
        if value == self._modified:
            return
        self._modified = value
        self._dot.setVisible(value)

    def set_reset_available(self, available: bool) -> None:
        """控制恢复按钮是否可点；按钮本身始终显示（不可用时置灰）。"""
        self._reset_available = bool(available)
        self._reset.setEnabled(self._resettable and self._reset_available)

    def is_modified(self) -> bool:
        return self._modified

    def set_error(self, message: str | None) -> None:
        text = str(message or "").strip()
        self._error.setText(text)
        self._error.setVisible(bool(text))

    def error(self) -> str:
        return self._error.text()

    # ------------------------------------------------------------------
    def update_style(self) -> None:
        tokens = get_design_tokens()
        colors = tokens.colors
        family = AppSettings.family

        title_font = QFont(family)
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Weight.Normal)
        self._title.setFont(title_font)
        self._title.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")

        hint_font = QFont(family)
        hint_font.setPixelSize(11)
        self._hint.setFont(hint_font)
        self._hint.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")

        error_font = QFont(family)
        error_font.setPixelSize(11)
        self._error.setFont(error_font)
        self._error.setStyleSheet(f"color: {colors.state_danger}; background: transparent;")

        badge_font = QFont(family)
        badge_font.setPixelSize(10)
        self._badge.setFont(badge_font)
        badge_bg = QColor(colors.state_warning)
        badge_bg.setAlpha(28)
        self._badge.setStyleSheet(
            f"color: {colors.state_warning}; background: {qss_color(badge_bg)}; border-radius: 7px; padding: 1px 6px;"
        )
        self._dot.set_color(colors.state_warning)
        self._reset.update()


class CSettingGroup(QWidget):
    """设置分组卡片：标题 + 说明 + 若干行，行间用发丝线分隔。"""

    def __init__(self, title: str = "", hint: str = "", parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(0)

        self._head = QWidget(self)
        head_layout = QVBoxLayout(self._head)
        head_layout.setContentsMargins(2, 0, 2, 6)
        head_layout.setSpacing(3)
        self._title = QLabel(title, self._head)
        self._title.setObjectName("CSettingGroup_Title")
        self._hint = QLabel(hint, self._head)
        self._hint.setObjectName("CSettingGroup_Hint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(bool(hint))
        head_layout.addWidget(self._title)
        head_layout.addWidget(self._hint)
        self._head.setVisible(bool(title or hint))
        layout.addWidget(self._head)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(0)
        layout.addLayout(self._body)
        self._rows: list[QWidget] = []
        self._dividers: list[QFrame] = []
        self.update_style()

    # ------------------------------------------------------------------
    def add_row(self, row: QWidget) -> None:
        if self._rows:
            divider = QFrame(self)
            divider.setFixedHeight(1)
            self._body.addWidget(divider)
            self._dividers.append(divider)
        self._body.addWidget(row)
        self._rows.append(row)
        self.update_style()

    def add_widget(self, widget: QWidget, *, divider: bool = True) -> None:
        if self._rows and divider:
            line = QFrame(self)
            line.setFixedHeight(1)
            self._body.addWidget(line)
            self._dividers.append(line)
        self._body.addWidget(widget)
        self._rows.append(widget)
        self.update_style()

    def body_layout(self) -> QVBoxLayout:
        return self._body

    def rows(self) -> tuple[QWidget, ...]:
        return tuple(self._rows)

    def set_title(self, title: str) -> None:
        self._title.setText(title)
        self._head.setVisible(bool(title or self._hint.text()))

    def set_hint(self, hint: str) -> None:
        self._hint.setText(hint)
        self._hint.setVisible(bool(hint))
        self._head.setVisible(bool(self._title.text() or hint))

    def update_style(self) -> None:
        tokens = get_design_tokens()
        colors = tokens.colors
        title_font = QFont(AppSettings.family)
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(title_font)
        self._title.setStyleSheet(f"color: {colors.text_title}; background: transparent;")

        hint_font = QFont(AppSettings.family)
        hint_font.setPixelSize(11)
        self._hint.setFont(hint_font)
        self._hint.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")

        line_color = QColor(colors.text_primary)
        line_color.setAlpha(22)
        for divider in self._dividers:
            divider.setStyleSheet(f"background: {qss_color(line_color)}; border: none;")
        for row in self._rows:
            if isinstance(row, (CSettingRow, CInfoRow, CActionRow)):
                row.update_style()
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        tokens = get_design_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, tokens.radius.window, tokens.radius.window)
        painter.fillPath(path, card_surface_color())
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(card_stroke_color(), 1))
        painter.drawPath(path)
        painter.end()


class CActionRow(QWidget):
    """动作行：标题 + 说明 + 右侧执行按钮（测试 / 导入 / 同步等）。

    组件只负责外观与点击信号，命令执行与异常隔离由设置页承担；这样同一行
    既能执行界面操作，也能交给插件做后台任务。
    """

    clicked = Signal()

    def __init__(
        self,
        title: str,
        hint: str = "",
        button_text: str = "",
        *,
        parent=None,
    ):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 10, 2, 10)
        layout.setSpacing(20)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(3)
        self._title = QLabel(title, self)
        self._title.setObjectName("CActionRow_Title")
        self._hint = QLabel(hint, self)
        self._hint.setObjectName("CActionRow_Hint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(bool(hint))
        text_box.addWidget(self._title)
        text_box.addWidget(self._hint)
        layout.addLayout(text_box, 1)

        self._button = CButton(
            button_text,
            severity="secondary",
            variant="outlined",
            size="sm",
            parent=self,
        )
        self._button.clicked.connect(lambda *_args: self.clicked.emit())
        layout.addWidget(self._button, 0, Qt.AlignVCenter)
        self.update_style()

    # ------------------------------------------------------------------
    def set_title(self, text: str) -> None:
        self._title.setText(str(text))

    def set_hint(self, text: str) -> None:
        self._hint.setText(str(text))
        self._hint.setVisible(bool(text))

    def set_button_text(self, text: str) -> None:
        self._button.setText(str(text))

    def button(self) -> CButton:
        return self._button

    def update_style(self) -> None:
        colors = get_design_tokens().colors
        title_font = QFont(AppSettings.family)
        title_font.setPixelSize(13)
        self._title.setFont(title_font)
        self._title.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")

        hint_font = QFont(AppSettings.family)
        hint_font.setPixelSize(11)
        self._hint.setFont(hint_font)
        self._hint.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self._button.update()


class CInfoRow(QWidget):
    """只读信息行：键 + 值 + 可选操作按钮（关于页 / 当前窗口信息）。"""

    def __init__(self, key: str, value: str = "", *, mono: bool = True, parent=None):
        super().__init__(parent)
        self._mono = mono
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 8, 2, 8)
        layout.setSpacing(16)

        self._key = QLabel(key, self)
        self._key.setFixedWidth(88)
        self._value = QLabel(value, self)
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._actions = QHBoxLayout()
        self._actions.setContentsMargins(0, 0, 0, 0)
        self._actions.setSpacing(6)

        layout.addWidget(self._key, 0, Qt.AlignTop)
        layout.addWidget(self._value, 1)
        layout.addLayout(self._actions)
        self.update_style()

    def set_value(self, text: str) -> None:
        self._value.setText(str(text))
        self._value.setToolTip(str(text))

    def value(self) -> str:
        return self._value.text()

    def set_key(self, text: str) -> None:
        self._key.setText(str(text))

    def add_action(self, button: QWidget) -> None:
        self._actions.addWidget(button, 0, Qt.AlignVCenter)

    def update_style(self) -> None:
        colors = get_design_tokens().colors
        key_font = QFont(AppSettings.family)
        key_font.setPixelSize(11)
        self._key.setFont(key_font)
        self._key.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")

        value_font = QFont(AppSettings.family)
        value_font.setPixelSize(11)
        if self._mono:
            value_font.setFamilies(["Cascadia Mono", "Consolas", AppSettings.family])
        self._value.setFont(value_font)
        self._value.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")


class CEditActionBar(QWidget):
    """编辑操作栏：脏值计数 / 错误 / 保存中 + 放弃 / 保存。"""

    saveRequested = Signal()
    discardRequested = Signal()
    resetRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)
        self._saving = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(8)

        self._dot = _StatusDot(self)
        layout.addWidget(self._dot, 0, Qt.AlignVCenter)

        self._status = QLabel("", self)
        self._status.setObjectName("CEditActionBar_Status")
        layout.addWidget(self._status, 1)

        self._reset = CButton(
            Language.resolve_key("language.UI.ui_SettingsResetPage", "恢复本页默认"),
            severity="secondary",
            variant="text",
            size="sm",
        )
        self._reset.clicked.connect(self.resetRequested.emit)
        layout.addWidget(self._reset, 0, Qt.AlignVCenter)

        self._discard = CButton(
            Language.resolve_key("language.UI.ui_SettingsDiscard", "放弃"),
            severity="secondary",
            variant="text",
            size="sm",
        )
        self._discard.clicked.connect(self.discardRequested.emit)
        layout.addWidget(self._discard, 0, Qt.AlignVCenter)

        self._save = CButton(
            Language.resolve_key("language.UI.ui_Save", "保存"),
            severity="primary",
            variant="solid",
            size="sm",
        )
        self._save.clicked.connect(self.saveRequested.emit)
        layout.addWidget(self._save, 0, Qt.AlignVCenter)

        self.update_style()

    # ------------------------------------------------------------------
    def set_dirty_count(self, count: int) -> None:
        self._dot.set_color(get_design_tokens().colors.state_warning)
        self._status.setStyleSheet(f"color: {get_design_tokens().colors.text_muted}; background: transparent;")
        self._status.setText(
            Language.resolve_key("language.UI.ui_SettingsUnsaved", "{count} 项未保存的更改").format(count=int(count))
        )
        self._save.setEnabled(not self._saving)
        self._discard.setEnabled(not self._saving)
        self._reset.setEnabled(not self._saving)

    def set_error(self, message: str) -> None:
        self._dot.set_color(get_design_tokens().colors.state_danger)
        self._status.setStyleSheet(f"color: {get_design_tokens().colors.state_danger}; background: transparent;")
        self._status.setText(str(message))
        self._save.setEnabled(not self._saving)
        self._discard.setEnabled(True)

    def set_reset_visible(self, visible: bool) -> None:
        self._reset.setVisible(bool(visible))

    def set_saving(self, saving: bool) -> None:
        self._saving = bool(saving)
        self._save.setEnabled(not self._saving)
        self._discard.setEnabled(not self._saving)
        self._reset.setEnabled(not self._saving)
        if self._saving:
            self._dot.set_color(get_design_tokens().colors.accent)
            self._status.setStyleSheet(f"color: {get_design_tokens().colors.text_muted}; background: transparent;")
            self._status.setText(Language.resolve_key("language.UI.ui_SettingsSaving", "正在保存…"))
            self._save.setText(Language.resolve_key("language.UI.ui_SettingsSaving", "正在保存…"))
        else:
            self._save.setText(Language.resolve_key("language.UI.ui_Save", "保存"))

    def status_text(self) -> str:
        return self._status.text()

    def show_saved(self) -> None:
        self._dot.set_color(get_design_tokens().colors.state_success)
        self._status.setStyleSheet(f"color: {get_design_tokens().colors.text_muted}; background: transparent;")
        self._status.setText(Language.resolve_key("language.UI.ui_SettingsSaved", "设置已保存"))

    def reset_texts(self) -> None:
        self._reset.setText(Language.resolve_key("language.UI.ui_SettingsResetPage", "恢复本页默认"))
        self._discard.setText(Language.resolve_key("language.UI.ui_SettingsDiscard", "放弃"))
        self._save.setText(
            Language.resolve_key("language.UI.ui_SettingsSaving", "正在保存…")
            if self._saving
            else Language.resolve_key("language.UI.ui_Save", "保存")
        )

    def update_style(self) -> None:
        colors = get_design_tokens().colors
        font = QFont(AppSettings.family)
        font.setPixelSize(12)
        self._status.setFont(font)
        if not self._status.text():
            self._status.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self._dot.set_color(colors.state_warning if not self._saving else colors.accent)
        self._save.update()
        self._discard.update()
        self._reset.update()
        self.update()

    def paintEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        colors = get_design_tokens().colors
        painter = QPainter(self)
        line = QColor(colors.text_primary)
        line.setAlpha(26)
        painter.setPen(QPen(line, 1))
        painter.drawLine(0, 0, self.width(), 0)
        painter.end()


__all__ = ["CActionRow", "CEditActionBar", "CInfoRow", "CSettingGroup", "CSettingRow"]
