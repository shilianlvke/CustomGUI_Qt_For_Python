"""属性访问映射（纯标准库实现，替代 easydict）。

`Attrs` 是一个同时支持「属性访问」与「字典访问」的映射类型：

    cfg = Attrs(window=Attrs(width=960), title="demo")
    cfg.window.width   # 960
    cfg["window"].width  # 960
    cfg.get("missing")   # None（属性访问缺失时抛 AttributeError）
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class Attrs(dict):
    """支持属性访问的 dict。

    规则：
    - ``attrs.key`` 等价于 ``attrs["key"]``；
    - 键缺失时 ``__getattr__`` 抛 :class:`AttributeError`（保证
      ``getattr(attrs, key, default)`` 的默认值语义成立）；
    - ``merge`` 提供原地深度合并。
    """

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.keys()))

    def get_path(self, path: str, default: Any = None) -> Any:
        """按点号路径读取嵌套值，如 ``"window.startup_size"``。"""
        value: Any = self
        for part in path.split("."):
            if isinstance(value, Mapping):
                if part in value:
                    value = value[part]
                else:
                    return default
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
        return value

    def merge(self, other: Mapping | Any) -> "Attrs":
        """将另一个映射（或含 ``.data`` 的对象）深度合并进自身，返回 self。"""
        source = getattr(other, "data", other)
        if not isinstance(source, Mapping):
            raise TypeError(f"merge 需要映射对象，收到 {type(other).__name__}")
        deep_merge(self, source)
        return self

    def copy(self) -> "Attrs":
        return Attrs(self)


def deep_merge(target: dict, source: Mapping) -> dict:
    """将 ``source`` 深度合并进 ``target``（原地修改并返回 target）。

    字典递归合并；其余类型（含列表）直接覆盖。
    """
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, Mapping):
            deep_merge(target[key], value)
        else:
            target[key] = to_attrs(value)
    return target


def to_attrs(value: Any) -> Any:
    """递归将嵌套字典转换为 :class:`Attrs`，其余类型原样返回。"""
    if isinstance(value, Attrs):
        return value
    if isinstance(value, Mapping):
        return Attrs((key, to_attrs(item)) for key, item in value.items())
    if isinstance(value, list):
        return [to_attrs(item) for item in value]
    if isinstance(value, tuple):
        return tuple(to_attrs(item) for item in value)
    return value


def to_dict(value: Any) -> Any:
    """递归将 :class:`Attrs` 还原为普通字典（供序列化使用）。"""
    if isinstance(value, Attrs):
        return {key: to_dict(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, tuple):
        return tuple(to_dict(item) for item in value)
    return value
