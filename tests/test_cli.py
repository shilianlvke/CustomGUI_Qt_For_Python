"""CLI 与「开箱即用」路径的回归测试。

这些用例守的是**装完就能用**：不需要用户先读三页 README，也不需要设
5 个环境变量。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from customgui import cli


def test_doctor_runs_and_reports_version(capsys):
    code = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert code == 0
    assert "CustomGUI doctor" in output
    assert "应用目录" in output
    assert "当前主题" in output


def test_doctor_reports_missing_apps_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CUSTOMGUI_APPS_DIR", str(tmp_path / "nope"))
    code = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert code == 0
    assert "应用目录" in output
    assert "install-demo" in output


def test_install_demo_copies_bundled_apps(tmp_path, capsys, monkeypatch):
    # 源码树里没有 customgui/apps（wheel 才有），这里把仓库 apps/ 当作包内示例
    monkeypatch.setattr(cli, "_demo_source", lambda: Path(__file__).resolve().parents[1] / "apps")

    dest = tmp_path / "my-apps"
    code = cli.main(["install-demo", "--dest", str(dest)])
    output = capsys.readouterr().out

    assert code == 0
    assert dest.is_dir()
    assert (dest / "button_preview" / "config.yml").is_file()
    assert "button_preview" in output


def test_install_demo_skips_existing_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_demo_source", lambda: Path(__file__).resolve().parents[1] / "apps")
    dest = tmp_path / "my-apps"
    (dest / "button_preview").mkdir(parents=True)

    cli.main(["install-demo", "--dest", str(dest)])
    output = capsys.readouterr().out
    assert "已存在" in output or "跳过" in output


def test_examples_copy_writes_runnable_skeleton(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "_example_source", lambda: Path(__file__).resolve().parents[1] / "examples" / "hello_world"
    )
    dest = tmp_path / "myapp"

    code = cli.main(["examples", "--copy", str(dest)])
    capsys.readouterr()

    assert code == 0
    assert (dest / "main.py").is_file()


def test_examples_copy_refuses_non_empty_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "_example_source", lambda: Path(__file__).resolve().parents[1] / "examples" / "hello_world"
    )
    dest = tmp_path / "busy"
    dest.mkdir()
    (dest / "keep.txt").write_text("x", encoding="utf-8")

    code = cli.main(["examples", "--copy", str(dest)])
    output = capsys.readouterr().out

    assert code == 1
    assert "非空" in output


def test_module_entry_point_matches_cli():
    """``python -m customgui`` 必须与 ``customgui`` 命令同源。"""
    result = subprocess.run(
        [sys.executable, "-m", "customgui", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "customgui" in result.stdout.lower()


def test_py_typed_is_packaged():
    """PEP 561 标记必须存在于包内，否则类型检查器不认。"""
    import customgui

    assert (Path(customgui.__file__).parent / "py.typed").is_file()


@pytest.mark.parametrize("command", ["run", "install-demo", "examples", "doctor"])
def test_parser_defines_all_subcommands(command):
    parser = cli.build_parser()
    args = parser.parse_args([command])
    assert callable(args.func)
