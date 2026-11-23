"""组件配置读取的共享兜底工具。

配置上下文（主题 / 设计令牌尚未就绪）可能让组件在读取 AppSettings 时抛错；
组件不能因此不可用，统一在这里用默认值兜底。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def resolve_config(getter: Callable[[], Any], defaults: tuple[Any, ...]) -> tuple[Any, ...]:
    """调用 ``getter`` 读取配置，逐项转成 ``defaults`` 对应项的类型。

    ``defaults`` 中每项的类型决定转换：``int`` 项用 ``int()``，``float`` 项用
    ``float()``；其余类型原样保留。转换在 ``getter`` 之外完成，二者任一抛错
    （配置缺失、字段不存在、值无法转换等）都整体回落到 ``defaults``。
    """
    try:
        values = getter()
        return tuple(
            int(value) if type(default) is int else float(value) if type(default) is float else value
            for value, default in zip(values, defaults, strict=False)
        )
    except Exception:  # noqa: BLE001 - 配置上下文未就绪时用兜底值，组件不应因此不可用
        return defaults
