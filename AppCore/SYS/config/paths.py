"""项目根路径解析（独立于当前工作目录）。

配置加载始终以「项目根目录」为锚点，不依赖 ``os.getcwd``，
保证从任意工作目录启动（或打包运行）时配置路径稳定。

可通过环境变量 ``CUSTOMGUI_ROOT_DIR`` 覆盖项目根目录。
"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT_ENV = "CUSTOMGUI_ROOT_DIR"
_APPS_ENV = "CUSTOMGUI_APPS_DIR"


def project_root() -> Path:
    """返回项目根目录（环境变量优先，否则按包位置推导）。"""
    custom_root = os.getenv(_ROOT_ENV, "").strip()
    if custom_root:
        return Path(custom_root).expanduser().resolve()
    # AppCore/SYS/config/paths.py -> parents: config, SYS, AppCore, root
    return Path(__file__).resolve().parents[3]


def apps_root() -> Path:
    """返回 Apps 应用模组目录（环境变量 CUSTOMGUI_APPS_DIR 优先）。"""
    custom_apps = os.getenv(_APPS_ENV, "").strip()
    if custom_apps:
        return Path(custom_apps).expanduser().resolve()
    return project_root() / "Apps"


def resolve_path(path: str | Path) -> Path:
    """将相对路径解析为项目根目录下的绝对路径；绝对路径原样返回。"""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (project_root() / candidate).resolve()


def iter_files(directory: str | Path, suffix: str) -> list[Path]:
    """递归收集目录下指定后缀的文件（按路径排序，保证顺序稳定）。"""
    pattern = suffix if suffix.startswith(".") else f".{suffix}"
    base = resolve_path(directory)
    if not base.is_dir():
        return []
    return sorted(path.resolve() for path in base.rglob(f"*{pattern}") if path.is_file())
