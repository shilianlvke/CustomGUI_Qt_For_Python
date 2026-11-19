"""插件规范校验器：供源仓库 CI 或本地提交前调用。

用法::

    uv run python scripts/validate_plugin.py <插件仓库路径> [--json]
    # 或在已安装 sllkgui 的环境中：
    python -m sllkgui.plugin.lint <插件仓库路径>

退出码：0 通过，1 存在错误。等价于 ``sllkgui plugin lint``，但不需要启动 Qt。

本脚本**不修改** ``sys.path``——那正是 lint 禁止插件做的事，基座自己不该做。
运行方式上优先用 ``uv run``（依赖已装在项目环境里）；在其它环境中请先安装
sllkgui，或由调用方自行设置 ``PYTHONPATH``，本脚本不会隐式注入源码路径。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _import_lint():
    """拿到 lint 入口；未安装 sllkgui 时给出明确指引，不修改 sys.path。"""
    try:
        from sllkgui.gallery.lint import lint_plugin
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "未找到 sllkgui。请用 uv run 运行、先安装 sllkgui，或由调用方自行设置 PYTHONPATH；本脚本不修改 sys.path。"
        ) from exc
    return lint_plugin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 SllkGUI 插件开发规范")
    parser.add_argument("path", help="插件仓库目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args(argv)

    lint_plugin = _import_lint()

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
