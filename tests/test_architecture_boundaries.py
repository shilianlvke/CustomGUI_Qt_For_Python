import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _iter_python_files(folder: str):
    """函数：_iter_python_files。

    参数:
    - 按函数签名传入。

    返回:
    - 按函数实现返回。
    """
    base = ROOT / folder
    for path in base.rglob("*.py"):
        yield path


def _extract_import_roots(file_path: Path) -> list[str]:
    "函数：_extract_import_roots。"
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


def test_appcore_does_not_depend_on_presentation_layers():
    "测试用例：test_appcore_does_not_depend_on_presentation_layers。"
    violations = []
    for path in _iter_python_files("AppCore"):
        for module in _extract_import_roots(path):
            if module == "GUI" or module.startswith("GUI.") or module == "GuiCore" or module.startswith("GuiCore."):
                rel = path.relative_to(ROOT).as_posix()
                violations.append(f"{rel} -> {module}")

    assert not violations, "AppCore must not import GUI/GuiCore:\n" + "\n".join(violations)


def test_presentation_layer_uses_appcore_public_api_only():
    "测试用例：test_presentation_layer_uses_appcore_public_api_only。"
    violations = []
    targets = ["GUI", "GuiCore"]

    for folder in targets:
        for path in _iter_python_files(folder):
            for module in _extract_import_roots(path):
                if module == "AppCore.SYS" or module.startswith("AppCore.SYS."):
                    rel = path.relative_to(ROOT).as_posix()
                    violations.append(f"{rel} -> {module}")

    assert not violations, "Presentation code must not import AppCore.SYS internals:\n" + "\n".join(violations)

