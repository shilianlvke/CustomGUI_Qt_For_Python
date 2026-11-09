"""资源、应用与数据目录解析（独立于当前工作目录）。

默认资源来自可安装的 ``sllkgui`` 包，因此基座从任意目录运行、以 wheel
安装或由 PyInstaller 收集后都能找到主题/语言/图标。

应用可以通过环境变量叠加自己的资源（前面的优先）：

``SLLKGUI_RESOURCE_DIR``
    包含 ``resource/`` 的覆盖根目录。例如 PyCL2 仓库根目录。
``SLLKGUI_ROOT_DIR``
    兼容旧版本的覆盖根目录，同样按其中的 ``resource/`` 查找。
``SLLKGUI_APPS_DIR``
    应用插件目录，默认是当前项目的 ``Apps/``。
``SLLKGUI_DATA_DIR``
    可写数据根目录（日志、遥测、用户配置），默认程序运行根目录。

优先使用显式配置入口 ``sllkgui.configure(...)``；环境变量仅在未显式
指定时作为兜底，因此调用顺序不再是硬性要求。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sllkgui import package_root
from sllkgui import resource_root as _package_resource_root


def _cfg():
    """延迟导入，避免 sllkgui 包初始化期形成循环。"""
    from sllkgui.config import current_config

    return current_config()

_ROOT_ENV = "SLLKGUI_ROOT_DIR"
_APPS_ENV = "SLLKGUI_APPS_DIR"
_RESOURCE_ENV = "SLLKGUI_RESOURCE_DIR"
_DATA_ENV = "SLLKGUI_DATA_DIR"


def _env_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def resource_root() -> Path:
    """返回基座包内只读默认资源根（其下直接是 ``sllkgui/``）。"""
    return _package_resource_root().resolve()


def _app_overlay_roots() -> list[Path]:
    """各应用自带的品牌覆盖层（``<app>/brand``，其下直接是 ``sllkgui/``）。

    为什么要有这一层
    ----------------
    应用不该把自己的主题/语言/图标塞进**项目根**的 ``resource/``——那会让
    应用仓库根目录被基座资源污染，且必须先于基座导入配好环境变量。改成
    「资产跟着插件走」：``apps/<app>/brand/sllkgui/...``，基座扫描
    ``apps_dir`` 时自动纳入解析链，应用侧零配置。

    只做**文件判断**，不 import 任何应用代码，因此不会产生循环依赖；
    只有真的存在 ``brand/sllkgui/`` 的目录才会被当作资源根——这一点很
    重要：``<app>/sllkgui`` 直接当根会让 ``sllkgui/themes`` 拼成
    ``sllkgui/sllkgui/themes``（多一层），只有 ``<app>/brand`` 这一层
    才是「其下直接是 ``sllkgui/``」的正确语义。
    """
    try:
        base = apps_root()
    except Exception:
        return []
    if not base.is_dir():
        return []
    overlays: list[Path] = []
    try:
        children = sorted(base.iterdir())
    except OSError:
        return []
    for child in children:
        if not child.is_dir():
            continue
        brand = child / "brand"
        if (brand / "sllkgui").is_dir():
            overlays.append(brand)
    return overlays


def _configured_roots() -> list[Path]:
    """显式配置 + 环境变量给出的资源根（未追加品牌层与基座包内）。"""
    roots: list[Path] = []
    for candidate in (*_cfg().resolved_resource_dirs(), _env_path(_RESOURCE_ENV), _env_path(_ROOT_ENV)):
        if candidate is None:
            continue
        nested = candidate / "resource"
        resolved = nested if nested.is_dir() else candidate
        if resolved not in roots:
            roots.append(resolved)
    return roots


def resource_roots() -> list[Path]:
    """按优先级返回资源根目录（统一到"其下有 ``sllkgui/``"这一层）。

    三种布局都接受，调用方只写 ``sllkgui/themes`` 这类**相对资源根**的路径：

    - 基座包内：``sllkgui/_resources/sllkgui/...``
    - 应用覆盖：``<root>/resource/sllkgui/...``（历史布局，仍兼容）
    - 应用品牌层：``<apps_dir>/<app>/brand/sllkgui/...``（推荐）

    覆盖目录里若有 ``<root>/resource`` 时自动下沉一级，让几种根的语义对齐。

    解析顺序：显式 ``configure()`` / 环境变量 → 各应用品牌层 → 基座包内。
    品牌层排在基座之前，才能覆盖基座默认的主题与图标。
    """
    roots: list[Path] = list(_configured_roots())
    for overlay in _app_overlay_roots():
        resolved = overlay.resolve()
        if resolved not in roots:
            roots.append(resolved)
    roots.append(resource_root())
    return roots


def _normalize_relative(path: str | Path) -> Path:
    """把历史调用点传的 ``resource/sllkgui/...`` 归一成 ``sllkgui/...``。

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


def source_root() -> Path | None:
    """返回**源码树**的仓库根，wheel / PyInstaller 形态下返回 ``None``。

    判定方式刻意用「上一级是否有 ``pyproject.toml``」而不是目录深度：源码树
    与安装形态的层级不同，按层数回溯是最隐蔽的「装完就崩」来源（见
    ``tests/test_architecture_boundaries.py`` 的 ``parents[N]`` 守卫）。

    源码树独有 ``apps/`` 与 ``examples/``（wheel 里它们被 ``force-include``
    复制进包内），``sllkgui install-demo`` / ``sllkgui examples`` 需要
    在这里回落，否则源码用户会被告知「安装包里没有内置示例」。
    """
    candidate = package_root().parent.parent
    return candidate if (candidate / "pyproject.toml").is_file() else None


