import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = ["AppCore", "GUI", "GuiCore"]
RUNTIME_FILES = ["main.py"]

LEGACY_IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+AppCore\.SYS\.module\.config_module\b"),
    re.compile(r"^\s*from\s+AppCore\.SYS\.module\.languge_module\b"),
    re.compile(r"^\s*from\s+GUI\.windows\.loading_window\.ui_mian\b"),
    re.compile(r"^\s*from\s+\.languge_module\b"),
    re.compile(r"^\s*from\s+\.ui_mian\b"),
]

ALLOWED_FILES = {
    "AppCore/SYS/module/language_module.py",
    "GUI/windows/loading_window/ui_main.py",
}


def _iter_runtime_files():
    """函数：_iter_runtime_files。

    参数:
    - 按函数签名传入。

    返回:
    - 按函数实现返回。
    """
    for rel in RUNTIME_DIRS:
        base = ROOT / rel
        for path in base.rglob("*.py"):
            yield path
    for rel in RUNTIME_FILES:
        path = ROOT / rel
        if path.exists():
            yield path


def test_runtime_code_does_not_add_new_legacy_imports():
    "测试用例：test_runtime_code_does_not_add_new_legacy_imports。"
    violations = []

    for path in _iter_runtime_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_FILES:
            continue

        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in LEGACY_IMPORT_PATTERNS):
                violations.append(f"{rel}:{index}: {line.strip()}")

    assert not violations, "New legacy imports are not allowed:\n" + "\n".join(violations)

