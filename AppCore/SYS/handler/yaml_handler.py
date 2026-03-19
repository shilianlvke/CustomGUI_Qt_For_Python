import yaml
from easydict import EasyDict
import os
from typing import Any, Dict, Union, Optional
import json
from ..module.error_module import IOErrorBoundary


class YamlHandler:
    def __init__(self, file_path: str, auto_load: bool = True):
        """
        初始化YamlHandler

        Args:
            file_path: YAML文件路径
            auto_load: 是否在初始化时自动加载文件
        """
        self.file_path = file_path
        self.data = EasyDict()

        if auto_load:
            self.load()

    def load(self, file_path: Optional[str] = None) -> EasyDict:
        """
        加载YAML文件

        Args:
            file_path: 可选，指定要加载的文件路径

        Returns:
            EasyDict对象
        """
        if file_path:
            self.file_path = file_path

        if not os.path.exists(self.file_path):
            raise IOErrorBoundary(
                code="YAML_FILE_NOT_FOUND",
                message="配置文件不存在",
                details=self.file_path,
            )

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
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

    def save(self, data: Optional[Union[Dict, EasyDict]] = None, file_path: Optional[str] = None, **kwargs):
        """
        保存数据到YAML文件

        Args:
            data: 要保存的数据，如果为None则保存当前data
            file_path: 可选，指定保存的文件路径
            **kwargs: 传递给yaml.dump的其他参数
        """
        if file_path:
            save_path = file_path
        else:
            save_path = self.file_path

        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

        if data is None:
            data = self.data

        # 如果传入的是EasyDict，转换为普通字典
        if isinstance(data, EasyDict):
            data = self._easydict_to_dict(data)

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, **kwargs)
        except OSError as exc:
            raise IOErrorBoundary(
                code="YAML_WRITE_ERROR",
                message="配置文件保存失败",
                details=f"{save_path}: {exc}",
            ) from exc

    def update(self, new_data: Union[Dict, EasyDict], merge: bool = True):
        """
        更新数据

        Args:
            new_data: 新的数据
            merge: 是否合并数据（True为合并，False为替换）
        """
        if isinstance(new_data, EasyDict):
            new_data = self._easydict_to_dict(new_data)

        if merge:
            # 深度合并字典
            self._deep_update(self.data, new_data)
        else:
            self.data = self._dict_to_easydict(new_data)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取值，支持点符号访问嵌套键

        Args:
            key: 键名，支持点符号如 "database.host"
            default: 默认值

        Returns:
            对应的值
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

    def set(self, key: str, value: Any):
        """
        设置值，支持点符号访问嵌套键

        Args:
            key: 键名，支持点符号如 "database.host"
            value: 要设置的值
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

    def to_dict(self) -> Dict:
        """
        将EasyDict转换为普通字典

        Returns:
            普通字典
        """
        return self._easydict_to_dict(self.data)

    def to_json(self, indent: int = 2) -> str:
        """
        将数据转换为JSON字符串

        Args:
            indent: JSON缩进

        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def reload(self) -> EasyDict:
        """
        重新加载文件

        Returns:
            EasyDict对象
        """
        return self.load()

    def _dict_to_easydict(self, data: Dict) -> EasyDict:
        """递归将字典转换为EasyDict"""
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

    def _easydict_to_dict(self, data: Union[EasyDict, Any]) -> Dict:
        """递归将EasyDict转换为普通字典"""
        if isinstance(data, EasyDict):
            return {key: self._easydict_to_dict(value) for key, value in data.items()}
        elif isinstance(data, dict):
            return {key: self._easydict_to_dict(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._easydict_to_dict(item) for item in data]
        else:
            return data

    def _deep_update(self, original: EasyDict, new_data: Dict):
        """深度更新字典"""
        for key, value in new_data.items():
            if key in original and isinstance(original[key], (dict, EasyDict)) and isinstance(value, dict):
                self._deep_update(original[key], value)
            else:
                # 如果值是字典，转换为EasyDict
                if isinstance(value, dict):
                    value = self._dict_to_easydict(value)
                original[key] = value

    def __getitem__(self, key):
        """支持字典式访问"""
        return getattr(self.data, key)

    def __setitem__(self, key, value):
        """支持字典式设置"""
        setattr(self.data, key, value)

    def __getattr__(self, name):
        """代理属性访问到data"""
        return getattr(self.data, name)

    def __str__(self):
        """字符串表示"""
        return str(self.data)

    def __repr__(self):
        """repr表示"""
        return f"YamlHandler(file_path='{self.file_path}')"
