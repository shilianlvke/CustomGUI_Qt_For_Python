"""打包元数据契约：下游依赖本包时能拿到什么保证。

3.0 起基座承诺「分层类型化」：插件作者依赖的那一层（``sllkgui.plugin`` /
``sllkgui.window`` / 插件协议 / 设置 schema）类型完整；``guicore`` 组件库
内部不承诺。这组用例把该承诺固化，防止 ``py.typed`` 被误删、或门禁范围被
悄悄收窄到失去意义。
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_py_typed_marker_is_present():
    """``py.typed`` 必须随包分发，否则下游拿不到任何类型信息。"""
    marker = ROOT / "src" / "sllkgui" / "py.typed"
    assert marker.is_file(), "缺少 py.typed 标记文件"


def test_py_typed_marker_is_empty():
    """PEP 561 要求 inline 包的 ``py.typed`` 为空。

    ``partial`` 只适用于 stub-only 包；写进 inline 包会让部分检查器误判。
    """
    marker = ROOT / "src" / "sllkgui" / "py.typed"
    assert marker.read_text(encoding="utf-8").strip() == ""


def test_typed_classifier_is_declared():
    """声明了 ``Typing :: Typed`` 就要真的提供类型信息，两者必须一致。"""
    classifiers = _pyproject()["project"]["classifiers"]
    assert "Typing :: Typed" in classifiers


def test_mypy_gate_covers_the_public_api():
    """类型门禁必须覆盖下游插件作者真正依赖的那一层。

    这些模块是 ``sllkgui.plugin`` 的依赖闭包，少任何一个，门禁就名存实亡。
    """
    files = _pyproject()["tool"]["mypy"]["files"]
    required = {
        "src/sllkgui/plugin.py",
        "src/sllkgui/window.py",
        "src/sllkgui/gallery/api.py",
        "src/sllkgui/appcore/settings",
        "src/sllkgui/appcore/user_settings.py",
    }
    missing = required - set(files)
    assert not missing, f"类型门禁缺少公开 API 模块: {sorted(missing)}"


def test_downstream_receives_usable_type_information(tmp_path):
    """下游写错类型时，mypy 必须能报错——证明 ``py.typed`` 真的生效。

    这里刻意用 ``--follow-imports=normal``：仓库自身的门禁用 ``skip``
    提速，但对外部使用者，类型信息必须完整可用。
    """
    sample = tmp_path / "plugin_sample.py"
    sample.write_text(
        "from sllkgui.plugin import GalleryContext, Setting\n"
        "\n"
        "\n"
        "def bad(ctx: GalleryContext) -> None:\n"
        '    Setting.switch("k", "not-a-bool", "L")\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--no-incremental",
            "--follow-imports=normal",
            "--no-error-summary",
            str(sample),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "incompatible type" in result.stdout, (
        f"下游没有获得 sllkgui 的类型信息（py.typed 可能失效）：\n{result.stdout}\n{result.stderr}"
    )


def test_downstream_public_api_imports_are_typed(tmp_path):
    """插件作者会用的符号必须能被 mypy 解析，且类型正确。"""
    sample = tmp_path / "plugin_sample.py"
    sample.write_text(
        "from sllkgui.plugin import (\n"
        "    GalleryContext,\n"
        "    Plugin,\n"
        "    Setting,\n"
        "    SettingsPage,\n"
        "    SettingsSection,\n"
        ")\n"
        "\n"
        "\n"
        "def build(ctx: GalleryContext):\n"
        '    ctx.log("hi")\n'
        "    return None\n"
        "\n"
        "\n"
        "class P(Plugin):\n"
        "    def on_load(self, ctx: GalleryContext) -> None:\n"
        "        ctx.settings.define(\n"
        "            SettingsPage(\n"
        '                page_id="",\n'
        '                title="T",\n'
        "                sections=[\n"
        '                    SettingsSection(title="S", items=[Setting.switch("k", True, "L")])\n'
        "                ],\n"
        "            )\n"
        "        )\n"
        "\n"
        "    def surfaces(self):\n"
        '        return {"home": build}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--no-incremental",
            "--follow-imports=normal",
            "--no-error-summary",
            str(sample),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 0, f"下游插件作者的标准写法应当通过类型检查：\n{result.stdout}\n{result.stderr}"


@pytest.mark.parametrize("module", ["sllkgui.plugin", "sllkgui.window"])
def test_public_facades_export_expected_names(module: str):
    """公开门面必须真的导出文档承诺的类型。"""
    import importlib

    mod = importlib.import_module(module)
    assert mod.__all__, f"{module} 缺少 __all__"
    for name in mod.__all__:
        assert hasattr(mod, name), f"{module}.{name} 未导出"
