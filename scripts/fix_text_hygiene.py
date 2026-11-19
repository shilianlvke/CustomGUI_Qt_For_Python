"""文件卫生检查：末尾换行与行尾空白。

供 pre-commit 调用，也可单独运行::

    uv run python scripts/fix_text_hygiene.py            # 检查并报告
    uv run python scripts/fix_text_hygiene.py --fix      # 就地修复

只处理文本文件；``.md`` 保留行尾双空格（Markdown 用它表示换行）。
二进制文件与 ``.git`` / ``.venv`` 等目录自动跳过。
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 跳过的目录
SKIP_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "logs",
    "node_modules",
    "_resources",
    # 运行时产物目录（.gitignore 已忽略）
    "gallery",
    "settings",
    "Data",
}

#: 只检查这些后缀：源码与配置。SVG/图片等资源由导出工具生成，不做改写。
CHECKED_SUFFIXES = {
    ".py",
    ".md",
    ".markdown",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".cfg",
    ".ini",
    ".txt",
    ".bat",
    ".cmd",
    ".ps1",
    ".ui",
    ".qml",
}

#: 这些后缀不做行尾空白清理
KEEP_TRAILING_SPACE = {".md", ".markdown"}


def _is_text(path: Path) -> bool:
    try:
        path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return True


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in CHECKED_SUFFIXES:
            continue
        yield path


def _display(path: Path) -> str:
    """尽量给出相对仓库根的路径；不在仓库内时退回绝对路径。"""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_skipped(path: Path) -> bool:
    """路径是否落在跳过目录里。

    pre-commit 按文件名逐个传给钩子时，``rglob`` 的目录过滤不会生效，
    这里再按路径分段判一次，避免误改资源文件。
    """
    try:
        parts = path.resolve().relative_to(ROOT).parts
    except ValueError:
        parts = path.parts
    return any(part in SKIP_DIRS for part in parts)


def check(path: Path, fix: bool) -> list[str]:
    """返回该文件的问题列表；``fix`` 为真时就地修复。"""
    # 后缀白名单：资源文件（SVG / 图片等）由导出工具生成，一律不改写。
    # 这条检查放在最前面，避免调用方直接传文件名绕过过滤。
    if path.suffix.lower() not in CHECKED_SUFFIXES:
        return []
    if _is_skipped(path):
        return []
    if not _is_text(path):
        return []
    try:
        original = path.read_text(encoding="utf-8")
    except OSError:
        return []

    problems: list[str] = []
    fixed = original

    # 行尾空白（Markdown 除外）
    if path.suffix.lower() not in KEEP_TRAILING_SPACE:
        cleaned = "\n".join(line.rstrip() for line in fixed.split("\n"))
        if cleaned != fixed:
            problems.append(f"{_display(path)}: 行尾空白")
            fixed = cleaned

    # 末尾换行
    if fixed and not fixed.endswith("\n"):
        problems.append(f"{_display(path)}: 缺少末尾换行")
        fixed += "\n"

    if fix and fixed != original:
        path.write_text(fixed, encoding="utf-8")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查并修复文件末尾换行与行尾空白")
    parser.add_argument("paths", nargs="*", default=["."], help="要检查的路径")
    parser.add_argument("--fix", action="store_true", help="就地修复")
    args = parser.parse_args(argv)

    roots = [Path(item) for item in (args.paths or ["."])]
    problems: list[str] = []
    for root in roots:
        target = root if root.is_file() else root
        files = [target] if target.is_file() else _iter_files(target)
        for path in files:
            problems.extend(check(path, args.fix))

    for item in problems:
        print(item)

    if problems and not args.fix:
        print(f"\n共 {len(problems)} 处问题（加 --fix 可就地修复）")
        return 1
    if args.fix and problems:
        print(f"\n已修复 {len(problems)} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
