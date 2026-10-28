"""CustomGUI 基座包。

该包只负责携带基座版本信息和只读默认资源；可复用的 Python 代码仍由
``AppCore``、``GuiCore``、``Guis`` 顶层包提供，以兼容现有应用代码。
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.2.1"

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = PACKAGE_ROOT


def resource_root() -> Path:
    """返回基座只读默认资源根目录。"""
    return RESOURCE_ROOT


def package_root() -> Path:
    return PACKAGE_ROOT


__all__ = ["PACKAGE_ROOT", "RESOURCE_ROOT", "package_root", "resource_root", "__version__"]
