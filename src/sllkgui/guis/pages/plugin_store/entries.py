"""列表行与检查器内容：插件/来源的紧凑行、信息网格、权限与空态。

条目只负责展示与最小交互（选中、启停、安装），所有业务动作都通过信号
回到 ``StorePage``；这样列表与检查器都不直接持有运行时，测试可以只构造
条目本身。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sllkgui.guicore import (
    CButton,
    CChip,
    CElidedLabel,
    CIconTile,
    CText,
    CToggleSwitch,
)
from sllkgui.guicore.fonts import MONO_FAMILIES

from .context import PageContext
from .theme import (
    ROW_BAR_OBJECT,
    ROW_OBJECT,
    UPDATE_DOT_OBJECT,
    repolish,
    text_role,
)

_MONO_FONT = tuple(MONO_FAMILIES)


# ----------------------------------------------------------------------
# 基础文本与标签
# ----------------------------------------------------------------------
def label(
    role: str,
    text: str,
    *,
    pixel_size: int = 10,
    weight: str = "regular",
    mono: bool = False,
    wrap: bool = False,
) -> CText:
    """按角色构造可随主题变色的文本。"""
    node = CText(text, pixel_size=pixel_size, weight=weight, mono=mono, wrap=wrap)
    return text_role(node, role)


def elided(role: str, text: str, *, pixel_size: int, weight: str = "regular") -> CElidedLabel:
    """单行省略文本；行内标题/简介用它，避免长 ID 把开关挤出去。

    行内标签必须关闭文字选择：``QLabel`` 一旦接受鼠标选择就会吞掉点击，
    导致整行无法被选中（检查器里的值仍保留可选择）。
    """
    node = CElidedLabel(text)
    node.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    font = QFont(node.font())
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Medium if weight == "medium" else QFont.Weight.Normal)
    node.setFont(font)
    return text_role(node, role)


def chip(text: str, *, accent: bool = False) -> CChip:
    """紧凑标签片：20px 高、10px 字，和基座 CChip 的默认尺寸拉开一档。"""
    return CChip(text, height=20, font_pixel_size=10, tone="accent" if accent else "neutral")


def version_chip(text: str) -> CChip:
    node = chip(text, accent=True)
    font = QFont(node.font())
    font.setFamilies(list(_MONO_FONT))
    node.setFont(font)
    node.updateGeometry()
    return node


def update_dot(version: str) -> QFrame:
    dot = QFrame()
    dot.setObjectName(UPDATE_DOT_OBJECT)
    dot.setFixedSize(6, 6)
    dot.setToolTip(version)
    return dot


def section_title(text: str) -> QWidget:
    """分区标题：强调色短竖线 + 标题 + 延伸到右端的发丝线。"""
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)

    rule = QFrame()
    rule.setObjectName("CSectionTitle_Rule")
    rule.setFixedSize(3, 12)
    rule.setStyleSheet("#CSectionTitle_Rule { border-radius: 1px; }")

    node = label("title", text, pixel_size=12, weight="semibold")
    node.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    divider = QFrame()
    divider.setObjectName("CSectionTitle_Divider")
    divider.setFixedHeight(1)
    divider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    row.addWidget(rule, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(node, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(divider, 1, Qt.AlignmentFlag.AlignVCenter)
    return host


# ----------------------------------------------------------------------
# 列表行
# ----------------------------------------------------------------------
class StoreRow(QFrame):
    """插件/来源行：点击选中，右侧承载启停开关或「安装」按钮。"""

    clicked = Signal(dict)
    toggled = Signal(str, bool)
    install_requested = Signal(dict)

    def __init__(self, record: dict[str, Any], mode: str, ctx: PageContext, parent=None) -> None:
        super().__init__(parent)
        self.record = dict(record)
        self.mode = mode
        self.ctx = ctx
        self._selected = False
        self._hover = False
        self.setObjectName(ROW_OBJECT)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 8, 10, 8)
        row.setSpacing(10)

        self._bar = QFrame()
        self._bar.setObjectName(ROW_BAR_OBJECT)
        self._bar.setFixedWidth(2)
        self._bar.setVisible(False)
        row.addWidget(self._bar)

        is_source = self.mode == "sources"
        icon_name = "icon_database" if is_source else (str(self.record.get("icon_name") or "icon_store"))
        icon_file = "" if is_source else str(self.record.get("icon") or "")
        row.addWidget(CIconTile(icon_name, 32, self, image=icon_file))

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)

        title_line = QHBoxLayout()
        title_line.setContentsMargins(0, 0, 0, 0)
        title_line.setSpacing(6)

        title_text = str(self.record.get("name") or self.record.get("id") or "")
        subtitle_text = str(self.record.get("summary") or self.record.get("url") or "")
        title = elided("body", title_text, pixel_size=13, weight="medium")
        # 标题按内容取宽、上限 180px；后面的版本/状态片紧跟标题，剩余空间才留白。
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        title.setMaximumWidth(180)
        title_line.addWidget(title, 0)

        if is_source:
            trust = str(self.record.get("trust") or "user")
            title_line.addWidget(
                chip(
                    self.ctx.text("sources.official", "官方")
                    if trust == "official"
                    else self.ctx.text("sources.user", "用户"),
                    accent=trust == "official",
                )
            )
        else:
            version = str(self.record.get("version") or "?")
            title_line.addWidget(version_chip(f"v{version}"))
            if self.mode == "discover":
                installed = bool(self.record.get("installed"))
                title_line.addWidget(
                    chip(
                        self.ctx.text("detail.installed", "已安装")
                        if installed
                        else self.ctx.text("detail.not_installed", "未安装"),
                        accent=installed,
                    )
                )
            if self.record.get("update_available"):
                version_text = str(self.record.get("available_version") or "")
                dot = update_dot(f"v{version_text}")
                dot.setToolTip(f"{self.ctx.text('detail.available', '可用版本')} v{version_text}")
                title_line.addWidget(dot)

        title_line.addStretch(1)
        column.addLayout(title_line)
        column.addWidget(elided("muted", subtitle_text, pixel_size=10))
        row.addLayout(column, 1)

        if is_source:
            enabled = bool(self.record.get("enabled", True))
            self._add_switch(row, enabled)
        elif bool(self.record.get("installed")):
            self._add_switch(row, bool(self.record.get("enabled", True)))
        else:
            install = CButton(
                self.ctx.text("discover.install", "安装"),
                severity="secondary",
                variant="text",
                size="sm",
                fixed_width=56,
            )
            install.clicked.connect(lambda: self.install_requested.emit(dict(self.record)))
            row.addWidget(install, 0, Qt.AlignmentFlag.AlignVCenter)

    def _add_switch(self, row: QHBoxLayout, enabled: bool) -> None:
        switch = CToggleSwitch("", checked=enabled)
        switch.setToolTip(
            self.ctx.text("installed.enabled", "已启用") if enabled else self.ctx.text("installed.disabled", "已停用")
        )
        switch.setAccessibleName(
            self.ctx.text("installed.enable", "启用") if not enabled else self.ctx.text("installed.disable", "停用")
        )
        switch.toggled.connect(lambda checked: self.toggled.emit(str(self.record.get("id") or ""), checked))
        row.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if selected == self._selected:
            return
        self._selected = selected
        self._bar.setVisible(selected)
        self.setProperty("selected", "true" if selected else "false")
        repolish(self)

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def enterEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if self.isEnabled():
            self._hover = True
            self.setProperty("hover", "true")
            repolish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        self._hover = False
        self.setProperty("hover", "false")
        repolish(self)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - 覆写 Qt 命名
        if (
            self.isEnabled()
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(dict(self.record))
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ----------------------------------------------------------------------
# 检查器内容
# ----------------------------------------------------------------------
def hero(record: dict[str, Any], chips: list[QWidget], *, icon_name: str, icon_file: str = "") -> QWidget:
    """检查器头部：图标 + 名称 + ID + 状态片。"""
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(14)
    row.addWidget(CIconTile(icon_name, 48, host, image=icon_file), 0, Qt.AlignmentFlag.AlignTop)

    column = QVBoxLayout()
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(2)
    name = label(
        "title", str(record.get("name") or record.get("id") or ""), pixel_size=17, weight="semibold", wrap=True
    )
    column.addWidget(name)
    column.addWidget(label("muted", str(record.get("id") or ""), pixel_size=10, mono=True))

    chip_row = QHBoxLayout()
    chip_row.setContentsMargins(0, 0, 0, 0)
    chip_row.setSpacing(6)
    for item in chips:
        chip_row.addWidget(item)
    chip_row.addStretch(1)
    column.addLayout(chip_row)
    row.addLayout(column, 1)
    return host


def meta_grid(items: list[tuple[str, str, bool]]) -> QWidget:
    """基础信息网格：左列键名固定 72px，右列值可换行、可选中。"""
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    for index, (key, value, mono) in enumerate(items):
        key_label = label("muted", key, pixel_size=10)
        key_label.setFixedWidth(72)
        value_label = label("body", value or "—", pixel_size=10 if mono else 11, mono=mono, wrap=True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(key_label, index, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value_label, index, 1)
    grid.setColumnStretch(1, 1)
    return host


def permission_block(permissions: list[str], ctx: PageContext) -> QWidget:
    """权限区：无权限时给一句人话，而不是留空。"""
    host = QWidget()
    column = QVBoxLayout(host)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(8)
    column.addWidget(section_title(ctx.text("detail.permissions", "权限")))
    if not permissions:
        column.addWidget(label("muted", ctx.text("inspector.no_permissions", "没有声明额外权限"), pixel_size=10))
        return host

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)
    for index, permission in enumerate(permissions):
        grid.addWidget(chip(str(permission)), index // 3, index % 3)
    grid.setColumnStretch(3, 1)
    column.addLayout(grid)
    return host


def empty_state(
    icon_name: str,
    title: str,
    hint: str,
    action_text: str = "",
    on_action=None,
) -> QWidget:
    """检查器空态：居中图标 + 标题 + 一句下一步。"""
    host = QWidget()
    column = QVBoxLayout(host)
    column.setContentsMargins(16, 32, 16, 24)
    column.setSpacing(10)
    column.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    column.addStretch(1)
    column.addWidget(CIconTile(icon_name, 58, host), 0, Qt.AlignmentFlag.AlignHCenter)
    column.addWidget(label("title", title, pixel_size=14, weight="semibold"), 0, Qt.AlignmentFlag.AlignHCenter)
    hint_label = label("muted", hint, pixel_size=10, wrap=True)
    hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint_label.setMaximumWidth(330)
    column.addWidget(hint_label, 0, Qt.AlignmentFlag.AlignHCenter)
    if action_text:
        button = CButton(action_text, severity="primary", variant="solid", size="sm")
        button.setObjectName("CPluginEmptyAction")
        if on_action is not None:
            button.clicked.connect(on_action)
        column.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
    column.addStretch(2)
    return host


__all__ = [
    "StoreRow",
    "chip",
    "elided",
    "empty_state",
    "hero",
    "label",
    "meta_grid",
    "permission_block",
    "section_title",
    "update_dot",
    "version_chip",
]
