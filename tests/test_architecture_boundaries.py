"""架构边界守卫：用 AST 扫 import 根，防止分层依赖被悄悄破坏。

> 注意：src layout 下运行时包在 ``src/sllkgui``，这里的路径必须跟着走，
> 否则 ``rglob`` 会扫空、断言永远通过（假绿）。

分层契约（3.0 起用 5×5 白名单矩阵表达）：

    appcore  ←  guicore  ←  guis  ←  gallery（组合根只有 gallery/window.py）
                                      ↖ showcase（内置插件，允许驱动窗口动画）

- ``gallery`` 只有在组合根 ``gallery/window.py`` 里可以 import ``guis``；
- ``guis`` / ``guicore`` 不得 import ``gallery``（插件注册表由窗口持有，鸭子类型读取）；
- ``appcore`` 不得 import 任何上层。
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sllkgui"

PACKAGES = ("appcore", "guicore", "guis", "gallery", "showcase")

#: 允许的包间依赖（行 = 源，列 = 目标）
ALLOWED_EDGES: dict[str, set[str]] = {
    "appcore": set(),
    "guicore": {"appcore"},
    "guis": {"appcore", "guicore"},
    "gallery": {"appcore", "guicore", "guis"},
    "showcase": {"appcore", "guicore", "guis"},
}

#: 边级白名单：只有这些文件可以使用该边
EDGE_ALLOWLIST: dict[tuple[str, str], set[str]] = {
    ("gallery", "guis"): {"gallery/window.py"},
}

#: 已知待清理的反向依赖：P3 删设置抽屉后此表必须为空（空表本身也由此测试守护）
PENDING_INVERSIONS: dict[tuple[str, str], set[str]] = {
    ("guicore", "gallery"): {
        "guicore/window/settings/sections.py",
        "guicore/window/left_column/settings_panel.py",
        "guicore/window/settings_window/window.py",
    },
}


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


def _is_type_checking(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    return isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING"


class _RuntimeImportCollector(ast.NodeVisitor):
    """收集运行期 import；``if TYPE_CHECKING:`` 里的导入不算依赖。"""

    def __init__(self) -> None:
        self.nodes: list[ast.Import | ast.ImportFrom] = []

    def visit_If(self, node: ast.If) -> None:  # noqa: N802 - ast 访问器命名
        if _is_type_checking(node.test):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        self.nodes.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        self.nodes.append(node)


def _extract_import_roots(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    collector = _RuntimeImportCollector()
    collector.visit(tree)

    imports: list[str] = []
    # FIX-05: 相对导入若被跳过，``from ..guis import x`` 之类写法即可绕过分层守卫。
    # 按 src layout 还原文件所属包，再把 level>0 的相对导入折算成绝对模块名。
    sub_parts = file_path.relative_to(SRC).parts[:-1]
    package = "sllkgui" + ("." + ".".join(sub_parts) if sub_parts else "")
    package_parts = package.split(".")

    for node in collector.nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif node.level == 0:
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


def _package_of(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "sllkgui":
        return None
    return parts[1] if parts[1] in PACKAGES else None


def _collect_edges() -> dict[tuple[str, str], list[str]]:
    edges: dict[tuple[str, str], list[str]] = {}
    for path in _iter_python_files(SRC):
        relative = path.relative_to(SRC)
        source = relative.parts[0] if relative.parts[0] in PACKAGES else None
        if source is None:
            continue
        for module in _extract_import_roots(path):
            target = _package_of(module)
            if target is None or target == source:
                continue
            edges.setdefault((source, target), []).append(
                f"{relative.as_posix()}:{module}"
            )
    return edges


def test_package_dependency_matrix():
    """5×5 白名单：出现未登记的边即失败，并直接指出文件与模块。"""
    violations: list[str] = []
    for (source, target), sites in sorted(_collect_edges().items()):
        if target in ALLOWED_EDGES[source]:
            files = EDGE_ALLOWLIST.get((source, target))
            if files is None:
                continue
            violations.extend(site for site in sites if site.split(":", 1)[0] not in files)
            continue
        pending = PENDING_INVERSIONS.get((source, target), set())
        violations.extend(site for site in sites if site.split(":", 1)[0] not in pending)
    assert not violations, (
        "Layering contract violated (source -> target):\n"
        + "\n".join(violations)
        + "\n允许的边："
        + repr({k: sorted(v) for k, v in ALLOWED_EDGES.items()})
    )


def test_pending_inversions_are_still_needed():
    """待清理表只能变小：里面的文件若已不再违规，必须从表中删除。"""
    edges = _collect_edges()
    for (source, target), files in PENDING_INVERSIONS.items():
        actual = {site.split(":", 1)[0] for site in edges.get((source, target), [])}
        stale = files - actual
        assert not stale, f"PENDING_INVERSIONS 已过期，请删除: {sorted(stale)}"


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
    for path in _iter_python_files(SRC, ROOT / "tests", ROOT / "examples", ROOT / "scripts"):
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
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AssertionError):
        list(_iter_python_files(empty))
