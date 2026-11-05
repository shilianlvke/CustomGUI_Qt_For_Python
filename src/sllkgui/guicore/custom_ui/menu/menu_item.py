"""菜单族共享数据模型。

所有菜单组件（菜单栏、分层菜单、MegaMenu、面板菜单、右键菜单、标签菜单）
都使用同一个 :class:`MenuItem` 描述数据，避免每套组件各自定义一套键名。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtGui import QIcon


@dataclass
class MenuItem:
    """一个菜单项。

    Attributes:
        label: 显示文本。
        icon: 图标名（``icon_xxx``）、绝对路径或 ``QIcon``。
        command: 点击后的无参回调；菜单组件先发信号再调用它。
        items: 子菜单项。非空时渲染子菜单箭头。
        disabled: 禁用项不响应点击，文字使用弱化色。
        separator: 为真时该行渲染为分隔线，其余字段忽略。
        key: 业务标识，随 ``itemClicked`` 一起回传。
    """

    label: str = ""
    icon: str | QIcon | None = None
    command: Callable[[], None] | None = None
    items: list[MenuItem] = field(default_factory=list)
    disabled: bool = False
    separator: bool = False
    key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.label, str):
            self.label = str(self.label)
        self.items = [as_menu_item(entry) for entry in self.items]

    @property
    def has_children(self) -> bool:
        """是否包含子菜单项。"""
        return bool(self.items)


_ALLOWED_KEYS = ("label", "icon", "command", "items", "disabled", "separator", "key")


def as_menu_item(value: MenuItem | dict[str, Any] | str | None) -> MenuItem:
    """把字符串 / 字典 / :class:`MenuItem` 归一为 :class:`MenuItem`。

    字典允许使用 ``children`` 作为 ``items`` 的别名，方便从 PrimeVue 风格的
    配置直接迁移。
    """
    if isinstance(value, MenuItem):
        return value
    if value is None:
        return MenuItem()
    if isinstance(value, str):
        return MenuItem(label=value)
    if isinstance(value, dict):
        data = dict(value)
        if "children" in data and "items" not in data:
            data["items"] = data.pop("children")
        unknown = set(data) - set(_ALLOWED_KEYS)
        if unknown:
            raise TypeError(f"菜单项包含未知字段: {sorted(unknown)}")
        return MenuItem(**data)
    raise TypeError(f"无法转换为 MenuItem: {type(value)!r}")


def normalize_items(values: Iterable[MenuItem | dict[str, Any] | str] | None) -> list[MenuItem]:
    """批量归一菜单项；``None`` 视为空列表。"""
    if not values:
        return []
    return [as_menu_item(value) for value in values]


__all__ = ["MenuItem", "as_menu_item", "normalize_items"]
