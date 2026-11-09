import ast
from pathlib import Path

from sllkgui.appcore.sysx.config.paths import program_root

ROOT = Path(__file__).resolve().parents[1]
# src layout：运行时包在 src/sllkgui 下，扫错路径会让断言永远通过。
RUNTIME_DIRS = [
    "src/sllkgui/appcore",
    "src/sllkgui/guis",
    "src/sllkgui/guicore",
]
RUNTIME_FILES = ["examples/hello_world/main.py"]


def _iter_runtime_files():
    found = False
    for rel in RUNTIME_DIRS:
        base = ROOT / rel
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            found = True
            yield path
    for rel in RUNTIME_FILES:
        path = ROOT / rel
        if path.exists():
            found = True
            yield path
    # 自检：一个文件都没扫到时必须报错，不能静默通过。
    assert found, "runtime 目录清单失效（路径不存在），请检查 src layout"


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
                    # FIX-05: Path.cwd() 同样是运行时 cwd 依赖，必须与 os.getcwd() 一并禁止。
                    if func.value.id == "Path" and func.attr == "cwd":
                        violations.append(f"{file_path.relative_to(ROOT).as_posix()} -> Path.cwd()")
                elif isinstance(func, ast.Name) and func.id == "getcwd":
                    violations.append(f"{file_path.relative_to(ROOT).as_posix()} -> getcwd()")

    assert not violations, "Runtime code must not depend on os.getcwd:\n" + "\n".join(violations)


def test_program_root_stable_without_data_dir(monkeypatch, tmp_path):
    """program_root() 在删除显式目录后仍与当前工作目录无关。"""
    # FIX-05: conftest 全局设了 SLLKGUI_DATA_DIR，不移除就测不到末级兜底分支。
    monkeypatch.delenv("SLLKGUI_DATA_DIR", raising=False)
    monkeypatch.delenv("SLLKGUI_PROGRAM_DIR", raising=False)

    before = program_root()
    monkeypatch.chdir(tmp_path)
    after = program_root()

    assert after == before, "program_root() must be stable across cwd changes"
    assert after != tmp_path.resolve(), "program_root() must not fall back to cwd"
