"""应用容器模块的导入机制：伪造私有命名空间，让目录插件能按包导入。

``apps/<app>/`` 不在 ``sys.path`` 里，所以不能直接用包路径 import。这里用一个
**私有**命名空间伪造父包（下划线前缀，明确「非公开契约」），并装一个只在该
命名空间内生效的 Finder，把 ``<app>/<任意层级>`` 解析成真实包/模块。
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import ModuleType

from customgui.appcore import Logger, apps_root

#: 应用模组的模块命名空间（私有，消费方不应依赖）。
_APP_NAMESPACE = "_customgui_apps"

#: 应用名 -> 应用根目录。每个应用单独登记，避免多个 Apps 根互相串台。
_NAMESPACE_ROOTS: dict[str, str] = {}


def _ensure_parent_packages(module_name: str, app_dir: Path) -> None:
    """为应用主模块建立父包层级，使 App 内部相对导入可用。

    例：加载 ``_customgui_apps.example.gui.main`` 时建立：

    - ``_customgui_apps``：__path__ = Apps 根目录，并安装一个只在该命名空间内
      生效的 MetaPathFinder，负责把 ``<app>/xxx`` 目录按包加载；
    - ``_customgui_apps.example``：__path__ = 应用目录（由此支持
      ``from .lib import ...`` 等自定义逻辑目录的常规导入）；
    - ``_customgui_apps.example.gui``：__path__ = gui 子目录。

    应用内的子模块（如 ``lib/__init__.py``）由 Python 常规导入机制按
    ``__path__`` 自动发现；跨目录的相对导入（``lib/__init__.py`` 里的
    ``from ..calc import add``）则需要 Finder 才能定位到 ``<app>/calc.py``。
    """
    parts = module_name.split(".")
    app_name = parts[1]
    # key 必须与模块名一致（只用 app_name），否则 Finder 查不到根目录、
    # 应用内部的跨目录相对导入会静默失效。清单校验保证 app_name == 目录名，
    # 这里再按模块名兜一次底。
    _NAMESPACE_ROOTS[app_name] = str(app_dir)
    _install_namespace_finder()

    for index in range(len(parts) - 1):
        package_name = ".".join(parts[: index + 1])
        # 已存在的包也需更新 __path__（同名 App 目录可能变化，如测试注入）
        package = sys.modules.get(package_name) or types.ModuleType(package_name)
        if index == 0:
            # 命名空间根 -> Apps 根目录
            package.__path__ = [str(apps_root())]
        elif index == 1:
            # <ns>.<app_name> -> 应用目录
            package.__path__ = [str(app_dir)]
        else:
            # <ns>.<app_name>.<子包> -> 应用内同名子目录
            sub_dir = app_dir.joinpath(*parts[2 : index + 1])
            package.__path__ = [str(sub_dir)]
        sys.modules[package_name] = package

    # 确保模块名中的应用名与目录名一致（防御：加载器始终按目录名生成）
    if parts[1] != app_dir.name:
        Logger.warning(f"应用模块名与目录名不一致: {module_name} vs {app_dir.name}")


def _install_namespace_finder() -> None:
    """安装伪命名空间 Finder（全局唯一）。"""
    if not any(isinstance(finder, _NamespacePackageFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _NamespacePackageFinder())


class _NamespacePackageFinder:
    """把 ``<ns>.<app>.<任何层级>`` 解析成该应用目录下的真实包/模块。

    ``sys.modules`` 只预置了 ``gui`` 这一条链路，应用里其余目录（``lib``、
    ``LauncherCore`` 等）必须由 Finder 兜住，否则应用内部的跨目录相对导入
    （``from ..calc import add``）会找不到模块。

    每个应用名对应的根目录单独登记，避免多个 Apps 根（仓库 demo 与
    用户目录）互相串台。
    """

    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001 - importlib 协议
        if not fullname.startswith(f"{_APP_NAMESPACE}."):
            return None
        parts = fullname[len(_APP_NAMESPACE) + 1 :].split(".")
        if len(parts) < 2:
            return None
        root = _NAMESPACE_ROOTS.get(parts[0])
        if root is None:
            return None
        candidate = Path(root).joinpath(*parts[1:])
        if candidate.is_dir():
            init = candidate / "__init__.py"
            return importlib.util.spec_from_file_location(
                fullname,
                init,
                submodule_search_locations=[str(candidate)],
            )
        module_file = candidate.with_suffix(".py")
        if module_file.is_file():
            return importlib.util.spec_from_file_location(fullname, module_file)
        return None


def _import_app_module(module_name: str, app_dir: Path, file_path: Path) -> ModuleType:
    _ensure_parent_packages(module_name, app_dir)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载应用模块: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


__all__ = ["_APP_NAMESPACE"]
