import json
from easydict import EasyDict
from pathlib import Path
from AppCore.SYS.logger import Logger

class JsonHandler:
    def __init__(self, file_path):
        self.file_path = Path.cwd() / file_path
        self.data = self.read()

    def read(self):
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                Logger.debug(f"加载文件：'{self.file_path}'")
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"未找到文件：'{self.file_path}'")
        except json.JSONDecodeError as exc:
            Logger.error(f"{self.file_path}解析错误：{exc}")
            return None

    def _write(self):
        with self.file_path.open("w", encoding="utf-8") as f:
            return json.dump(self.data, f, indent=4, ensure_ascii=False)

    def update(self, new_data):
        if isinstance(new_data, dict):
            self.data.update(new_data)
            self._write()
        else:
            Logger.error("json写入失败")

    def merge(self, other):
        self.data.update(other.data)

    def __getitem__(self, key, default=None):
        return self.data.get(key, default)

    def __getattr__(self, item):
        return EasyDict(self.data)[item]

    def __str__(self):
        return json.dumps(self.data, indent=4)
