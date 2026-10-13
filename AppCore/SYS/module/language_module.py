from dataclasses import dataclass
from typing import Any

from ..config.mapping import Attrs, to_attrs


@dataclass
class LanguageHandler:
    """语言包容器：保存当前激活语言的全部文本。

    - ``update``：增量合并（历史兼容）；
    - ``replace``：清空后整体替换（语言切换使用，避免旧语言残留键）；
    - ``resolve`` / ``resolve_key``：按点号路径读取文本，
      支持 ``language.app.example.app_text`` 形式的资源键引用。
    """

    def update(self, new_str: dict) -> None:
        for key, value in new_str.items():
            setattr(self, key, to_attrs(value))

    def replace(self, new_str: dict) -> None:
        """清空全部动态键并整体替换（实例属性即语言数据）。"""
        for key in list(self.__dict__):
            delattr(self, key)
        self.update(new_str)

    def resolve(self, path: str, default: Any = None) -> Any:
        """按点号路径读取嵌套文本，如 ``"app.p2ptest_home.app_text"``。"""
        value: Any = self
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, Attrs) and part in value:
                value = value[part]
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
        return value

    def resolve_key(self, key: str, default: Any = None) -> Any:
        """解析 ``language.<path>`` 资源键；非资源键原样返回。"""
        if isinstance(key, str) and key.startswith("language."):
            return self.resolve(key[len("language.") :], default if default is not None else key)
        return key


Language = LanguageHandler()


__all__ = ["Language", "LanguageHandler"]
