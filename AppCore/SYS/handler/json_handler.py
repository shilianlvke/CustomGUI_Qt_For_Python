"""模块说明。"""

import json
from pathlib import Path

from easydict import EasyDict

from AppCore.SYS.logger import Logger


class JsonHandler:
    """JSON 文件处理器。

    职责:
    - 读取、更新与写回 JSON 配置数据。
    - 提供字典式与属性式访问能力。
    """

    def __init__(self, file_path: str | Path) -> None:
        """初始化 JSON 处理器并加载文件。

        参数:
        - file_path: JSON 文件相对路径。

        返回:
        - None
        """
        self.file_path = Path.cwd() / file_path
        self.data = self.read()

    def read(self) -> dict[str, object] | None:
        """读取 JSON 文件内容。

        返回:
        - dict | None: 解析结果；解析失败时返回 None。
        """
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                Logger.debug(f"加载文件：'{self.file_path}'")
                return json.load(f)
        except FileNotFoundError as exc:
            message = f"未找到文件：'{self.file_path}'"
            raise FileNotFoundError(message) from exc
        except json.JSONDecodeError as exc:
            Logger.error(f"{self.file_path}解析错误：{exc}")
            return None

    def _write(self) -> None:
        """将当前数据写回 JSON 文件。

        返回:
        - Any: json.dump 的返回值。
        """
        with self.file_path.open("w", encoding="utf-8") as f:
            return json.dump(self.data, f, indent=4, ensure_ascii=False)

    def update(self, new_data: dict[str, object]) -> None:
        """更新当前 JSON 数据并写回文件。

        参数:
        - new_data: 待更新字典。

        返回:
        - None
        """
        if isinstance(new_data, dict):
            self.data.update(new_data)
            self._write()
        else:
            Logger.error("json写入失败")

    def merge(self, other: "JsonHandler") -> None:
        """将另一个 JsonHandler 的数据合并到当前对象。

        参数:
        - other: 另一个 JsonHandler 实例。

        返回:
        - None
        """
        self.data.update(other.data)

    def __getitem__(self, key: str, default: object | None = None) -> object | None:
        """按键获取数据。

        参数:
        - key: 键名。
        - default: 默认值。

        返回:
        - Any: 对应值或默认值。
        """
        return self.data.get(key, default)

    def __getattr__(self, item: str) -> object:
        """按属性方式读取数据字段。"""
        return EasyDict(self.data)[item]

    def __str__(self) -> str:
        """返回格式化后的 JSON 字符串。"""
        return json.dumps(self.data, indent=4)
