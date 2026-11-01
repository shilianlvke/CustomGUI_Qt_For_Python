"""CustomGUI —— 基于 PySide6 的开源 UI 基座。

包结构（一个顶层包，四个子包）：:

    customgui.appcore    逻辑层：配置、主题/语言/令牌、插件协议、错误边界、工具
    customgui.guicore    UI 组件与全局样式（设计令牌驱动）
    customgui.guis       窗口装配：主窗口、页面栈、插件加载、语言服务
    customgui._resources 只读默认资源（主题/语言/图标/设置）

对外稳定面：``configure()`` / ``get_app_context()`` / ``create_application()`` /
``run()`` / ``install_demo_apps()``，以及 ``customgui.window`` 门面。
"""

from __future__ import annotations

from pathlib import Path


def _read_version() -> str:
    """单一来源：优先读已安装包的元数据，源码运行时回落到 ``_version.py``。"""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover
        PackageNotFoundError = Exception  # type: ignore[assignment,misc]
        version = None  # type: ignore[assignment]

    if version is not None:
        try:
            return version("customgui")
        except PackageNotFoundError:
            pass
    from ._version import __version__ as fallback

    return fallback


__version__ = _read_version()

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = PACKAGE_ROOT / "_resources"


def resource_root() -> Path:
    """返回基座只读默认资源根目录（其下为 ``resource/``）。"""
    return RESOURCE_ROOT


def package_root() -> Path:
    """返回 ``customgui`` 包目录。"""
    return PACKAGE_ROOT


from .config import AppConfig, ConfigAlreadyLoadedError, configure, current_config, reset_config

__all__ = [
    "AppConfig",
    "ConfigAlreadyLoadedError",
    "PACKAGE_ROOT",
    "RESOURCE_ROOT",
    "configure",
    "current_config",
    "package_root",
    "reset_config",
    "resource_root",
    "__version__",
]
