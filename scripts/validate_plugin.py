"""插件规范校验器：供源仓库 CI 或本地提交前调用。

用法::

    uv run python scripts/validate_plugin.py <插件仓库路径> [--json]
    # 或在已安装 sllkgui 的环境中：
    python -m sllkgui.plugin.lint <插件仓库路径>

退出码：0 通过，1 存在错误。等价于 ``sllkgui plugin lint``，但不需要启动 Qt。

本脚本**不修改** ``sys.path``——那正是 lint 禁止插件做的事，基座自己不该做。
运行方式上优先用 ``uv run``（依赖已装在项目环境里）；若 sllkgui 未安装，
再用 ``--src`` 显式声明源码树位置，由调用方决定而非隐式注入。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _import_lint(src: Path | None):
    """拿到 lint 入口；必要时由调用方显式指定源码树。"""
    try:
        from sllkgui.gallery.lint import lint_plugin
    except ModuleNotFoundError as exc:
        if src is None:
            raise SystemExit(
                "未找到 sllkgui。请在已安装环境运行，或用 --src <源码树路径> 指定。\n"
                "（本脚本不自行修改 sys.path：基座不该做 lint 禁止插件做的事。）"
            ) from exc
        # 调用方显式指定源码树：此时才把路径加进 sys.path
        sys.path.insert(0, str(Path(src).resolve() / "src"))
        from sllkgui.gallery.lint import lint_plugin
    return lint_plugin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 SllkGUI 插件开发规范")
    parser.add_argument("path", help="插件仓库目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument(
        "--src",
        default=None,
        help="源码树路径（仅在 sllkgui 未安装时需要；默认取仓库自身的 src/）",
    )
    args = parser.parse_args(argv)

    src = Path(args.src) if args.src else ROOT
    lint_plugin = _import_lint(src)

    report = lint_plugin(Path(args.path))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"{report.plugin_id or args.path} {report.version}")
        for issue in report.errors:
            print(f"✗ [{issue.code}] {issue.message} {issue.file}:{issue.line}")
        for issue in report.warnings:
            print(f"⚠ [{issue.code}] {issue.message} {issue.file}:{issue.line}")
        print("通过" if report.ok else "未通过")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
