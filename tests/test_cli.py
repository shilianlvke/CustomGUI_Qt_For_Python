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
    """``doctor --apps-dir apps --allow-external``（相对路径）必须真的发现应用。

    回归：相对路径会被资源解析器当成「资源根下的相对路径」，结果永远是
    「发现应用：0 个」，而用户目录里明明有应用。该目录在已配置应用根之外，
    需加 ``--allow-external`` 放行归属校验，仍应正常发现。
    """
    app_dir = tmp_path / "apps" / "demo"
    (app_dir / "gui").mkdir(parents=True)
    (app_dir / "config.yml").write_text('app_name: "demo"\n', encoding="utf-8")
    (app_dir / "gui" / "main.py").write_text(
        "def build_page(app):\n    return None\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    code = cli.main(["doctor", "--apps-dir", "apps", "--allow-external"])
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


# FIX-01: 相交校验只在 --force 生效，不带 --force 时源码树默认路径不应被误拒。
def test_install_demo_without_force_allows_overlapping_source_dest(tmp_path, monkeypatch, capsys):
    """不带 --force 时源与目标同址只跳过已存在应用，不应被相交校验误拒。"""
    from sllkgui.appcore.sysx.config import paths

    source = tmp_path / "apps"
    (source / "demo").mkdir(parents=True)
    (source / "demo" / "config.yml").write_text('app_name: "demo"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "_demo_source", lambda: source)
    monkeypatch.setattr(paths, "data_root", lambda: source.parent)

    code = cli.main(["install-demo"])
    output = capsys.readouterr().out

    assert code == 0
    assert "已存在" in output or "跳过" in output
    assert (source / "demo" / "config.yml").is_file()


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


# ----------------------------------------------------------------------
# FIX-01：install-demo --force 覆盖前安全校验
# ----------------------------------------------------------------------
# FIX-01: 已有同名目录时 --force 应覆盖成功，内容来自内置示例源。
def test_install_demo_force_replaces_existing(tmp_path, capsys):
    """同名目录已存在时 --force 覆盖成功，内容取自内置示例源。"""
    dest = tmp_path / "my-apps"
    stale = dest / "button_preview"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("old", encoding="utf-8")

    code = cli.main(["install-demo", "--dest", str(dest), "--force"])
    capsys.readouterr()

    assert code == 0
    assert (dest / "button_preview" / "config.yml").is_file()
    assert not (stale / "stale.txt").exists()


# FIX-01: --dest 等于内置源目录时必须拒绝，且源应用不被删除。
def test_install_demo_force_rejects_source_dest_overlap(capsys):
    """目标与内置示例源同址时拒绝，避免 --force 自毁内置示例。"""
    source = cli._demo_source()
    assert source is not None
    sentinel = source / "button_preview" / "config.yml"
    assert sentinel.is_file()

    code = cli.main(["install-demo", "--force", "--dest", str(source)])
    output = capsys.readouterr().out

    assert code == 1
    assert "拒绝" in output
    assert sentinel.is_file()


# FIX-01: 目标为符号链接时拒绝覆盖（Windows 下以 monkeypatch 模拟，不真建链接）。
def test_install_demo_force_rejects_symlink_target(tmp_path, monkeypatch, capsys):
    """目标是符号链接时必须拒绝并返回非 0，打印目标名。"""
    dest = tmp_path / "my-apps"
    dest.mkdir()
    (dest / "button_preview").mkdir()
    real_is_symlink = Path.is_symlink

    def fake_is_symlink(self):
        return self.name == "button_preview" or real_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    code = cli.main(["install-demo", "--dest", str(dest), "--force"])
    output = capsys.readouterr().out

    assert code == 1
    assert "符号链接" in output
    assert "button_preview" in output


# FIX-01: copytree 抛 OSError 时返回非 0，且不残留半截目标目录。
def test_install_demo_force_returns_nonzero_on_oserror(tmp_path, monkeypatch, capsys):
    """复制失败应返回非 0 并清理已删除/半截的目标目录。"""
    source = cli._demo_source()
    assert source is not None
    first_name = sorted(p.name for p in source.iterdir() if p.is_dir())[0]
    dest = tmp_path / "my-apps"
    stale = dest / first_name
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("old", encoding="utf-8")

    def boom(src, dst, *args, **kwargs):
        Path(dst).mkdir(parents=True, exist_ok=True)
        raise OSError("模拟复制中断")

    monkeypatch.setattr(cli.shutil, "copytree", boom)

    code = cli.main(["install-demo", "--dest", str(dest), "--force"])
    output = capsys.readouterr().out

    assert code == 1
    assert "失败" in output
    assert not stale.exists()


# ----------------------------------------------------------------------
# FIX-03：doctor 安全诊断
# ----------------------------------------------------------------------
# FIX-03: 默认 doctor 只发现不加载，插件入口代码不得执行。
def test_doctor_does_not_execute_plugin_code_by_default(tmp_path, capsys):
    """默认 doctor 不执行应用入口代码，标记文件不应出现。"""
    apps_dir = tmp_path / "apps"
    app_dir = apps_dir / "demo"
    (app_dir / "gui").mkdir(parents=True)
    (app_dir / "config.yml").write_text('app_name: "demo"\n', encoding="utf-8")
    marker = tmp_path / "executed.marker"
    (app_dir / "gui" / "main.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )

    code = cli.main(["doctor", "--apps-dir", str(apps_dir), "--allow-external"])
    output = capsys.readouterr().out

    assert code == 0
    assert "发现应用      : 1 个" in output
    assert "成功加载" not in output
    assert not marker.exists()


# FIX-03: --load 触发加载动作，执行入口代码并输出「成功加载」。
def test_doctor_load_flag_executes_plugins(tmp_path, monkeypatch, capsys):
    """--load 会触发加载分支、执行入口代码并打印「成功加载」。

    真实加载器会改写全局 Language.app / app_state / PluginRegistry，残留会污染同批
    其它测试，故用受控桩替换 load_app_handles：桩通过 runpy 执行入口 main.py
    （写标记文件）后返回空句柄表。本用例以标记文件与「成功加载」输出共同锁定
    --load 触发了加载动作；默认不执行插件由
    test_doctor_does_not_execute_plugin_code_by_default 用真实 doctor 反向保证。
    """
    import runpy

    import sllkgui.window

    apps_dir = tmp_path / "apps"
    app_dir = apps_dir / "demo"
    (app_dir / "gui").mkdir(parents=True)
    (app_dir / "config.yml").write_text('app_name: "demo"\n', encoding="utf-8")
    marker = tmp_path / "executed.marker"
    (app_dir / "gui" / "main.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )

    def fake_load_app_handles(root=None, force=False):
        runpy.run_path(str(app_dir / "gui" / "main.py"))
        return []

    monkeypatch.setattr(sllkgui.window, "load_app_handles", fake_load_app_handles)

    code = cli.main(["doctor", "--apps-dir", str(apps_dir), "--allow-external", "--load"])
    output = capsys.readouterr().out

    assert code == 0
    assert "成功加载" in output
    assert marker.exists()


# FIX-03: 外部 --apps-dir 未加 --allow-external 时拒绝并返回非 0。
def test_doctor_rejects_unowned_apps_dir(tmp_path, capsys):
    """--apps-dir 越过已配置应用根且未放行时必须拒绝。"""
    external = tmp_path / "external-apps"
    external.mkdir()

    code = cli.main(["doctor", "--apps-dir", str(external)])
    output = capsys.readouterr().out

    assert code == 1
    assert "--allow-external" in output
    assert "拒绝" in output


# FIX-03: 加载阶段抛异常时返回非 0，不再吞掉后继续。
def test_doctor_returns_nonzero_on_load_failure(monkeypatch, capsys):
    """--load 下加载异常应返回非 0。"""
    import sllkgui.window

    def boom(*args, **kwargs):
        raise RuntimeError("模拟加载失败")

    monkeypatch.setattr(sllkgui.window, "load_app_handles", boom)

    code = cli.main(["doctor", "--load"])
    output = capsys.readouterr().out

    assert code == 1
    assert "失败" in output


# FIX-03: 模块顶层只依赖标准库，仅 import cli 不得传递导入 PySide6。
def test_cli_module_does_not_import_pyside6():
    """``import sllkgui.cli`` 后 PySide6 不应出现在 sys.modules。"""
    result = subprocess.run(
        [sys.executable, "-c", "import sllkgui.cli, sys; print('PySide6' in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "False"
