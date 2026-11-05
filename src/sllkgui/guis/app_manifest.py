"""应用清单：发现目录、读取 config.yml、装载语言、解析图标与入口。

这一层只与磁盘打交道，不 import 任何应用代码、也不注册插件——注册在
``app_loader``，协议 v2 的翻译在 ``app_v2``。
"""

from __future__ import annotations

from pathlib import Path

from sllkgui.appcore import (
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    AppPluginError,
    Attrs,
    Language,
    Logger,
    YamlHandler,
    apps_root,
    to_attrs,
)

from . import app_state
from .app_namespace import _APP_NAMESPACE


def _absolute_dir(app_dir: str | Path) -> Path:
    """把应用目录统一成绝对路径。

    ``YamlHandler`` 内部走 :func:`resolve_path`，它把**相对路径当作资源相对路径**
    去各资源根里找——``Path("apps/demo/config.yml")`` 会被解析成
    ``<wheel>/sllkgui/apps/demo/config.yml``，读不到就抛 ``IOErrorBoundary``。
    用户在项目目录里敲 ``sllkgui run --apps-dir apps`` 时正好落进这个坑，
    表现是「应用目录里明明有应用，窗口却是空的」。
    """
    return Path(app_dir).expanduser().resolve()


def discover_app_dirs(root: str | Path | None = None) -> list[Path]:
    """扫描应用目录，返回全部含 ``config.yml`` 的子目录（按名称排序）。

    ``root`` 为相对路径时按**当前工作目录**解析（CLI 传入的 ``--apps-dir apps``
    就是这种用法），不是按资源根解析。
    """
    base = _absolute_dir(root) if root is not None else apps_root()
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir() and (path / "config.yml").is_file())


def load_app_manifest(app_dir: Path) -> Attrs:
    """读取应用的 config.yml 清单（``app_dir`` 可以是相对路径）。"""
    return YamlHandler(str(_absolute_dir(app_dir) / "config.yml")).data


def _load_app_lang_data(app_dir: Path, language: str) -> dict:
    """读取应用的语言文件（支持 .yml/.yaml），缺失时返回空字典。"""
    app_dir = _absolute_dir(app_dir)
    for suffix in (".yml", ".yaml"):
        lang_file = app_dir / "resource" / "lang" / f"{language}{suffix}"
        if lang_file.is_file():
            return YamlHandler(str(lang_file)).to_dict()
    return {}


def collect_app_languages(language: str, app_dirs: list[Path] | None = None) -> Attrs:
    """收集全部应用的语言数据，返回 {app_name: {key: text}} 命名空间。"""
    app_node = Attrs()
    for app_dir in app_dirs if app_dirs is not None else discover_app_dirs():
        data = _load_app_lang_data(app_dir, language)
        app_node[app_dir.name] = to_attrs(data)
    return app_node


def apply_apps_language(language: str, app_dirs: list[Path] | None = None) -> None:
    """把全部应用的语言文件注入 ``Language.app.<app_name>`` 命名空间。"""
    Language.app = collect_app_languages(language, app_dirs)
    Logger.debug(f"应用语言注入完成: {language}")


def _app_language_provider(language: str) -> dict:
    """供 Language.apply 使用的 App 语言提供者（复用已发现的目录）。"""
    return collect_app_languages(language, app_state.app_dirs or None)


# 注册 App 语言提供者：语言切换时由 LanguageManager 自动调用
Language.register_app_provider(_app_language_provider)


def _resolve_icon(config: Attrs, app_dir: Path) -> str:
    """解析应用图标：``icon.<ns>.<filename>`` 资源键 -> 应用内图标文件绝对路径。"""
    icon_ref = config.get("app_icon") or f"icon.app.{config.get('app_name') or app_dir.name}.app_icon"
    filename = str(icon_ref).split(".")[-1]
    icon_path = app_dir / "resource" / "icon" / f"{filename}.svg"
    if icon_path.is_file():
        return str(icon_path)
    # 回退：按基座内置图标名解析
    return str(icon_ref)


def _manifest_protocol(config: Attrs) -> str:
    """读清单声明的协议版本，缺省视为 v1（历史应用无此字段）。"""
    raw = config.get("protocol")
    version = str(raw).strip() if raw is not None else "1"
    if version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise AppPluginError(
            "APP_PROTOCOL_UNSUPPORTED",
            f"清单 protocol={version!r} 不受支持（可用: {sorted(SUPPORTED_PROTOCOL_VERSIONS)}）",
        )
    return version


def _resolve_entry(protocol: str, app_dir: Path, name: str) -> tuple[Path | None, str]:
    """解析应用的入口文件与对应模块名。

    返回 ``(file_path, module_name)``；找不到入口时返回 ``(None, "")``。

    - **v2**：优先 ``app.py``（应用根，插件入口），回退 ``gui/main.py``；
    - **v1**：``gui/main.py``（历史布局，保持兼容）。
    """
    candidates: list[tuple[Path, str]] = []
    if protocol == PROTOCOL_VERSION:
        candidates.append((app_dir / "app.py", f"{_APP_NAMESPACE}.{name}.app"))
    candidates.append((app_dir / "gui" / "main.py", f"{_APP_NAMESPACE}.{name}.gui.main"))
    for file_path, module_name in candidates:
        if file_path.is_file():
            return file_path, module_name
    return None, ""


def _check_core(config: Attrs, app_dir: Path) -> str | None:
    """校验清单 ``core`` 声明的逻辑层目录存在，返回目录名。"""
    raw = config.get("core")
    if raw is None:
        return None
    core_name = str(raw).strip()
    if not core_name:
        return None
    if not (app_dir / core_name).is_dir():
        raise AppPluginError(
            "APP_CORE_MISSING",
            f"清单声明 core={core_name!r}，但目录不存在: {app_dir / core_name}",
        )
    return core_name


def _check_name(config: Attrs, app_dir: Path) -> str:
    """清单 ``app_name`` 必须与目录名一致。

    不一致时命名空间 Finder 会用目录名登记、而模块名用 ``app_name``，
    导致应用内部 ``import`` 静默失效——宁可这里显式报错。
    """
    name = str(config.get("app_name") or app_dir.name).strip()
    if name != app_dir.name:
        raise AppPluginError(
            "APP_NAME_MISMATCH",
            f"清单 app_name={name!r} 与目录名 {app_dir.name!r} 不一致（会让应用内导入失效）",
        )
    return name


__all__ = [
    "apply_apps_language",
    "collect_app_languages",
    "discover_app_dirs",
    "load_app_manifest",
]
