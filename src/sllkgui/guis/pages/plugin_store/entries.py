"""条目渲染：列表项、元信息网格、权限块与详情页头部。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from sllkgui.guicore import CChip, CElidedLabel, CIconTile, CText, CToggleSwitch

from .context import PageContext


def _chip(text: str, *, accent: bool = False) -> CChip:
    """紧凑标签片：20px 高、10px 字，强调态走 accent 色调。"""
    return CChip(text, height=20, font_pixel_size=10, tone="accent" if accent else "neutral")


def _elided(text: str, pixel_size: int = 10) -> CElidedLabel:
    """单行省略文本；字号沿用条目排版（默认 10px）。"""
    label = CElidedLabel(text)
    font = label.font()
    font.setPixelSize(pixel_size)
    label.setFont(font)
    return label


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
        icon_file = ""
        trust = str(record.get("trust") or "user")
        trust_text = ctx.text("sources.official", "官方") if trust == "official" else ctx.text("sources.user", "用户")
        badges.append((trust_text, trust == "official"))
    elif kind == "discover":
        title = str(record.get("name") or item_id)
        subtitle = str(record.get("summary") or item_id)
        icon = "icon_store"
        icon_file = str(record.get("icon") or "")
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
        icon_file = str(record.get("icon") or "")
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
        top.addWidget(CIconTile(icon, 40, image=icon_file))
        top.addStretch(1)
        if toggle is not None:
            top.addWidget(toggle, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        title_label = CText.with_role("entry", title)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(_elided(subtitle))
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        for text, accent in badges:
            badge_row.addWidget(_chip(text, accent=accent))
        badge_row.addStretch(1)
        layout.addLayout(badge_row)
        root.setMinimumHeight(132)
        return root

    layout = QHBoxLayout(root)
    layout.setContentsMargins(2, 2, 2, 2)
    layout.setSpacing(12)
    layout.addWidget(CIconTile(icon, 38, image=icon_file), 0, Qt.AlignmentFlag.AlignTop)
    column = QVBoxLayout()
    column.setSpacing(4)
    title_row = QHBoxLayout()
    title_row.setSpacing(6)
    title_row.addWidget(CText.with_role("entry", title), 1)
    for text, accent in badges:
        title_row.addWidget(_chip(text, accent=accent))
    column.addLayout(title_row)
    column.addWidget(_elided(subtitle))
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
        key_label = CText.with_role("muted", key)
        key_label.setFixedWidth(72)
        value_label = CText.with_role("value", value or "—", mono=bool(mono))
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
    layout.addWidget(CText.with_role("section", ctx.text("detail.permissions", "权限")))
    if not permissions:
        layout.addWidget(CText.with_role("muted", "—"))
        return box
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)
    for index, permission in enumerate(permissions):
        grid.addWidget(_chip(str(permission)), index // 3, index % 3)
    grid.setColumnStretch(3, 1)
    layout.addLayout(grid)
    return box


def _detail_hero(record: dict[str, Any], ctx: PageContext, *, installed: bool, icon: str) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    layout.addWidget(CIconTile(icon, 54), 0, Qt.AlignmentFlag.AlignTop)

    column = QVBoxLayout()
    column.setSpacing(4)
    title = str(record.get("name") or record.get("id") or "")
    title_label = CText.with_role("title", title)
    title_label.setWordWrap(True)
    column.addWidget(title_label)
    column.addWidget(CText.with_role("muted", str(record.get("id") or ""), mono=True))

    chips = QHBoxLayout()
    chips.setSpacing(6)
    chips.addWidget(_chip(f"v{record.get('version') or '?'}", accent=True))
    if installed:
        chips.addWidget(_chip(ctx.text("detail.installed", "已安装"), accent=True))
        enabled = bool(record.get("enabled", True))
        key = "installed.enabled" if enabled else "installed.disabled"
        fallback = "已启用" if enabled else "已停用"
        chips.addWidget(_chip(ctx.text(key, fallback), accent=enabled))
    else:
        chips.addWidget(_chip(ctx.text("detail.not_installed", "未安装")))
    chips.addStretch(1)
    column.addLayout(chips)
    layout.addLayout(column, 1)
    return box
