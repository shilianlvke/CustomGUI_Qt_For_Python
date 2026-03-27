"""模块说明。"""

import json
from pathlib import Path

import yaml
from easydict import EasyDict

from AppCore.SYS.module.error_module import IOErrorBoundary


class YamlHandler:
    """YAML 配置处理器。

    职责:
    - 负责 YAML 配置的加载、保存、更新与查询。
    - 提供 EasyDict 与 dict 之间的转换能力。
    """

    def __init__(self, file_path: str, *, auto_load: bool = True) -> None:
        """初始化 YAML 处理器。

        参数:
        - file_path: YAML 文件路径。
        - auto_load: 是否在初始化时自动加载。

        返回:
        - None
        """
        self.file_path = file_path
        self.data = EasyDict()

        if auto_load:
            self.load()

    def load(self, file_path: str | None = None) -> EasyDict:
        """加载 YAML 文件。

        参数:
        - file_path: 可选文件路径，传入时会覆盖当前路径。

        返回:
        - EasyDict: 解析后的配置对象。
        """
        if file_path:
            self.file_path = file_path

        yaml_path = Path(self.file_path)
        if not yaml_path.exists():
            raise IOErrorBoundary(
                code="YAML_FILE_NOT_FOUND",
                message="配置文件不存在",
                details=self.file_path,
            )

        try:
            with yaml_path.open(encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise IOErrorBoundary(
                code="YAML_PARSE_ERROR",
                message="配置文件解析失败",
                details=f"{self.file_path}: {exc}",
            ) from exc
        except OSError as exc:
            raise IOErrorBoundary(
                code="YAML_READ_ERROR",
                message="配置文件读取失败",
                details=f"{self.file_path}: {exc}",
            ) from exc

        # 将嵌套字典转换为EasyDict
        self.data = self._dict_to_easydict(raw_data)
        return self.data

    def save(
        self,
        data: dict[str, object] | EasyDict | None = None,
        file_path: str | None = None,
        **kwargs: object,
    ) -> None:
        """保存数据到 YAML 文件。

        参数:
        - data: 待保存数据；为空时保存当前 data。
        - file_path: 可选输出路径。
        - **kwargs: 透传给 yaml.dump 的参数。

        返回:
        - None
        """
        save_path = file_path or self.file_path

        # 确保目录存在
        Path(save_path).resolve().parent.mkdir(parents=True, exist_ok=True)

        if data is None:
            data = self.data

        # 如果传入的是EasyDict，转换为普通字典
        if isinstance(data, EasyDict):
            data = self._easydict_to_dict(data)

        try:
            with Path(save_path).open("w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, **kwargs)
        except OSError as exc:
            raise IOErrorBoundary(
                code="YAML_WRITE_ERROR",
                message="配置文件保存失败",
                details=f"{save_path}: {exc}",
            ) from exc

    def update(self, new_data: dict[str, object] | EasyDict, *, merge: bool = True) -> None:
        """更新内存中的配置数据。

        参数:
        - new_data: 新数据。
        - merge: True 为深度合并，False 为整体替换。

        返回:
        - None
        """
        if isinstance(new_data, EasyDict):
            new_data = self._easydict_to_dict(new_data)

        if merge:
            # 深度合并字典
            self._deep_update(self.data, new_data)
        else:
            self.data = self._dict_to_easydict(new_data)

    def get(self, key: str, default: object = None) -> object:
        """获取配置值，支持点路径。

        参数:
        - key: 键名，支持如 ``database.host`` 的点路径。
        - default: 缺失时的默认值。

        返回:
        - Any: 查找到的值或默认值。
        """
        keys = key.split(".")
        value = self.data

        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: object) -> None:
        """设置配置值，支持点路径。

        参数:
        - key: 键名，支持如 ``database.host`` 的点路径。
        - value: 要设置的值。

        返回:
        - None
        """
        keys = key.split(".")
        current = self.data

        # 导航到最后一个键的父级
        for k in keys[:-1]:
            if not hasattr(current, k):
                setattr(current, k, EasyDict())
            current = getattr(current, k)

        # 设置值
        last_key = keys[-1]

        # 如果值是字典，转换为EasyDict
        if isinstance(value, dict):
            value = self._dict_to_easydict(value)

        setattr(current, last_key, value)

    def to_dict(self) -> dict[str, object]:
        """将当前数据转换为普通字典。

        返回:
        - Dict: 普通字典数据。
        """
        return self._easydict_to_dict(self.data)

    def to_json(self, indent: int = 2) -> str:
        """将当前数据转换为 JSON 字符串。

        参数:
        - indent: 缩进空格数。

        返回:
        - str: JSON 字符串。
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def reload(self) -> EasyDict:
        """重新加载当前 YAML 文件。

        返回:
        - EasyDict: 重新加载后的数据对象。
        """
        return self.load()

    def _dict_to_easydict(self, data: dict[str, object] | object) -> EasyDict | object:
        """递归将字典转换为 EasyDict。

        参数:
        - data: 待转换字典。

        返回:
        - EasyDict: 转换结果。
        """
        if not isinstance(data, dict):
            return data

        result = EasyDict()
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._dict_to_easydict(value)
            elif isinstance(value, list):
                result[key] = [self._dict_to_easydict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    def _easydict_to_dict(
        self,
        data: EasyDict | dict[str, object] | list[object] | object,
    ) -> dict[str, object] | list[object] | object:
        """递归将 EasyDict 转换为普通字典。

        参数:
        - data: 待转换对象。

        返回:
        - Dict: 转换结果。
        """
        if isinstance(data, (EasyDict, dict)):
            return {key: self._easydict_to_dict(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._easydict_to_dict(item) for item in data]
        return data

    def _deep_update(self, original: EasyDict, new_data: dict[str, object]) -> None:
        """深度更新字典对象。

        参数:
        - original: 原始 EasyDict。
        - new_data: 新数据字典。

        返回:
        - None
        """
        for key, value in new_data.items():
            if key in original and isinstance(original[key], (dict, EasyDict)) and isinstance(value, dict):
                self._deep_update(original[key], value)
            else:
                # 如果值是字典，转换为EasyDict
                updated_value = value
                if isinstance(value, dict):
                    updated_value = self._dict_to_easydict(value)
                original[key] = updated_value

    def __getitem__(self, key: str) -> object:
        """支持字典式读取。"""
        return getattr(self.data, key)

    def __setitem__(self, key: str, value: object) -> None:
        """支持字典式写入。"""
        setattr(self.data, key, value)

    def __getattr__(self, name: str) -> object:
        """将属性访问代理到内部 data 对象。"""
        return getattr(self.data, name)

    def __str__(self) -> str:
        """返回字符串表示。"""
        return str(self.data)

    def __repr__(self) -> str:
        """返回调试表示字符串。"""
        return f"YamlHandler(file_path='{self.file_path}')"
