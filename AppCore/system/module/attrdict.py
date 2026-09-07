"""属性访问字典。

职责:
- 提供支持点访问的字典结构，替代第三方 ``easydict`` 依赖。
- 提供字典与属性字典之间的递归转换能力。

说明:
- ``AttrDict`` 是 ``dict`` 子类，仅补充属性读写代理，其余行为与字典一致。
- ``to_attrdict`` 与 ``to_plain_dict`` 为纯函数，供配置加载层复用。
"""

__all__ = ["AttrDict", "to_attrdict", "to_plain_dict"]


class AttrDict(dict):
    """支持属性访问的字典。"""

    def __getattr__(self, name: str) -> object:
        """以属性方式读取字典键。"""
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: object) -> None:
        """以属性方式写入字典键。"""
        self[name] = value

    def __delattr__(self, name: str) -> None:
        """以属性方式删除字典键。"""
        try:
            del self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def to_attrdict(data: object) -> object:
    """递归将字典转换为属性字典。

    参数:
    - data: 待转换对象，可为字典、列表或标量。

    返回:
    - object: 转换后的属性字典结构。
    """
    if isinstance(data, dict):
        return AttrDict({key: to_attrdict(value) for key, value in data.items()})
    if isinstance(data, list):
        return [to_attrdict(item) for item in data]
    return data


def to_plain_dict(data: object) -> object:
    """递归将属性字典转换为普通字典。

    参数:
    - data: 待转换对象，可为属性字典、列表或标量。

    返回:
    - object: 转换后的普通字典结构。
    """
    if isinstance(data, dict):
        return {key: to_plain_dict(value) for key, value in data.items()}
    if isinstance(data, list):
        return [to_plain_dict(item) for item in data]
    return data
