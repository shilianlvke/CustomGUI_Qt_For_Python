"""通用小工具：JSON/文本的原子读写。

只收**与平台无关、与业务无关**的东西。串口/HID/网卡枚举那类 Windows 专有的
设备探测不进基座——它们会拖入 ``pyserial`` / ``hidapi`` / ``wmi`` 三个可选依赖，
而基座本身一个都用不到；需要的话由应用在自己的 ``core`` 目录里实现。
"""

from .storage import StoreError as StoreError
from .storage import read_json as read_json
from .storage import read_text as read_text
from .storage import write_json as write_json
from .storage import write_text as write_text

__all__ = [
    "StoreError",
    "read_json",
    "read_text",
    "write_json",
    "write_text",
]
