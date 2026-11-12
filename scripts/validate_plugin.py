"""插件规范校验器：供源仓库 CI 或本地提交前调用。

用法::

    python scripts/validate_plugin.py <插件仓库路径> [--json]

退出码：0 通过，1 存在错误。等价于 ``sllkgui plugin lint``，但不需要启动 Qt。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sllkgui.gallery.lint import lint_plugin  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 SllkGUI 插件开发规范")
    parser.add_argument("path", help="插件仓库目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args(argv)

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
