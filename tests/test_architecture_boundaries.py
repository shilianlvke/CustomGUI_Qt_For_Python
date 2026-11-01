"""架构边界守卫：用 AST 扫描 import 根，防止分层依赖被悄悄破坏。

> 注意：src layout 下运行时包在 ``src/customgui``，这里的路径必须跟着走，
> 否则 ``rglob`` 会扫空、断言永远通过（假绿）。
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "customgui"


def _iter_python_files(*folders: Path):
    for base in folders:
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def _extract_import_roots(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imports.append(node.module)
    return imports


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def test_appcore_does_not_depend_on_presentation_layers():
    violations = []
    for path in _iter_python_files(SRC / "appcore"):
        for module in _extract_import_roots(path):
            if _matches(module, "customgui.guis") or _matches(module, "customgui.guicore"):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module}")

    assert not violations, "customgui.appcore must not import presentation layers:\n" + "\n".join(violations)


def test_guicore_does_not_depend_on_guis():
    """层级倒挂守卫：guicore 更底层，不得反向依赖 guis 的装配层。"""
    violations = []
    for path in _iter_python_files(SRC / "guicore"):
        for module in _extract_import_roots(path):
            if _matches(module, "customgui.guis"):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module}")

    assert not violations, "customgui.guicore must not import customgui.guis:\n" + "\n".join(violations)


def test_presentation_layer_uses_appcore_public_api_only():
    violations = []
    for path in _iter_python_files(SRC / "guis", SRC / "guicore"):
        for module in _extract_import_roots(path):
            if _matches(module, "customgui.appcore.sysx"):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module}")

    assert not violations, "Presentation code must not import appcore internals:\n" + "\n".join(violations)


def test_fake_app_namespace_is_private():
    """应用模组的伪造命名空间必须带下划线（私有、不构成公开契约）。

    允许 ``_customgui_apps``（私有），禁止裸 ``customgui_apps``（旧名）。
    """
    import re

    forbidden = re.compile(r"(?<![_A-Za-z])customgui_apps\b")
    violations = []
    for path in _iter_python_files(SRC, ROOT / "tests", ROOT / "apps", ROOT / "examples", ROOT / "scripts"):
        if path.name == "test_architecture_boundaries.py":
            continue  # 本文件自身定义了模式字符串
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and forbidden.search(node.value):
                violations.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: {node.value[:60]!r}")

    assert not violations, "Legacy fake package name 'customgui_apps' is not allowed:\n" + "\n".join(violations)


def test_no_dunder_file_parents_depth():
    """禁止 ``Path(__file__).resolve().parents[N]``（N >= 2）。

    源码运行、wheel 安装、PyInstaller 收集三种形态的目录深度各不相同，
    按层数回溯路径是最隐蔽的「装完就崩」来源。资源定位一律走
    ``customgui.config.paths``。
    """
    violations = []
    for path in _iter_python_files(SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            value = node.value
            if not (isinstance(value, ast.Attribute) and value.attr == "parents"):
                continue
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, int) and index.value >= 2:
                violations.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: parents[{index.value}]")

    assert not violations, "Use resource resolution helpers instead of parents[N]:\n" + "\n".join(violations)
