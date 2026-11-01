"""CustomGUI 基座包。

该包只负责携带基座版本信息和只读默认资源；可复用的 Python 代码仍由
``AppCore``、``GuiCore``、``Guis`` 顶层包提供，以兼容现有应用代码。
"""

from __future__ import annotations

from pathlib import Path

def _read_version() -> str:
    """单一来源：优先读已安装包的元数据，源码运行时回落到 ``_version.py``。"""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover
        PackageNotFoundError = Exception
        version = None
    if version is not None:
        try:
            return version("customgui")
        except PackageNotFoundError:
            pass
    from ._version import __version__ as fallback

    return fallback


__version__ = _read_version()

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = PACKAGE_ROOT


def resource_root() -> Path:
    """返回基座只读默认资源根目录。"""
    return RESOURCE_ROOT


def package_root() -> Path:
    return PACKAGE_ROOT


__all__ = ["PACKAGE_ROOT", "RESOURCE_ROOT", "package_root", "resource_root", "__version__"]
