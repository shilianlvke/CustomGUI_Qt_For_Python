#!/usr/bin/env python3
"""把旧顶层包名（sllkgui.appcore/sllkgui.guicore/sllkgui.guis）重写为 ``sllkgui.*`` 命名空间。

用法::

    python scripts/rewrite_imports.py --check     # 只报告，不写入
    python scripts/rewrite_imports.py             # 实际写入

设计要点：

1. 规则表按 key 长度降序匹配，避免 ``sllkgui.appcore`` 抢先匹配 ``sllkgui.appcore.sysx``；
2. 只处理 ``level == 0`` 的绝对导入，相对导入保持不动；
3. 按 AST 的 ``lineno/col_offset`` 定位后做**行内文本替换**，保留缩进、
   注释、``# noqa`` 与 ``as`` 别名——不使用 ``ast.unparse``，因为它会丢注释；
4. 只替换导入语句里的模块文本，字符串字面量里的包名需人工处理。
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_DIRS = ["src", "apps", "examples", "tests", "scripts"]

# 前缀规则：按 key 长度降序匹配
PREFIX_RULES: dict[str, str] = {
    "sllkgui.appcore.sysx.config": "sllkgui.appcore.sysx.config",
    "sllkgui.appcore.sysx.modules": "sllkgui.appcore.sysx.modules",
    "sllkgui.appcore.sysx.handlers": "sllkgui.appcore.sysx.handlers",
    "sllkgui.appcore.sysx.common": "sllkgui.appcore.sysx.common",
    "sllkgui.appcore.sysx": "sllkgui.appcore.sysx",
    "sllkgui.appcore.app": "sllkgui.appcore.app",
    "sllkgui.appcore.tool": "sllkgui.appcore.tool",
    "sllkgui.appcore": "sllkgui.appcore",
    "sllkgui.guicore.custom_ui": "sllkgui.guicore.custom_ui",
    "sllkgui.guicore.window": "sllkgui.guicore.window",
    "sllkgui.guicore.app_ui": "sllkgui.guicore.app_ui",
    "sllkgui.guicore": "sllkgui.guicore",
    "sllkgui.guis": "sllkgui.guis",
}

# 包内部的相对模块名也要跟着改（相对导入本身不动，但被导入的子模块名变了）
SUBMODULE_RULES: dict[tuple[str, str], str] = {
    # (旧包, 旧子模块前缀) -> 新子模块前缀；作用在 level>0 的相对导入上
    ("sllkgui.appcore", "SYS.module"): "sysx.modules",
    ("sllkgui.appcore", "SYS.config"): "sysx.config",
    ("sllkgui.appcore", "SYS.handler"): "sysx.handlers",
    ("sllkgui.appcore", "SYS.other"): "sysx.common",
    ("sllkgui.appcore", "SYS"): "sysx",
    ("sllkgui.appcore", "APP"): "app",
    ("sllkgui.appcore", "Tool"): "tool",
    ("sllkgui.guicore", "CustomUI"): "custom_ui",
    ("sllkgui.guicore", "WindowDefineUI"): "window",
    ("sllkgui.guicore", "AppDefineUI"): "app_ui",
}


def rewrite_module_name(name: str) -> str:
    for old in sorted(PREFIX_RULES, key=len, reverse=True):
        if name == old or name.startswith(old + "."):
            return PREFIX_RULES[old] + name[len(old):]
    return name


def rewrite_relative_target(module: str | None) -> str | None:
    if not module:
        return module
    for (_pkg, old), new in sorted(SUBMODULE_RULES.items(), key=lambda kv: len(kv[0][1]), reverse=True):
        if module == old or module.startswith(old + "."):
            return new + module[len(old):]
    return module


def process_file(path: Path, apply: bool) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        print(f"SKIP（语法错误）{path}: {exc}")
        return False

    lines = source.splitlines(keepends=True)
    edits: list[tuple[int, int, int, int, str]] = []
    # (start_lineno, start_col, end_lineno, end_col, replacement)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                new = rewrite_module_name(alias.name)
                if new != alias.name:
                    edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset,
                                  ast.unparse(_rebuild_import(node, {id(alias): new}))))
                    break
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.module:
                new = rewrite_relative_target(node.module)
                if new != node.module:
                    edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset,
                                  ast.unparse(_rebuild_import(node, module=new))))
            elif not node.level and node.module:
                new = rewrite_module_name(node.module)
                if new != node.module:
                    edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset,
                                  ast.unparse(_rebuild_import(node, module=new))))

    if not edits:
        return False

    print(f"{'WRITE' if apply else 'DRY  '} {path.relative_to(ROOT)}  ({len(edits)} 处)")
    if not apply:
        return True

    edits.sort(key=lambda e: (e[0], e[1]), reverse=True)
    for start_line, start_col, end_line, end_col, replacement in edits:
        if start_line != end_line:
            print(f"  ! 跳过跨行导入 {path}:{start_line}")
            continue
        line = lines[start_line - 1]
        lines[start_line - 1] = line[:start_col] + replacement + line[end_col:]

    path.write_text("".join(lines), encoding="utf-8")
    return True


def _rebuild_import(node: ast.AST, renames: dict | None = None, module: str | None = None) -> ast.AST:
    """构造一个只包含目标导入语句的 AST 片段，用于 unparse 出单行文本。"""
    renames = renames or {}
    if isinstance(node, ast.Import):
        names = [ast.alias(name=renames.get(id(a), a.name), asname=a.asname) for a in node.names]
        return ast.Import(names=names)
    return ast.ImportFrom(module=module if module is not None else node.module,
                          names=[ast.alias(name=a.name, asname=a.asname) for a in node.names],
                          level=node.level)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只报告，不写入")
    args = parser.parse_args()

    changed = 0
    for rel in SCAN_DIRS:
        base = ROOT / rel
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if process_file(path, apply=not args.check):
                changed += 1
    print(f"\n共 {changed} 个文件{'待修改' if args.check else '已修改'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
