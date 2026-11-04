"""CustomGUI —— 基于 PySide6 的开源 UI 基座。

包结构（一个顶层包，四个子包）：:

    customgui.appcore    逻辑层：配置、主题/语言/令牌、插件协议、错误边界、工具
    customgui.guicore    UI 组件与全局样式（设计令牌驱动）
    customgui.guis       窗口装配：主窗口、页面栈、插件加载、语言服务
    customgui._resources 只读默认资源（主题/语言/图标/设置）

对外稳定面：``configure()`` / ``current_config()`` / ``reset_config()`` / ``__version__``，
以及 ``customgui.appcore``、``customgui.window`` 两个门面。
"""

from __future__ import annotations

from pathlib import Path

from . import _version


def _read_version() -> str:
    """版本以 ``_version.py`` 为**唯一来源**，缺失时才回落到已安装元数据。

    顺序不能反：以前优先读 ``importlib.metadata``，结果是源码树里改了
    ``_version.py``（或 ``git tag`` 已到 0.6.0）却还显示装进 site-packages
    那个旧 wheel 的版本号，``doctor`` 与 ``CHANGELOG`` 对不上。
    ``_version.py`` 会随包一起分发，因此 wheel 形态下两种来源本来就一致。
    """
    source_version = getattr(_version, "__version__", "")
    if source_version:
        return str(source_version)

    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - 3.8+ 一定有
        return "0.0.0"

    try:
        return version("customgui")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _read_version()

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = PACKAGE_ROOT / "_resources"


def resource_root() -> Path:
    """返回基座只读默认资源根目录（其下为 ``resource/``）。"""
    return RESOURCE_ROOT


def package_root() -> Path:
    """返回 ``customgui`` 包目录。"""
    return PACKAGE_ROOT


# 配置 API 放在函数定义之后导入：config 模块会延迟 import appcore，
# 放在这里可以避免包初始化期出现半初始化模块。
from .config import AppConfig, ConfigAlreadyLoadedError, configure, current_config, reset_config  # noqa: E402

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
