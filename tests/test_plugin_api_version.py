"""插件 API 版本唯一策略守卫（api=2）：

只保留最新协议版本，不做多版本共存与 capability detection。
本测试防止有人把写死的 api:1 带回来，确保 defaults.py 是唯一来源。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.gallery.defaults import PLUGIN_API_VERSION, SUPPORTED_API
from sllkgui.gallery.errors import PLUGIN_API_UNSUPPORTED
from sllkgui.gallery.manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).name

#: 写死的 v1 用法；defaults.py 允许出现历史常量定义以外的形式由常量守卫覆盖
_HARDCODED_V1 = [
    re.compile(r"\bapi\s*:\s*1\b"),
    re.compile(r"\bapi\s*=\s*1\b"),
    re.compile(r"""["']api["']\s*:\s*1\b"""),
    re.compile(r"""get\(["']api["']\s*,\s*1\s*\)"""),
    re.compile(r"\bapi\s*!=\s*1\b"),
]


def test_api_constants_aligned():
    assert PLUGIN_API_VERSION == 2
    assert SUPPORTED_API == {PLUGIN_API_VERSION}


def test_no_hardcoded_api_v1():
    """src/docs/examples/tests/README 中不得残留写死的 v1 用法。"""
    roots = [ROOT / name for name in ("src", "docs", "examples", "tests")] + [ROOT / "README.md"]
    hits: list[str] = []
    for target in roots:
        paths = (
            [target]
            if target.is_file()
            else list(target.rglob("*.py"))
            + list(target.rglob("*.yml"))
            + list(target.rglob("*.yaml"))
            + list(target.rglob("*.md"))
        )
        for path in paths:
            if not path.is_file() or path.name == SELF:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                # 允许 CHANGELOG / 评审报告里的历史陈述（非指令性配置）
                if path.name in {"CHANGELOG.md", "CHANGE_PLAN.md"}:
                    continue
                for pattern in _HARDCODED_V1:
                    if pattern.search(line):
                        hits.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert hits == [], "发现写死的 api v1:\n" + "\n".join(hits)


def test_api_v1_rejected(tmp_path: Path):
    """api:1 清单必须被拒——证明只保留最新协议，无兼容分支。"""
    text = """schema: 1
api: 1
id: com.example.v1
name: V1
version: 1.0.0
entry: plugin.py
surfaces:
  - id: home
    title: {en_us: Home}
"""
    root = write_plugin(tmp_path / "v1", manifest_text=text)
    with pytest.raises(Exception) as exc:
        load_manifest(root)
    assert getattr(exc.value, "code", None) == PLUGIN_API_UNSUPPORTED
