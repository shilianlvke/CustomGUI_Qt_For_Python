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

优先使用显式配置入口 ``customgui.configure(...)``；环境变量仅在未显式
指定时作为兜底，因此调用顺序不再是硬性要求。
"""

from __future__ import annotations

import os
from pathlib import Path

from customgui import package_root
from customgui import resource_root as _package_resource_root


def _cfg():
    """延迟导入，避免 customgui 包初始化期形成循环。"""
    from customgui.config import current_config

    return current_config()

_ROOT_ENV = "CUSTOMGUI_ROOT_DIR"
_APPS_ENV = "CUSTOMGUI_APPS_DIR"
_RESOURCE_ENV = "CUSTOMGUI_RESOURCE_DIR"
_DATA_ENV = "CUSTOMGUI_DATA_DIR"


def _env_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def resource_root() -> Path:
    """返回基座包内只读默认资源根（其下直接是 ``customui/``）。"""
    return _package_resource_root().resolve()


def resource_roots() -> list[Path]:
    """按优先级返回资源根目录（统一到"其下有 ``customui/``"这一层）。

    两种布局都接受，调用方只写 ``customui/themes`` 这类**相对资源根**的路径：

    - 基座包内：``customgui/_resources/customui/...``
    - 应用覆盖：``<root>/resource/customui/...``（PyCL2 等把 ``resource/`` 放在工程根）

    因此覆盖目录��有 ``<root>/resource`` 时自动下沉一级，让两种根的语义对齐。
    """
    roots: list[Path] = []
    for candidate in (*_cfg().resolved_resource_dirs(), _env_path(_RESOURCE_ENV), _env_path(_ROOT_ENV)):
        if candidate is None:
            continue
        nested = candidate / "resource"
        resolved = nested if nested.is_dir() else candidate
        if resolved not in roots:
            roots.append(resolved)
    roots.append(resource_root())
    return roots


def _normalize_relative(path: str | Path) -> Path:
    """把历史调用点传的 ``resource/customui/...`` 归一成 ``customui/...``。

    ``resource/`` 只是应用侧覆盖根的目录名，不该出现在解析路径里；
    这里做一次兼容剥除，调用点可以逐步改掉。
    """
    relative = Path(path)
    if relative.parts and relative.parts[0] == "resource":
        return Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path(".")
    return relative


def project_root() -> Path:
    """返回当前项目的根目录（环境变量优先，否则取基座仓库根）。"""
    custom_root = _env_path(_ROOT_ENV)
    if custom_root:
        return custom_root
    return resource_root().parent


def apps_root() -> Path:
    """返回应用模组目录（``configure(apps_dir=...)`` / ``CUSTOMGUI_APPS_DIR`` 优先）。

    未显式配置时按「由近及远」探测，第一个存在的目录胜出：

    1. 环境变量 ``CUSTOMGUI_APPS_DIR``
    2. ``data_root()/apps`` —— 用户运行 ``customgui install-demo`` 的落地位置
    3. ``<仓库根>/apps`` / ``<src>/apps`` / ``<包>/apps``（存在即用）
    4. 兜底返回仓库根 ``apps/``（可能不存在，调用方自行判断空目录）

    注意：src layout 下 ``package_root()`` 是 ``src/customgui``，
    它的上两级才是仓库根，所以探测表里要带上 ``parent.parent``。
    """
    configured = _cfg().resolved_apps_dir()
    if configured is not None:
        return configured
    custom_apps = _env_path(_APPS_ENV)
    if custom_apps:
        return custom_apps

    candidates = [
        data_root() / "apps",
        package_root().parent.parent / "apps",
        package_root().parent / "apps",
        package_root() / "apps",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return package_root().parent.parent / "apps"


def data_root() -> Path:
    """返回可写数据根目录，绝不写入安装目录。"""
    resolved = _cfg().resolved_data_dir()
    if resolved is not None:
        return resolved
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
    relative = _normalize_relative(candidate)
    for root in resource_roots():
        target = (root / relative).resolve()
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
    return (resource_root() / _normalize_relative(candidate)).resolve()


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

    relative = _normalize_relative(base)
    seen: dict[str, Path] = {}
    for root in resource_roots():
        directory_path = root / relative
        if not directory_path.is_dir():
            continue
        for path in directory_path.rglob(f"*{pattern}"):
            if not path.is_file():
                continue
            key = path.relative_to(directory_path).as_posix()
            seen.setdefault(key, path.resolve())
    return sorted(seen.values(), key=lambda path: path.as_posix())
