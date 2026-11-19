"""基座内置快捷键：与插件共用同一张注册表，优先级更高且锁定。

内置项与插件项走完全相同的注册/派发路径（``guicore.shortcuts``），差别只有：

- ``owner`` 固定为 :data:`BASE_OWNER`，插件用 ``plugin_id``；
- 优先级 :data:`PRIORITY_BASE`，高于任何插件默认值；
- ``locked=True``，插件用 ``conflict="replace"`` 也顶不掉；
- 绑定到宿主窗口，窗口销毁时自动注销，避免重建窗口后残留旧回调。
"""

from __future__ import annotations

from typing import Any

from sllkgui.appcore import Logger
from sllkgui.guicore.shortcuts import (
    PRIORITY_BASE,
    ConflictPolicy,
    ShortcutError,
    shortcut_registry,
)

#: 基座内置快捷键的归属名
BASE_OWNER = "sllkgui.base"

#: 内置绑定表：``(id, 可移植序列, 说明)``。
#: 序列一律用 ``primary``：macOS 自动变 ⌘，Windows/Linux 为 Ctrl。
BUILTIN_BINDINGS: tuple[tuple[str, str, str], ...] = (
    ("base.search", "primary+k", "打开页面快速跳转"),
    ("base.settings", "primary+,", "打开设置窗口"),
)


def install_builtin_shortcuts(window: Any, controller: Any) -> int:
    """装配内置快捷键，返回成功注册的条数。

    幂等：同一进程内重建窗口时先清掉上一份基座绑定，不会出现重复条目。
    """
    registry = shortcut_registry()
    registry.unregister_owner(BASE_OWNER)
    actions = {
        "base.search": getattr(controller, "open_search_palette", None),
        "base.settings": getattr(controller, "open_settings_window", None),
    }
    registered = 0
    for shortcut_id, sequence, description in BUILTIN_BINDINGS:
        action = actions.get(shortcut_id)
        if not callable(action):
            continue
        try:
            registry.register(
                shortcut_id,
                sequence,
                action,
                owner=BASE_OWNER,
                priority=PRIORITY_BASE,
                description=description,
                host=window,
                locked=True,
                allow_in_modal=False,
                policy=ConflictPolicy.REPLACE,
            )
        except ShortcutError as exc:
            # 同序列被其他基座窗口（或已锁定的其他内置项）占用：跳过并告警
            Logger.warning(f"内置快捷键注册失败 {shortcut_id} ({sequence}): {exc.message}")
            continue
        registered += 1
    return registered


def uninstall_builtin_shortcuts() -> int:
    """注销全部内置快捷键（窗口真正关闭时调用）。"""
    return shortcut_registry().unregister_owner(BASE_OWNER)


__all__ = ["BASE_OWNER", "BUILTIN_BINDINGS", "install_builtin_shortcuts", "uninstall_builtin_shortcuts"]
