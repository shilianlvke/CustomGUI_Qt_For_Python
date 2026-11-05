"""CLI 与「开箱即用」路径的回归测试。

这些用例守的是**装完就能用**：不需要用户先读三页 README，也不需要设
5 个环境变量。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sllkgui import cli


def test_doctor_runs_and_reports_version(capsys):
    code = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert code == 0
    assert "SllkGUI doctor" in output
    assert "应用目录" in output
    assert "当前主题" in output


def test_doctor_reports_missing_apps_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SLLKGUI_APPS_DIR", str(tmp_path / "nope"))
    code = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert code == 0
    assert "应用目录" in output
    assert "install-demo" in output


def test_doctor_accepts_relative_apps_dir(tmp_path, monkeypatch, capsys):
    """``doctor --apps-dir apps``（相对路径）必须真的发现应用。

    回归：相对路径会被资源解析器当成「资源根下的相对路径」，结果永远是
    「发现应用：0 个」，而用户目录里明明有应用。
    """
    app_dir = tmp_path / "apps" / "demo"
    (app_dir / "gui").mkdir(parents=True)
    (app_dir / "config.yml").write_text('app_name: "demo"\n', encoding="utf-8")
    (app_dir / "gui" / "main.py").write_text(
        "def build_page(app):\n    return None\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    code = cli.main(["doctor", "--apps-dir", "apps"])
    output = capsys.readouterr().out

    assert code == 0
    assert "发现应用      : 1 个" in output
    assert "demo" in output


def test_bundled_dirs_resolve_without_wheel_install(capsys):
    """源码树里没有 ``sllkgui/apps``，也要回落到仓库 ``apps/`` 与 ``examples/``。"""
    demo = cli._demo_source()
    example = cli._example_source()

    assert demo is not None
    assert (demo / "button_preview" / "config.yml").is_file()
    assert example is not None
    assert (example / "main.py").is_file()

    code = cli.main(["examples"])
    output = capsys.readouterr().out
    assert code == 0
    assert "内置示例位置" in output


def test_install_demo_copies_bundled_apps(tmp_path, capsys):
    dest = tmp_path / "my-apps"
    code = cli.main(["install-demo", "--dest", str(dest)])
    output = capsys.readouterr().out

    assert code == 0
    assert dest.is_dir()
    assert (dest / "button_preview" / "config.yml").is_file()
    assert "button_preview" in output


def test_install_demo_skips_existing_without_force(tmp_path, capsys):
    dest = tmp_path / "my-apps"
    (dest / "button_preview").mkdir(parents=True)

    cli.main(["install-demo", "--dest", str(dest)])
    output = capsys.readouterr().out
    assert "已存在" in output or "跳过" in output


def test_examples_copy_writes_runnable_skeleton(tmp_path, capsys):
    dest = tmp_path / "myapp"

    code = cli.main(["examples", "--copy", str(dest)])
    capsys.readouterr()

    assert code == 0
    assert (dest / "main.py").is_file()


def test_examples_copy_refuses_non_empty_dir(tmp_path, capsys):
    dest = tmp_path / "busy"
    dest.mkdir()
    (dest / "keep.txt").write_text("x", encoding="utf-8")

    code = cli.main(["examples", "--copy", str(dest)])
    output = capsys.readouterr().out

    assert code == 1
    assert "非空" in output


def test_version_comes_from_version_file():
    """``__version__`` 以 ``_version.py`` 为准。

    回归：以前优先读 ``importlib.metadata``，源码树里改了 ``_version.py``
    却还显示 site-packages 里那个旧 wheel 的版本号。
    """
    import sllkgui
    from sllkgui._version import __version__ as source_version

    assert sllkgui.__version__ == source_version


def test_module_entry_point_matches_cli():
    """``python -m sllkgui`` 必须与 ``sllkgui`` 命令同源。"""
    result = subprocess.run(
        [sys.executable, "-m", "sllkgui", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "sllkgui" in result.stdout.lower()


def test_py_typed_is_packaged():
    """PEP 561 标记必须存在于包内，否则类型检查器不认。"""
    import sllkgui

    assert (Path(sllkgui.__file__).parent / "py.typed").is_file()


@pytest.mark.parametrize("command", ["run", "install-demo", "examples", "doctor"])
def test_parser_defines_all_subcommands(command):
    parser = cli.build_parser()
    args = parser.parse_args([command])
    assert callable(args.func)
