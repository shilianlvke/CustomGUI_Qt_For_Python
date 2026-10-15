"""YAML 文件读写边界（唯一允许第三方库 PyYAML 出现的位置）。

所有读写错误统一转换为 :class:`IOErrorBoundary`，
错误码与历史实现保持一致（YAML_FILE_NOT_FOUND / YAML_PARSE_ERROR /
YAML_READ_ERROR / YAML_WRITE_ERROR）。

若未来切换存储格式（例如迁移到 TOML + 标准库 ``tomllib``），
只需替换本模块，其余配置框架代码无需改动。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from ..module.error_module import IOErrorBoundary
from .paths import resolve_path


def load_yaml_file(path: str | Path) -> dict:
    """读取并解析 YAML 文件，返回普通字典（空文件返回空字典）。"""
    target = resolve_path(path)
    if not target.is_file():
        raise IOErrorBoundary(
            code="YAML_FILE_NOT_FOUND",
            message="配置文件不存在",
            details=str(target),
        )

    try:
        content = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise IOErrorBoundary(
            code="YAML_READ_ERROR",
            message="配置文件读取失败",
            details=f"{target}: {exc}",
        ) from exc

    try:
        raw = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise IOErrorBoundary(
            code="YAML_PARSE_ERROR",
            message="配置文件解析失败",
            details=f"{target}: {exc}",
        ) from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise IOErrorBoundary(
            code="YAML_PARSE_ERROR",
            message="配置文件解析失败",
            details=f"{target}: 顶层结构必须是字典",
        )
    return raw


_DEFAULT_DUMP_OPTIONS: dict[str, Any] = {
    "default_flow_style": False,
    "allow_unicode": True,
    "sort_keys": False,
}


def dump_yaml_file(path: str | Path, data: Mapping, **kwargs: Any) -> None:
    """将映射写入 YAML 文件（自动创建父目录）。

    默认采用 :data:`_DEFAULT_DUMP_OPTIONS`；``kwargs`` 中的同名选项会**覆盖**
    默认值（而非与之冲突），调用方无需担心重复传参。
    """
    target = resolve_path(path)
    options = {**_DEFAULT_DUMP_OPTIONS, **kwargs}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as stream:
            yaml.dump(dict(data), stream, **options)
    except OSError as exc:
        raise IOErrorBoundary(
            code="YAML_WRITE_ERROR",
            message="配置文件保存失败",
            details=f"{target}: {exc}",
        ) from exc
