"""插件服务注册表：按 owner 注册与解析，卸载时只清自己的服务。

插件经 ``ctx.services`` 拿到绑定自身 ``plugin_id`` 的句柄。服务名默认是
提供者的 plugin_id；消费关系用清单的 ``dependencies`` 表达（加载顺序与
卸载阻止已由 manager 处理）。仅在本进程内分发，无跨进程协议。

owner-token 双表范式来自真实下游的 measure_registry：值表与 owner 表并行，
注销时校验 owner 相等才删，避免误删别的插件注册的同名服务。
"""

from __future__ import annotations

import threading
from typing import Any

from .api import GalleryServices


class ServiceHandle(GalleryServices):
    """绑定到单一 owner（plugin_id）的插件视图。"""

    def __init__(self, registry: PluginServiceRegistry, owner: str) -> None:
        self._registry = registry
        self.owner = owner

    def register(self, service: Any, *, name: str | None = None) -> bool:
        """注册服务；名称缺省为 owner，冒名（name != owner）被拒。"""
        target = name or self.owner
        if target != self.owner:
            return False
        return self._registry._register(target, service, self.owner)

    def get(self, name: str) -> Any | None:
        return self._registry._get(name)

    def has(self, name: str) -> bool:
        return self._registry._get(name) is not None

    def unregister(self, name: str) -> None:
        self._registry._unregister(name, self.owner)

    def clear(self) -> None:
        self._registry.clear_owner(self.owner)


class PluginServiceRegistry:
    """进程内服务注册表（每 runtime 一个实例）。"""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._owners: dict[str, str] = {}
        self._lock = threading.RLock()

    def handle(self, owner: str) -> ServiceHandle:
        return ServiceHandle(self, owner)

    def _register(self, name: str, service: Any, owner: str) -> bool:
        with self._lock:
            existing_owner = self._owners.get(name)
            if existing_owner is not None and existing_owner != owner:
                return False  # 重名异主拒绝
            self._values[name] = service
            self._owners[name] = owner
            return True

    def _get(self, name: str) -> Any | None:
        with self._lock:
            return self._values.get(name)

    def _unregister(self, name: str, owner: str) -> None:
        with self._lock:
            if self._owners.get(name) != owner:
                return  # 只清自己的
            self._values.pop(name, None)
            self._owners.pop(name, None)

    def clear_owner(self, owner: str) -> None:
        """只清指定 owner 的全部服务。"""
        with self._lock:
            for name in [n for n, o in self._owners.items() if o == owner]:
                self._values.pop(name, None)
                self._owners.pop(name, None)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self._owners.clear()


__all__ = ["PluginServiceRegistry", "ServiceHandle"]
