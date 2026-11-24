"""桌面宠物快捷键：复用基座统一快捷键注册表。

与内置快捷键共用 ``shortcut_registry``：
- owner 固定为 :data:`PET_OWNER`，关闭时按 owner 一次性注销；
- 使用 PRIORITY_NORMAL 与 ConflictPolicy.ERROR：不覆盖基座锁定项，
  冲突时给出警告提示（既不破坏现有绑定，也能让用户知道原因）；
- 所有序列用 primary，跨平台自动适配 Ctrl / Cmd。
"""

from __future__ import annotations

from typing import Any

from sllkgui.appcore import Logger
from sllkgui.guicore.shortcuts import (
    PRIORITY_NORMAL,
    ConflictPolicy,
    ShortcutError,
    shortcut_registry,
)

PET_OWNER = "sllkgui.pet"

#: (id, 序列, 说明键, 说明兜底)
PET_BINDINGS: tuple[tuple[str, str, str, str], ...] = (
    ("pet.toggle", "primary+alt+p", "language.UI.ui_PetShortcutToggle", "显示/隐藏宠物"),
    ("pet.spin", "primary+alt+r", "language.UI.ui_PetShortcutSpin", "宠物转一圈"),
    ("pet.hop", "primary+alt+j", "language.UI.ui_PetShortcutHop", "宠物跳一下"),
    ("pet.burst", "primary+alt+b", "language.UI.ui_PetShortcutBurst", "宠物粒子特效"),
)


def install_pet_shortcuts(pet: Any) -> tuple[str, ...]:
    """注册宠物快捷键，返回实际注册成功的 id 元组。

    重复调用会先清掉本 owner 的旧条目，保证幂等。
    """
    registry = shortcut_registry()
    registry.unregister_owner(PET_OWNER)
    actions = {
        "pet.toggle": getattr(pet, "toggle", None),
        "pet.spin": getattr(pet, "spin", None),
        "pet.hop": getattr(pet, "hop", None),
        "pet.burst": getattr(pet, "burst", None),
    }
    from sllkgui.appcore import Language

    registered: list[str] = []
    for shortcut_id, sequence, key, fallback in PET_BINDINGS:
        callback = actions.get(shortcut_id)
        if not callable(callback):
            continue
        description = str(Language.resolve_key(key, fallback))
        try:
            registry.register(
                shortcut_id,
                sequence,
                callback,
                owner=PET_OWNER,
                priority=PRIORITY_NORMAL,
                description=description,
                locked=False,
                policy=ConflictPolicy.ERROR,
            )
        except ShortcutError as exc:
            Logger.warning(f"宠物快捷键注册失败 {shortcut_id} ({sequence}): {exc.message}")
            _notify_shortcut_conflict(shortcut_id, sequence, exc)
            continue
        registered.append(shortcut_id)
    return tuple(registered)


def _notify_shortcut_conflict(shortcut_id: str, sequence: str, exc: ShortcutError) -> None:
    """冲突时给出非阻塞提示；提示基础设施不可用时只记日志。"""
    try:
        from sllkgui.appcore.feedback import ToastLevel, ToastRequest
        from sllkgui.guicore.feedback import toast_bus

        toast_bus().show(
            ToastRequest(
                text=f"{sequence} 已被占用，{shortcut_id} 未生效",
                title="宠物快捷键冲突",
                level=ToastLevel.WARN,
                code="PET_SHORTCUT_CONFLICT",
                scope="pet",
                channel="pet.shortcuts",
            )
        )
    except Exception as exc2:  # noqa: BLE001 - 提示失败不影响快捷键注册流程
        Logger.debug(f"宠物快捷键冲突提示失败: {exc2}")


def uninstall_pet_shortcuts() -> int:
    """注销全部宠物快捷键，返回注销条数。"""
    return shortcut_registry().unregister_owner(PET_OWNER)


__all__ = ["PET_BINDINGS", "PET_OWNER", "install_pet_shortcuts", "uninstall_pet_shortcuts"]
