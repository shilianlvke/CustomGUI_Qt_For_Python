"""插件快捷键门面：权限校验、id 命名空间、冲突错误码与卸载清理。

与托盘同一套思路（见 :mod:`sllkgui.gallery.tray`）：

- 所有条目进基座唯一的 :class:`~sllkgui.guicore.shortcuts.ShortcutRegistry`，
  与内置快捷键走同一条派发路径；
- 插件 id 自动加 ``plugin_id:`` 前缀，插件之间、插件与基座之间互不影响；
- 未声明 ``shortcuts`` 权限时访问 ``ctx.shortcuts`` 或调用任何方法都抛
  ``PLUGIN_PERMISSION_DENIED``；
- 加载器在 ``on_unload`` 后调用 :meth:`ShortcutBridge.clear`，条目与回调
  一起释放。

本模块**不在导入期加载 Qt**：只有真正注册快捷键时才会拉起 ``guicore``，
因此 ``sllkgui plugin lint`` 之类的无显示命令仍可直接导入。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .api import GalleryShortcut, GalleryShortcuts, Permission, ShortcutBinding, ShortcutConflict
from .errors import (
    PLUGIN_PERMISSION_DENIED,
    PLUGIN_SHORTCUT_CONFLICT,
    PLUGIN_SHORTCUT_INVALID,
    PLUGIN_SHORTCUT_LOCKED,
    GalleryError,
)

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from sllkgui.guicore.shortcuts import ShortcutRegistry

#: ``ShortcutError.code`` -> Gallery 稳定错误码
_CODE_MAP = {
    "SHORTCUT_CONFLICT": PLUGIN_SHORTCUT_CONFLICT,
    "SHORTCUT_LOCKED": PLUGIN_SHORTCUT_LOCKED,
    "SHORTCUT_INVALID_SEQUENCE": PLUGIN_SHORTCUT_INVALID,
    "SHORTCUT_NOT_FOUND": PLUGIN_SHORTCUT_INVALID,
}


def _to_gallery_error(exc: Exception) -> GalleryError:
    code = _CODE_MAP.get(getattr(exc, "code", ""), PLUGIN_SHORTCUT_INVALID)
    message = getattr(exc, "message", str(exc))
    detail = getattr(exc, "detail", "")
    return GalleryError(code, str(message), str(detail))


class PluginShortcut(GalleryShortcut):
    """单个插件条目的句柄：id 已带前缀，对外只暴露短 id。"""

    def __init__(self, bridge: ShortcutBridge, short_id: str) -> None:
        self._bridge = bridge
        self._short_id = short_id
        self._full_id = f"{bridge.plugin_id}:{short_id}"

    @property
    def shortcut_id(self) -> str:
        return self._short_id

    @property
    def sequence(self) -> str:
        entry = self._entry()
        return entry.sequence if entry is not None else ""

    @property
    def display(self) -> str:
        entry = self._entry()
        return entry.binding.display() if entry is not None else ""

    @property
    def enabled(self) -> bool:
        entry = self._entry()
        return bool(entry.enabled) if entry is not None else False

    def set_enabled(self, enabled: bool) -> None:
        self._bridge.set_enabled(self._short_id, enabled)

    def update(
        self,
        *,
        sequence: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> bool:
        return self._bridge.update(
            self._short_id,
            sequence=sequence,
            description=description,
            priority=priority,
            enabled=enabled,
        )

    def unregister(self) -> None:
        self._bridge.unregister(self._short_id)

    def _entry(self) -> Any:
        registry = self._bridge.registry
        return registry.get(self._full_id) if registry is not None else None


class ShortcutBridge(GalleryShortcuts):
    """插件侧的快捷键入口：权限 + 命名空间 + 错误码翻译。"""

    def __init__(
        self,
        registry: ShortcutRegistry,
        plugin_id: str,
        permissions: tuple[Permission, ...],
    ) -> None:
        self._registry: ShortcutRegistry | None = registry
        self._plugin_id = plugin_id
        self._permissions = permissions

    # ------------------------------------------------------------------
    # 基本信息
    # ------------------------------------------------------------------
    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def registry(self) -> ShortcutRegistry | None:
        return self._registry

    def _require(self, action: str) -> ShortcutRegistry:
        if Permission.SHORTCUTS not in self._permissions:
            raise GalleryError(
                PLUGIN_PERMISSION_DENIED,
                f"插件未声明 shortcuts 权限，无法{action}",
                "在 sllkgui-plugin.yml 的 permissions 中添加 shortcuts",
            )
        if self._registry is None:
            raise GalleryError(PLUGIN_PERMISSION_DENIED, "当前环境不提供快捷键能力")
        return self._registry

    def available(self) -> bool:
        if Permission.SHORTCUTS not in self._permissions or self._registry is None:
            return False
        return True

    def _full(self, shortcut_id: str) -> str:
        return f"{self._plugin_id}:{str(shortcut_id or '').strip()}"

    def _entry(self, shortcut_id: str) -> Any:
        registry = self._registry
        return registry.get(self._full(shortcut_id)) if registry is not None else None

    # ------------------------------------------------------------------
    # 注册 / 更新 / 注销
    # ------------------------------------------------------------------
    def register(
        self,
        shortcut_id: str,
        sequence: str,
        callback: Any,
        *,
        scope: str = "global",
        priority: int | None = None,
        description: str = "",
        allow_in_modal: bool = False,
        conflict: str = "error",
    ) -> PluginShortcut:
        registry = self._require("注册快捷键")
        short_id = str(shortcut_id or "").strip()
        if not short_id:
            raise GalleryError(PLUGIN_SHORTCUT_INVALID, "快捷键 id 不能为空")
        from sllkgui.guicore.shortcuts import PRIORITY_NORMAL

        try:
            registry.register(
                self._full(short_id),
                sequence,
                callback,
                owner=self._plugin_id,
                scope=scope,
                priority=PRIORITY_NORMAL if priority is None else int(priority),
                description=description,
                allow_in_modal=allow_in_modal,
                policy=conflict,
                meta={"plugin_id": self._plugin_id},
            )
        except Exception as exc:  # noqa: BLE001 - 统一翻译成 Gallery 错误码
            raise _to_gallery_error(exc) from exc
        return PluginShortcut(self, short_id)

    def update(
        self,
        shortcut_id: str,
        *,
        sequence: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> bool:
        registry = self._require("更新快捷键")
        try:
            return registry.update(
                self._full(shortcut_id),
                sequence=sequence,
                description=description,
                priority=priority,
                enabled=enabled,
            )
        except Exception as exc:  # noqa: BLE001
            raise _to_gallery_error(exc) from exc

    def set_enabled(self, shortcut_id: str, enabled: bool) -> bool:
        registry = self._require("启停快捷键")
        return registry.set_enabled(self._full(shortcut_id), enabled)

    def unregister(self, shortcut_id: str) -> bool:
        registry = self._require("注销快捷键")
        return registry.unregister(self._full(shortcut_id))

    def handle(self, shortcut_id: str) -> PluginShortcut:
        """取回已注册条目的句柄（未注册时句柄仍可查询，操作为空操作）。"""
        return PluginShortcut(self, str(shortcut_id or "").strip())

    def clear(self) -> None:
        """移除本插件的全部快捷键（卸载路径，不校验权限）。"""
        if self._registry is not None:
            self._registry.unregister_owner(self._plugin_id)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def bindings(self) -> tuple[ShortcutBinding, ...]:
        registry = self._registry
        if registry is None:
            return ()
        items = registry.describe(owner=self._plugin_id)
        return tuple(
            ShortcutBinding(
                shortcut_id=item.shortcut_id.split(":", 1)[-1],
                sequence=item.sequence,
                display=item.display,
                scope=item.scope,
                priority=item.priority,
                enabled=item.enabled,
                plugin_id=self._plugin_id,
                description=item.description,
                locked=item.locked,
            )
            for item in items
        )

    def conflicts(self) -> tuple[ShortcutConflict, ...]:
        """只返回涉及本插件的冲突。

        本插件条目用短 id，其他归属保留完整 id（便于定位是基座内置项还是
        另一个插件占用了序列）；不相关的插件冲突不会出现在这里。
        """
        registry = self._registry
        if registry is None:
            return ()
        result: list[ShortcutConflict] = []
        for item in registry.conflicts():
            if self._plugin_id not in item.owners:
                continue
            result.append(
                ShortcutConflict(
                    sequence=item.sequence,
                    shortcut_ids=tuple(
                        sid.split(":", 1)[-1] if sid.startswith(f"{self._plugin_id}:") else sid
                        for sid in item.shortcut_ids
                    ),
                    owners=item.owners,
                    winner=item.winner,
                )
            )
        return tuple(result)


__all__ = ["PluginShortcut", "ShortcutBridge"]
