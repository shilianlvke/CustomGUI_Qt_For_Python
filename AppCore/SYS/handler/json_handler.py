"""JsonHandler：JSON 文件读写处理器（薄封装）。

- 相对路径基于项目根目录解析，不依赖当前工作目录；
- 属性访问通过 :class:`Attrs` 代理，缺失键抛 AttributeError。
"""

from __future__ import annotations

import json

from ..config.mapping import Attrs
from ..config.paths import resolve_path
from ..logger import Logger


class JsonHandler:
    def __init__(self, file_path):
        self.file_path = resolve_path(file_path)
        self.data = self.read()

    def read(self):
        try:
            with self.file_path.open("r", encoding="utf-8") as stream:
                Logger.debug(f"加载文件：'{self.file_path}'")
                return json.load(stream)
        except FileNotFoundError:
            raise FileNotFoundError(f"未找到文件：'{self.file_path}'")
        except json.JSONDecodeError as exc:
            Logger.error(f"{self.file_path}解析错误：{exc}")
            return None

    def _write(self):
        with self.file_path.open("w", encoding="utf-8") as stream:
            return json.dump(self.data, stream, indent=4, ensure_ascii=False)

    def update(self, new_data):
        if isinstance(new_data, dict):
            self.data.update(new_data)
            self._write()
        else:
            Logger.error("json写入失败")

    def merge(self, other):
        self.data.update(other.data)

    def __getitem__(self, key):
        return self.data[key]

    def __getattr__(self, item):
        return getattr(Attrs(self.data), item)

    def __str__(self):
        return json.dumps(self.data, indent=4)
