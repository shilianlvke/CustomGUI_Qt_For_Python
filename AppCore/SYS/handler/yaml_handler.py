"""YamlHandler：单文件 YAML 配置处理器（薄封装，逻辑位于 AppCore.SYS.config）。

- 相对路径基于项目根目录解析，不依赖当前工作目录；
- ``data`` 为 :class:`AppCore.SYS.config.mapping.Attrs`（属性/字典双访问）；
- 读写错误统一抛 :class:`IOErrorBoundary`（错误码与历史实现一致）。
"""

from __future__ import annotations

from typing import Any, Mapping

from ..config.mapping import Attrs, deep_merge, to_attrs, to_dict
from ..config.paths import resolve_path
from ..config.yaml_io import dump_yaml_file, load_yaml_file


class YamlHandler:
    """加载/修改/保存单个 YAML 文件。

    Args:
        file_path: YAML 文件路径（相对路径基于项目根目录）。
        auto_load: 是否在初始化时立即加载。
    """

    def __init__(self, file_path: str, auto_load: bool = True):
        self.file_path = file_path
        self.data: Attrs = Attrs()
        if auto_load:
            self.load()

    def load(self, file_path: str | None = None) -> Attrs:
        """加载 YAML 文件，返回 Attrs 数据。"""
        if file_path is not None:
            self.file_path = file_path

        raw = load_yaml_file(resolve_path(self.file_path))
        self.data = to_attrs(raw)
        return self.data

    def save(self, data: Mapping | None = None, file_path: str | None = None, **kwargs) -> None:
        """保存数据到 YAML 文件（默认保存当前 data，自动创建目录）。"""
        target = file_path or self.file_path
        dump_yaml_file(resolve_path(target), to_dict(data if data is not None else self.data), **kwargs)

    def merge(self, other: "YamlHandler | Attrs | Mapping") -> "YamlHandler":
        """将另一个 YAML 配置（或其数据）深度合并进自身，返回 self。"""
        source = getattr(other, "data", other)
        if not isinstance(source, Mapping):
            raise TypeError(f"merge 需要映射对象，收到 {type(other).__name__}")
        deep_merge(self.data, source)
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """按点号路径读取嵌套值，如 ``"database.host"``。"""
        return self.data.get_path(key, default)

    def set(self, key: str, value: Any) -> None:
        """按点号路径设置嵌套值，缺失的中间层自动创建。"""
        parts = key.split(".")
        current: Attrs = self.data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], Attrs):
                current[part] = Attrs()
            current = current[part]
        current[parts[-1]] = to_attrs(value)

    def to_dict(self) -> dict:
        """还原为普通字典。"""
        return to_dict(self.data)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getattr__(self, name):
        return getattr(self.data, name)

    def __str__(self):
        return str(self.data)

    def __repr__(self):
        return f"YamlHandler(file_path='{self.file_path}')"
