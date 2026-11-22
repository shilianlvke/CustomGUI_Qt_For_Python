"""设置会话：把「页面声明 + 当前值 + 未保存改动」收在一处。

UI 只与 :class:`SettingsSession` 交互：

- ``set(key, value)`` 只改内存草稿并校验，不落盘；
- ``save()`` 按命名空间分组写入，成功后把草稿提升为基线；
- ``discard()`` 丢弃全部草稿，供「放弃」按钮与关闭确认使用；
- ``changes()`` / ``preview_keys()`` 给宿主做「保存后应用」与「实时预览」。

这样「编辑 → 保存 / 放弃」的语义只实现一次，基座页面与插件页面完全一致。
本模块不导入 Qt。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..sysx.modules.logger_module import Logger
from .events import settings_change_bus
from .registry import SettingsRegistry, settings_registry
from .schema import (
    SettingsError,
    SettingsPage,
    SettingSpec,
    SettingsValidationError,
    normalize_value,
)
from .store import SettingsStore, settings_store


class SettingsSession:
    """一次设置编辑会话（打开设置窗口时创建）。"""

    def __init__(
        self,
        registry: SettingsRegistry | None = None,
        store: SettingsStore | None = None,
    ) -> None:
        self._registry = registry if registry is not None else settings_registry()
        self._store = store if store is not None else settings_store()
        #: 已保存的基线值：full_key -> value
        self._baseline: dict[str, Any] = {}
        #: 当前草稿（含未保存改动）
        self._draft: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self.reload()

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """按注册表重新读取全部命名空间；未保存改动会被丢弃。"""
        baseline: dict[str, Any] = {}
        loaded: dict[str, dict[str, Any]] = {}
        for page in self._registry.pages():
            values = loaded.get(page.namespace)
            if values is None:
                try:
                    values = self._store.load(page.namespace)
                except (OSError, ValueError) as exc:  # pragma: no cover - 防御式分支
                    Logger.warning(f"设置读取失败，使用默认值: {page.namespace}: {exc}")
                    values = {}
                loaded[page.namespace] = values
            for spec in page.specs():
                full_key = page.full_key(spec.key)
                raw = values.get(page.storage_key(spec), spec.default)
                try:
                    baseline[full_key] = normalize_value(spec, raw)
                except SettingsValidationError as exc:
                    Logger.warning(f"设置值非法，回落默认值: {full_key}: {exc}")
                    baseline[full_key] = spec.default
        self._baseline = baseline
        self._draft = dict(baseline)
        self._dirty.clear()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @property
    def registry(self) -> SettingsRegistry:
        return self._registry

    @property
    def store(self) -> SettingsStore:
        return self._store

    def pages(self, namespace: str | None = None) -> tuple[SettingsPage, ...]:
        return self._registry.pages(namespace)

    def spec(self, full_key: str) -> tuple[SettingsPage, SettingSpec]:
        found = self._registry.find(full_key)
        if found is None:
            raise SettingsError(f"未注册的设置键: {full_key}")
        return found

    def value(self, full_key: str) -> Any:
        self.spec(full_key)
        return self._draft[full_key]

    def baseline(self, full_key: str) -> Any:
        self.spec(full_key)
        return self._baseline[full_key]

    def is_modified(self, full_key: str) -> bool:
        return full_key in self._dirty

    def is_default(self, full_key: str) -> bool:
        _page, spec = self.spec(full_key)
        return self._draft[full_key] == spec.default

    def dirty_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._dirty))

    def dirty_count(self) -> int:
        return len(self._dirty)

    def is_dirty(self) -> bool:
        return bool(self._dirty)

    def changes(self) -> dict[str, Any]:
        """未保存改动：``full_key -> 草稿值``。"""
        return {key: self._draft[key] for key in self._dirty}

    def preview_keys(self) -> tuple[str, ...]:
        """其中声明了 ``live_preview`` 的键（主题 / 材质 / 背景）。"""
        result = []
        for key in self._dirty:
            spec = self._registry.spec(key)
            if spec is not None and spec.live_preview:
                result.append(key)
        return tuple(sorted(result))

    def page_dirty_count(self, page: SettingsPage) -> int:
        # 键本身不含页面 ID，因此用页面声明集合精确判断，避免前缀误伤
        keys = {page.full_key(spec.key) for spec in page.specs()}
        return len(keys & self._dirty)

    # ------------------------------------------------------------------
    # 编辑
    # ------------------------------------------------------------------
    def set(self, full_key: str, value: Any) -> bool:
        """校验并写入草稿；返回是否有变化（值相同则视为未改动）。"""
        _page, spec = self.spec(full_key)
        normalized = normalize_value(spec, value)
        if normalized == self._draft[full_key]:
            if self._baseline[full_key] == normalized:
                self._dirty.discard(full_key)
            return False
        self._draft[full_key] = normalized
        if normalized == self._baseline[full_key]:
            self._dirty.discard(full_key)
        else:
            self._dirty.add(full_key)
        return True

    def reset(self, full_key: str) -> bool:
        """把单个键恢复为声明默认值（进入未保存状态）。"""
        _page, spec = self.spec(full_key)
        return self.set(full_key, spec.default)

    def reset_page(self, page: SettingsPage) -> int:
        """恢复整页默认值，返回实际变化的键数。"""
        count = 0
        for spec in page.specs():
            if self.reset(page.full_key(spec.key)):
                count += 1
        return count

    def reset_all(self) -> int:
        count = 0
        for page in self._registry.pages():
            count += self.reset_page(page)
        return count

    def discard(self) -> None:
        self._draft = dict(self._baseline)
        self._dirty.clear()

    def prune_namespace(self, namespace: str) -> tuple[str, ...]:
        """移除命名空间中已不存在于注册表的草稿键。

        插件热重载后可能删掉或改名设置键；旧草稿如果继续保留，
        ``save()`` 会在 ``self.spec(key)`` 上抛 ``SettingsError``。返回被
        丢弃的完整键，便于设置窗口提示用户。
        """
        prefix = f"{namespace}."
        valid = {page.full_key(spec.key) for page in self._registry.pages(namespace) for spec in page.specs()}
        removed = tuple(key for key in sorted(self._dirty) if key.startswith(prefix) and key not in valid)
        for key in removed:
            self._dirty.discard(key)
            self._draft.pop(key, None)
            self._baseline.pop(key, None)
        return removed

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def storage_updates(self) -> dict[str, dict[str, Any]]:
        """按命名空间汇总待写入的存储键值（基座使用历史键名）。"""
        grouped: dict[str, dict[str, Any]] = {}
        for key in self._dirty:
            page, spec = self.spec(key)
            grouped.setdefault(page.namespace, {})[page.storage_key(spec)] = self._draft[key]
        return grouped

    def save(self) -> bool:
        """写入全部改动；全部成功才清空脏标记，返回是否成功。

        某个命名空间失败时保留它的脏标记，成功写入的命名空间已经落盘，
        避免下一次保存重复覆盖用户刚改好的其它配置。
        """
        if not self._dirty:
            return True
        succeeded: list[str] = []
        failed: list[str] = []
        for namespace, updates in self.storage_updates().items():
            try:
                ok = self._store.save(namespace, updates)
            except (OSError, ValueError) as exc:  # pragma: no cover - 防御式分支
                Logger.warning(f"设置保存异常: {namespace}: {exc}")
                ok = False
            (succeeded if ok else failed).append(namespace)

        for namespace in succeeded:
            prefix = f"{namespace}."
            changes: dict[str, Any] = {}
            for key in [item for item in self._dirty if item.startswith(prefix)]:
                page, spec = self.spec(key)
                changes[spec.key] = self._draft[key]
                self._baseline[key] = self._draft[key]
                self._dirty.discard(key)
            # 会话层写入插件配置时，插件运行时需要知道值变了
            settings_change_bus().publish(namespace, changes)
        if failed:
            Logger.warning(f"设置保存失败，保留未保存状态: {', '.join(sorted(failed))}")
            return False
        return True

    # ------------------------------------------------------------------
    # 应用辅助
    # ------------------------------------------------------------------
    def values_for_page(self, page: SettingsPage) -> dict[str, Any]:
        return {spec.key: self._draft[page.full_key(spec.key)] for spec in page.specs()}

    def by_namespace(self, namespace: str) -> dict[str, Any]:
        """某命名空间下的草稿值：``短键 -> 值``（供插件 / 宿主直接消费）。"""
        result: dict[str, Any] = {}
        for page in self._registry.pages(namespace):
            for spec in page.specs():
                result[spec.key] = self._draft[page.full_key(spec.key)]
        return result

    def restore_defaults_snapshot(self) -> dict[str, Any]:
        """全部声明默认值：``full_key -> 默认值``（测试与诊断用）。"""
        return {page.full_key(spec.key): spec.default for page in self._registry.pages() for spec in page.specs()}

    def with_values(self, values: Mapping[str, Any]) -> SettingsSession:
        """返回应用了给定值的副本（不落盘，测试 / 预览用）。"""
        clone = SettingsSession(self._registry, self._store)
        for key, value in values.items():
            clone.set(key, value)
        return clone


def iter_live_preview(session: SettingsSession) -> Iterable[tuple[str, Any]]:
    """遍历需要实时预览的改动（``full_key, value``）。"""
    for key in session.preview_keys():
        yield key, session.value(key)


__all__ = ["SettingsSession", "iter_live_preview"]