def apps_root() -> Path:
    """返回应用模组目录（``configure(apps_dir=...)`` / ``SLLKGUI_APPS_DIR`` 优先）。

    未显式配置时按「由近及远」探测，第一个存在的目录胜出：

    1. 环境变量 ``SLLKGUI_APPS_DIR``
    2. ``data_root()/apps`` —— 用户运行 ``sllkgui install-demo`` 的落地位置
    3. ``<仓库根>/apps`` / ``<src>/apps`` / ``<包>/apps``（存在即用）
    4. 兜底返回仓库根 ``apps/``（可能不存在，调用方自行判断空目录）

    注意：src layout 下 ``package_root()`` 是 ``src/sllkgui``，
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


def program_root() -> Path:
    """返回程序运行根目录（运行期配置与日志的默认落点）。

    解析顺序：

    1. 环境变量 ``SLLKGUI_PROGRAM_DIR``（便携/测试显式指定）；
    2. 源码树仓库根（``src`` 的上一级存在 ``pyproject.toml``）；
    3. PyInstaller 等冻结形态：可执行文件所在目录；
    4. 其它安装形态：可执行文件所在目录（与冻结分支一致，稳定可写、与 cwd 无关）。

    与 :func:`resource_root`（只读默认资源）区分：这里专门用于**可写**的
    运行期数据，避免落到 ``%APPDATA%`` 等用户系统目录。
    """
    override = _env_path("SLLKGUI_PROGRAM_DIR")
    if override is not None:
        return override
    source = source_root()
    if source is not None:
        return source
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(sys.executable).resolve().parent


def data_root() -> Path:
    """返回可写数据根目录。

    显式 ``configure(data_dir=...)`` 或 ``SLLKGUI_DATA_DIR`` 优先；
    均未提供时落到 :func:`program_root`，不再默认写入用户系统目录。
    """
    resolved = _cfg().resolved_data_dir()
    if resolved is not None:
        return resolved
    custom_data = _env_path(_DATA_ENV)
    if custom_data:
        return custom_data
    return program_root()


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


def iter_file_layers(directory: str | Path, suffix: str) -> dict[str, tuple[Path, ...]]:
    """按文件名分组返回**每一层**的同名文件，组内顺序为「低优先级 -> 高优先级」。

    为什么需要它
    ------------
    ``iter_files()`` 的语义是「同名只留高优先级那份」，这对「发现有哪些文件」
    够用，但对**配置**是错的：应用的品牌层只写 ``window.yaml`` 里的三五个键，
    整份替换会让基座那份文件里其余键全部消失。基座版本一升级、``AppSettings``
    新增必填字段，下游就会在启动时崩在配置校验上——而这个崩法完全看不出是
    覆盖层造成的。

    所以配置装载必须拿到全部层，按顺序 :func:`deep_merge`：低优先级打底，
    高优先级逐键覆盖，未覆盖的键继续由基座提供。键是「相对资源根的路径」
    （含子目录），因此 ``settings/`` 下嵌套目录也能正确分层。

    Args:
        directory: 资源根下的相对目录（如 ``"resource/sllkgui/settings"``），
            或一个绝对目录（此时只有一层，组内就是一个文件）。
        suffix: 文件后缀，``".yaml"`` 与 ``"yaml"`` 等价。

    Returns:
        ``{相对路径: (低优先级文件, ..., 最高优先级文件)}``。目录不存在时返回空字典。
    """
    pattern = suffix if suffix.startswith(".") else f".{suffix}"
    base = Path(directory)
    layers: dict[str, list[Path]] = {}

    if base.is_absolute():
        if not base.is_dir():
            return {}
        for path in sorted(base.rglob(f"*{pattern}")):
            if not path.is_file():
                continue
            key = path.relative_to(base).as_posix()
            layers.setdefault(key, []).append(path.resolve())
        return {key: tuple(paths) for key, paths in layers.items()}

    relative = _normalize_relative(base)
    # resource_roots() 是「高 -> 低」优先级；反着收，组内顺序才是
    # 「基座 -> 品牌层」，调用方顺序 deep_merge 即可让覆盖生效。
    for root in reversed(resource_roots()):
        directory_path = root / relative
        if not directory_path.is_dir():
            continue
        for path in directory_path.rglob(f"*{pattern}"):
            if not path.is_file():
                continue
            key = path.relative_to(directory_path).as_posix()
            layers.setdefault(key, []).append(path.resolve())
    return {key: tuple(paths) for key, paths in layers.items()}


def iter_files(directory: str | Path, suffix: str) -> list[Path]:
    """列出目录中的文件，同名文件只保留高优先级版本。

    适合「有哪些主题/语言/图标」这类**发现**用途，以及存在性判断。

    注意：它**不能**用来装载配置——被覆盖层挡住的基座文件不会出现在结果里。
    配置请用 :func:`iter_file_layers()` 拿全部层再逐层合并（见
    :meth:`sllkgui.appcore.sysx.config.registry.ConfigRegistry.load_settings`）。
    """
    layers = iter_file_layers(directory, suffix)
    return sorted((paths[-1] for paths in layers.values()), key=lambda path: path.as_posix())
