"""资源、应用与数据目录解析（独立于当前工作目录）。

默认资源来自可安装的 ``customgui`` 包，因此基座从任意目录运行、以 wheel
安装或由 PyInstaller 收集后都能找到主题/语言/图标。

应用可以通过环境变量叠加自己的资源（前面的优先）：

``CUSTOMGUI_RESOURCE_DIR``
    包含 ``resource/`` 的覆盖根目录。例如 PyCL2 仓库根目录。
``CUSTOMGUI_ROOT_DIR``
    兼容旧版本的覆盖根目录，同样按其中的 ``resource/`` 查找。
``CUSTOMGUI_APPS_DIR``
    应用插件目录，默认是当前项目的 ``Apps/``。
``CUSTOMGUI_DATA_DIR``
    可写数据根目录（日志、遥测），默认 ``%APPDATA%/CustomGUI``。
"""

from __future__ import annotations

import os
from pathlib import Path

from customgui import resource_root as _package_resource_root

_ROOT_ENV = "CUSTOMGUI_ROOT_DIR"
_APPS_ENV = "CUSTOMGUI_APPS_DIR"
_RESOURCE_ENV = "CUSTOMGUI_RESOURCE_DIR"
_DATA_ENV = "CUSTOMGUI_DATA_DIR"


def _env_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def resource_root() -> Path:
    """返回基座包内只读默认资源根（包含 ``resource/``）。"""
    return _package_resource_root().resolve()


def resource_roots() -> list[Path]:
    """按优先级返回资源根目录。

    每个根目录下都应存在 ``resource/...``。应用覆盖资源排在基座默认资源
    之前；路径解析与目录文件枚举都遵守这个顺序。
    """
    roots: list[Path] = []
    for candidate in (_env_path(_RESOURCE_ENV), _env_path(_ROOT_ENV), resource_root()):
        if candidate is not None and candidate not in roots:
            roots.append(candidate)
    return roots


def project_root() -> Path:
    """返回当前项目的根目录（环境变量优先，否则取基座仓库根）。"""
    custom_root = _env_path(_ROOT_ENV)
    if custom_root:
        return custom_root
    return resource_root().parent


def apps_root() -> Path:
    """返回 Apps 应用模组目录（环境变量 CUSTOMGUI_APPS_DIR 优先）。"""
    custom_apps = _env_path(_APPS_ENV)
    if custom_apps:
        return custom_apps
    return project_root() / "Apps"


def data_root() -> Path:
    """返回可写数据根目录，绝不写入安装目录。"""
    custom_data = _env_path(_DATA_ENV)
    if custom_data:
        return custom_data
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return Path(appdata).expanduser().resolve() / "CustomGUI"
    return Path.home() / ".customgui"


def find_resource(path: str | Path) -> Path | None:
    """在覆盖资源与基座默认资源中查找一个相对路径。"""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for root in resource_roots():
        target = (root / candidate).resolve()
        if target.exists():
            return target
    return None


def resolve_path(path: str | Path) -> Path:
    """将相对路径解析为绝对路径；覆盖资源不存在时回落到基座资源。

    绝对路径原样返回，方便测试和调用方显式指定临时目录。
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    found = find_resource(candidate)
    if found is not None:
        return found
    # 即使不存在也返回基座内的稳定位置，便于错误信息与写操作定位。
    return (resource_root() / candidate).resolve()


def iter_files(directory: str | Path, suffix: str) -> list[Path]:
    """按资源优先级合并目录中的文件，同名文件只保留高优先级版本。

    这允许应用只覆盖少数字体/主题/语言文件，其余文件仍由基座包提供。
    """
    pattern = suffix if suffix.startswith(".") else f".{suffix}"
    base = Path(directory)
    if base.is_absolute():
        if not base.is_dir():
            return []
        return sorted(path.resolve() for path in base.rglob(f"*{pattern}") if path.is_file())

    seen: dict[str, Path] = {}
    for root in resource_roots():
        directory_path = root / base
        if not directory_path.is_dir():
            continue
        for path in directory_path.rglob(f"*{pattern}"):
            if not path.is_file():
                continue
            relative = path.relative_to(directory_path).as_posix()
            seen.setdefault(relative, path.resolve())
    return sorted(seen.values(), key=lambda path: path.as_posix())
