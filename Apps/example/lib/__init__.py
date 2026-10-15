"""示例应用自定义逻辑目录（lib）。

约定：lib/__init__.py 汇总导出本包公共 API，
gui/main.py 通过 ``from ..lib import add, sub`` 使用。
"""

from .test import add, sub

__all__ = ["add", "sub"]
