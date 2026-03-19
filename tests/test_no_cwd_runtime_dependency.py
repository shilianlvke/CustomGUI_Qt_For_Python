import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = ["AppCore", "GUI", "GuiCore"]
RUNTIME_FILES = ["main.py"]


def _iter_runtime_files():
    for rel in RUNTIME_DIRS:
        base = ROOT / rel
        for path in base.rglob("*.py"):
            yield path
    for rel in RUNTIME_FILES:
        path = ROOT / rel
        if path.exists():
            yield path


def test_runtime_code_must_not_use_os_getcwd():
    violations = []

    for file_path in _iter_runtime_files():
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                if any(alias.name == "getcwd" for alias in node.names):
                    violations.append(f"{file_path.relative_to(ROOT).as_posix()} -> from os import getcwd")

            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "os" and func.attr == "getcwd":
                        violations.append(f"{file_path.relative_to(ROOT).as_posix()} -> os.getcwd()")
                elif isinstance(func, ast.Name) and func.id == "getcwd":
                    violations.append(f"{file_path.relative_to(ROOT).as_posix()} -> getcwd()")

    assert not violations, "Runtime code must not depend on os.getcwd:\n" + "\n".join(violations)
