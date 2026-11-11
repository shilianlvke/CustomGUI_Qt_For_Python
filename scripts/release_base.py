"""基座补丁发布 helper：bump patch → 质量门禁 → 提交 → 打 tag → 推送。

用法（在 SllkGui 仓库根执行）::

    uv run python scripts/release_base.py --dry-run          # 只看将要发生什么
    uv run python scripts/release_base.py --message "fix: ..."  # 正式发布

脚本只处理 ``base-vX.Y.Z`` 的补丁位；minor / major 请手工修改版本号后再跑
``--tag-only``。发布前必须通过 ruff + mypy + pytest（覆盖率 70%），任一失败
直接退出，不会产生提交或 tag。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "sllkgui" / "_version.py"
CHANGELOG = ROOT / "CHANGELOG.md"
TAG_PREFIX = "base-v"
_COVERAGE_GATE = "70"


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, check=check, text=True, capture_output=True)


def _version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if match is None:
        raise SystemExit("无法从 _version.py 读取版本号")
    return match.group(1)


def _bump_patch(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _write_version(version: str) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(
        re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"', text),
        encoding="utf-8",
    )


def _sync_changelog(old: str, new: str) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    text = text.replace(f"当前版本：`{old}`", f"当前版本：`{new}`")
    text = text.replace(f"对应 tag `{TAG_PREFIX}{old}`", f"对应 tag `{TAG_PREFIX}{new}`")
    CHANGELOG.write_text(text, encoding="utf-8")


def _gate() -> None:
    dist = ROOT / "dist"
    steps: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ruff", ("uv", "run", "ruff", "check", "src", "tests", "apps", "examples", "scripts")),
        ("mypy", ("uv", "run", "mypy")),
        (
            "pytest",
            (
                "uv",
                "run",
                "pytest",
                "--cov=sllkgui",
                "--cov-report=term",
                f"--cov-fail-under={_COVERAGE_GATE}",
            ),
        ),
        ("build", ("uv", "run", "python", "-m", "build", "--wheel")),
    )
    for name, command in steps:
        print(f"[gate] {name}: {' '.join(command)}")
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(f"质量门禁失败：{name}")

    wheels = sorted(str(path) for path in dist.glob("*.whl"))
    if not wheels:
        raise SystemExit("质量门禁失败：dist 中没有 wheel")
    print(f"[gate] twine: {' '.join(wheels)}")
    if subprocess.run(("uv", "run", "twine", "check", *wheels), cwd=ROOT).returncode != 0:
        raise SystemExit("质量门禁失败：twine")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发布 SllkGUI 补丁版本")
    parser.add_argument("--message", default="", help="提交信息后缀（默认使用 release 文案）")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不修改文件")
    parser.add_argument("--skip-gate", action="store_true", help="跳过质量门禁（不推荐）")
    parser.add_argument("--tag-only", action="store_true", help="只打当前版本号的 tag 并推送")
    args = parser.parse_args(argv)

    current = _version()
    if args.tag_only:
        target = current
    else:
        target = _bump_patch(current)

    tag = f"{TAG_PREFIX}{target}"
    print(f"当前版本 {current} -> 目标版本 {target}（tag {tag}）")

    existing = _run("git", "tag", "--list", tag, check=False).stdout.strip()
    if existing:
        raise SystemExit(f"tag 已存在：{tag}")

    if args.dry_run:
        print("dry-run：将修改 _version.py / CHANGELOG.md，运行质量门禁并推送 tag")
        return 0

    if not args.tag_only:
        _write_version(target)
        _sync_changelog(current, target)

    if not args.skip_gate:
        _gate()

    message = args.message or f"release: SllkGUI {target} ({tag})"
    _run("git", "add", "src/sllkgui/_version.py", "CHANGELOG.md")
    commit = _run("git", "commit", "-m", message, check=False)
    if commit.returncode != 0:
        print(commit.stdout or commit.stderr)
    _run("git", "tag", "-a", tag, "-m", f"SllkGUI {target}")
    _run("git", "push", "origin", "HEAD")
    _run("git", "push", "origin", tag)
    print(f"已发布 {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
