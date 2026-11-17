"""``GallerySettings`` 实现：把插件配置接到统一设置框架。

职责边界：

- 声明页面 → 注册到全局注册表（命名空间固定 ``plugin.<plugin_id>``）；
- 读写配置 → 走共享 ``SettingsStore``，与设置窗口看到同一份缓存；
- 变更通知 → 自身写入直接回调，设置窗口保存经变更总线转发。

插件卸载时调用 :meth:`PluginSettings.clear`：移除页面与订阅，但**保留磁盘
文件**，重新加载后用户的配置仍然有效。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from sllkgui.appcore import (
    Logger,
    SettingsError,
    SettingsPage,
    SettingsRegistry,
    SettingsStore,
    normalize_value,
    plugin_namespace,
    settings_change_bus,
    settings_registry,
    settings_store,
)

from .api import GallerySettings


class PluginSettings(GallerySettings):
    """单个插件的设置桥接。"""

    def __init__(
        self,
        plugin_id: str,
        *,
        registry: SettingsRegistry | None = None,
        store: SettingsStore | None = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._namespace = plugin_namespace(plugin_id)
        self._registry = registry if registry is not None else settings_registry()
        self._store = store if store is not None else settings_store()
        self._callbacks: list[Callable[[str, Any], None]] = []
        self._unsubscribe = settings_change_bus().subscribe(self._namespace, self._on_external_change)
        self._prefix = f"[plugin:{plugin_id}]"

    # ------------------------------------------------------------------
    @property
    def namespace(self) -> str:
        return self._namespace

    def define(self, page: SettingsPage) -> None:
        """声明本插件的唯一设置页；重复调用整体替换。"""
        prepared = replace(
            page,
            page_id=page.page_id or self._plugin_id,
            namespace=self._namespace,
            origin="plugin",
        )
        # 一个插件一张页：先清空命名空间，避免修改 page_id 后残留旧页
        self._registry.unregister_namespace(self._namespace)
        self._registry.register(prepared, namespace=self._namespace, replace=True)
        Logger.debug(f"{self._prefix} 设置页已注册: {prepared.page_id}")

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        spec = self._registry.spec(f"{self._namespace}.{key}")
        if spec is None:
            return default
        raw = self._store.load(self._namespace).get(key, spec.default)
        try:
            return normalize_value(spec, raw)
        except SettingsError as exc:
            Logger.warning(f"{self._prefix} 配置值非法，回落默认值: {key}: {exc}")
            return spec.default

    def set(self, key: str, value: Any) -> bool:
        spec = self._registry.spec(f"{self._namespace}.{key}")
        if spec is None:
            Logger.warning(f"{self._prefix} 未声明的设置键: {key}")
            return False
        try:
            normalized = normalize_value(spec, value)
        except SettingsError as exc:
            Logger.warning(f"{self._prefix} 配置值非法: {key}: {exc}")
            return False
        if not self._store.save(self._namespace, {key: normalized}):
            return False
        self._notify(key, normalized)
        return True

    def reset(self, key: str) -> bool:
        spec = self._registry.spec(f"{self._namespace}.{key}")
        if spec is None:
            return False
        return self.set(key, spec.default)

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for page in self._registry.pages(self._namespace):
            for spec in page.specs():
                result[spec.key] = self.get(spec.key, spec.default)
        return result

    def on_changed(self, callback: Callable[[str, Any], None]) -> Callable[[], None]:
        if not callable(callback):
            raise TypeError("callback 必须可调用")
        self._callbacks.append(callback)

        def unsubscribe() -> None:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                return

        return unsubscribe

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """卸载插件时清理注册表与订阅（磁盘配置保留）。"""
        self._registry.unregister_namespace(self._namespace)
        self._callbacks.clear()
        try:
            self._unsubscribe()
        except Exception as exc:  # noqa: BLE001 - 清理失败不影响卸载
            Logger.debug(f"{self._prefix} 设置订阅清理失败: {exc}")

    # ------------------------------------------------------------------
    def _on_external_change(self, changes: Mapping[str, Any]) -> None:
        """设置窗口保存后的广播（短键 -> 值）。"""
        for key, value in changes.items():
            self._notify(str(key), value)

    def _notify(self, key: str, value: Any) -> None:
        for callback in list(self._callbacks):
            try:
                callback(key, value)
            except Exception as exc:  # noqa: BLE001 - 单个订阅者失败不影响保存
                Logger.warning(f"{self._prefix} 设置变更回调失败: {key}: {exc}")


__all__ = ["PluginSettings"]
