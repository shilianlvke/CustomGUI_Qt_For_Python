"""架构边界守卫：用 AST 扫描 import 根，防止分层依赖被悄悄破坏。

> 注意：src layout 下运行时包在 ``src/sllkgui``，这里的路径必须跟着走，
> 否则 ``rglob`` 会扫空、断言永远通过（假绿）。
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sllkgui"


def _iter_python_files(*folders: Path):
    found = False
    for base in folders:
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            found = True
            yield path
    # FIX-05: 一个文件都没扫到时必须报错，不能静默通过（防止 rglob 扫空造成假绿）。
    assert found, "Python file scanner matched nothing (stale or empty directory list)"


def _extract_import_roots(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imports: list[str] = []
    # FIX-05: 相对导入若被跳过，``from ..guis import x`` 之类写法即可绕过分层守卫。
    # 按 src layout 还原文件所属包，再把 level>0 的相对导入折算成绝对模块名
    # 纳入检查，确保「相对导入绕过守卫」不再成立。
    sub_parts = file_path.relative_to(SRC).parts[:-1]
    package = "sllkgui" + ("." + ".".join(sub_parts) if sub_parts else "")
    package_parts = package.split(".")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    imports.append(node.module)
            else:
                # 按 level 从当前包回溯到基准包，再拼上 node.module（可为空）。
                base = package_parts[: max(1, len(package_parts) - (node.level - 1))]
                resolved = ".".join(base) if node.module is None else ".".join(base) + "." + node.module
                imports.append(resolved)
    return imports


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def test_appcore_does_not_depend_on_presentation_layers():
    violations = []
    for path in _iter_python_files(SRC / "appcore"):
        for module in _extract_import_roots(path):
            if _matches(module, "sllkgui.guis") or _matches(module, "sllkgui.guicore"):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module}")

    assert not violations, "sllkgui.appcore must not import presentation layers:\n" + "\n".join(violations)


def test_guicore_does_not_depend_on_guis():
    """层级倒挂守卫：guicore 更底层，不得反向依赖 guis 的装配层。"""
    violations = []
    for path in _iter_python_files(SRC / "guicore"):
        for module in _extract_import_roots(path):
            if _matches(module, "sllkgui.guis"):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module}")

    assert not violations, "sllkgui.guicore must not import sllkgui.guis:\n" + "\n".join(violations)


def test_presentation_layer_uses_appcore_public_api_only():
    violations = []
    for path in _iter_python_files(SRC / "guis", SRC / "guicore"):
        for module in _extract_import_roots(path):
            if _matches(module, "sllkgui.appcore.sysx"):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module}")

    assert not violations, "Presentation code must not import appcore internals:\n" + "\n".join(violations)


def test_fake_app_namespace_is_private():
    """应用模组的伪造命名空间必须带下划线（私有、不构成公开契约）。

    允许 ``_sllkgui_apps``（私有），禁止裸 ``sllkgui_apps``（旧名）。
    """
    import re

    forbidden = re.compile(r"(?<![_A-Za-z])sllkgui_apps\b")
    violations = []
    for path in _iter_python_files(SRC, ROOT / "tests", ROOT / "apps", ROOT / "examples", ROOT / "scripts"):
        if path.name == "test_architecture_boundaries.py":
            continue  # 本文件自身定义了模式字符串
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and forbidden.search(node.value):
                violations.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: {node.value[:60]!r}")

    assert not violations, "Legacy fake package name 'sllkgui_apps' is not allowed:\n" + "\n".join(violations)


def test_no_dunder_file_parents_depth():
    """禁止 ``Path(__file__).resolve().parents[N]``（N >= 2）。

    源码运行、wheel 安装、PyInstaller 收集三种形态的目录深度各不相同，
    按层数回溯路径是最隐蔽的「装完就崩」来源。资源定位一律走
    ``sllkgui.config.paths``。
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


def test_python_file_scanner_rejects_empty_dir(tmp_path):
    """扫描器在空目录时必须失败，避免 rglob 扫空导致断言假绿。"""
    # FIX-05: 空目录应触发 found 自检 assert，而不是静默返回空结果。
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AssertionError):
        list(_iter_python_files(empty))
