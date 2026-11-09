import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = ["src/sllkgui/appcore", "src/sllkgui/guis", "src/sllkgui/guicore"]
RUNTIME_FILES = ["examples/hello_world/main.py"]

LEGACY_IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.modules\.config_module\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.modules\.languge_module\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.modules\.settings_module\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.common\.folder_tools\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.common\.resource_locator\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.logger\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.locator\b"),
    re.compile(r"^\s*from\s+sllkgui.appcore\.sysx\.loader\b"),
    re.compile(r"^\s*from\s+sllkgui.guis\.windows\.loading_window\.ui_mian\b"),
    # 业务页面已迁移至 apps/ 目录，基座运行时代码不得再引用
    re.compile(r"^\s*from\s+sllkgui.guis\.windows\.main_window\.user_define_pages\.p2ptest\w*\b"),
    re.compile(r"^\s*from\s+sllkgui.guis\.windows\.main_window\.user_define_pages\b"),
    re.compile(r"^\s*from\s+\.p2ptest\w*\b"),
    re.compile(r"^\s*from\s+\.normal_widget_show\b"),
    re.compile(r"^\s*from\s+\.\.logger\b"),
    re.compile(r"^\s*from\s+\.logger\b"),
    re.compile(r"^\s*from\s+\.languge_module\b"),
    re.compile(r"^\s*from\s+\.ui_mian\b"),
    re.compile(r"^\s*from\s+\.settings_module\b"),
    re.compile(r"^\s*from\s+\.folder_tools\b"),
    re.compile(r"^\s*from\s+\.resource_locator\b"),
]

ALLOWED_FILES = {
    "src/sllkgui/appcore/sysx/modules/language_module.py",
    "src/sllkgui/guis/windows/loading_window/ui_main.py",
}


def _iter_runtime_files():
    found = False
    for rel in RUNTIME_DIRS:
        base = ROOT / rel
        for path in base.rglob("*.py"):
            found = True
            yield path
    for rel in RUNTIME_FILES:
        path = ROOT / rel
        if path.exists():
            found = True
            yield path
    # 自检：一个文件都没扫到时必须报错，不能静默通过。
    assert found, "runtime file scanner matched nothing (stale or empty directory list)"


def test_runtime_code_does_not_add_new_legacy_imports():
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
