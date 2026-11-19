"""设置注册表：页面 / 键的全局索引与命名空间隔离。

规则：

- 每个页面属于一个命名空间：基座固定 ``core``，插件固定 ``plugin.<id>``；
- ``(namespace, page_id)`` 唯一，``namespace + "." + setting.key`` 全局唯一；
- 重复注册默认报错（方便定位插件写错 key），插件重载时用
  ``replace=True`` 幂等覆盖；
- 卸载插件时按命名空间整体移除，不影响基座与其它插件。

注册表只在主线程读写；不持有 Qt 对象，可在无显示环境与测试中直接使用。
"""

from __future__ import annotations

import threading

from .schema import (
    SettingsConflictError,
    SettingsError,
    SettingsPage,
    SettingSpec,
    is_core_namespace,
    normalize_namespace,
)

_CORE_ORDER = 0
_PLUGIN_ORDER = 1


class SettingsRegistry:
    """页面与设置键的集中索引。"""

    def __init__(self) -> None:
        self._pages: dict[tuple[str, str], SettingsPage] = {}
        self._keys: dict[str, tuple[SettingsPage, SettingSpec]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # 注册 / 注销
    # ------------------------------------------------------------------
    def register(
        self,
        page: SettingsPage,
        *,
        namespace: str | None = None,
        replace: bool = False,
    ) -> SettingsPage:
        """注册一个设置页；返回带命名空间的页面副本。

        ``namespace`` 为空时沿用页面自带的命名空间（基座页默认 ``core``）。
        同一命名空间内页面 ID 或设置键重复时，``replace=False`` 抛
        :class:`SettingsConflictError`。
        """
        target_ns = normalize_namespace(namespace or page.namespace)
        registered = page.with_namespace(target_ns)
        if not registered.page_id:
            raise SettingsError(f"{target_ns}: 设置页必须提供 page_id")

        with self._lock:
            slot = (target_ns, registered.page_id)
            existing = self._pages.get(slot)
            if existing is not None and not replace:
                raise SettingsConflictError(f"{target_ns}.{registered.page_id}: 设置页已注册")
            # 先检查整页的键是否与现有页面冲突，再一次性写入，避免半注册状态。
            # replace 时只允许占用「本页旧键」，与其它页面冲突仍然报错。
            old_keys = {existing.full_key(spec.key) for spec in existing.specs()} if existing is not None else set()
            for spec in registered.specs():
                full_key = registered.full_key(spec.key)
                if full_key in self._keys and full_key not in old_keys:
                    raise SettingsConflictError(f"设置键重复注册: {full_key}")

            if existing is not None:
                self._remove_page(slot)
            self._pages[slot] = registered
            for spec in registered.specs():
                self._keys[registered.full_key(spec.key)] = (registered, spec)
            return registered

    def unregister_namespace(self, namespace: str) -> int:
        """移除一个命名空间下的全部页面，返回移除的页面数。"""
        target = normalize_namespace(namespace)
        with self._lock:
            slots = [slot for slot in self._pages if slot[0] == target]
            for slot in slots:
                self._remove_page(slot)
            return len(slots)

    def unregister_page(self, page_id: str, *, namespace: str = "core") -> bool:
        with self._lock:
            slot = (normalize_namespace(namespace), page_id)
            if slot not in self._pages:
                return False
            self._remove_page(slot)
            return True

    def clear(self) -> None:
        with self._lock:
            self._pages.clear()
            self._keys.clear()

    def _remove_page(self, slot: tuple[str, str]) -> None:
        page = self._pages.pop(slot, None)
        if page is None:
            return
        for spec in page.specs():
            self._keys.pop(page.full_key(spec.key), None)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def pages(self, namespace: str | None = None) -> tuple[SettingsPage, ...]:
        """按「基座在前、插件在后，再按 order / 标题」返回页面。"""
        target = normalize_namespace(namespace) if namespace else None
        with self._lock:
            items = [page for page in self._pages.values() if target is None or page.namespace == target]
        return tuple(
            sorted(
                items,
                key=lambda page: (
                    _CORE_ORDER if is_core_namespace(page.namespace) else _PLUGIN_ORDER,
                    page.order,
                    page.display_title().lower(),
                    page.page_id,
                ),
            )
        )

    def namespaces(self) -> tuple[str, ...]:
        with self._lock:
            values = sorted({page.namespace for page in self._pages.values()})
        return tuple(values)

    def page(self, page_id: str, *, namespace: str = "core") -> SettingsPage | None:
        with self._lock:
            return self._pages.get((normalize_namespace(namespace), page_id))

    def find(self, full_key: str) -> tuple[SettingsPage, SettingSpec] | None:
        with self._lock:
            return self._keys.get(str(full_key))

    def spec(self, full_key: str) -> SettingSpec | None:
        found = self.find(full_key)
        return found[1] if found is not None else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._pages)


_REGISTRY = SettingsRegistry()


def settings_registry() -> SettingsRegistry:
    """进程级注册表（基座与插件共用）。"""
    return _REGISTRY


def set_settings_registry(registry: SettingsRegistry | None) -> None:
    """替换全局注册表（测试隔离用；传 ``None`` 复位）。"""
    global _REGISTRY
    _REGISTRY = registry or SettingsRegistry()


__all__ = [
    "SettingsRegistry",
    "set_settings_registry",
    "settings_registry",
]
