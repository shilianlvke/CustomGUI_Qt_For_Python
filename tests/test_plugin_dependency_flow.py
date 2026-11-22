"""依赖补全流程：加载期只检查、GUI 不弹窗、管理页可一键补全。

回归的是「缺少插件依赖」模态带来的三个问题：启动被阻断、信息层级错位、
用户没有可恢复的入口。新契约是：结构化错误 + 状态 + 显式补全动作。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sllkgui.gallery import dependencies as deps
from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.runtime import GalleryRuntime


def test_gui_never_prompts(monkeypatch):
    """GUI 下 ``ensure_python_dependencies`` 不得弹选择框，只回传结构化错误。"""
    monkeypatch.setattr(deps, "_gui_available", lambda: True)
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["demo-missing>=1"])
    prompted: list[dict] = []
    monkeypatch.setattr(deps, "_ask_choice", lambda **kwargs: prompted.append(kwargs) or "auto")

    with pytest.raises(GalleryError) as exc:
        deps.ensure_python_dependencies(
            ["demo-missing>=1"],
            plugin_id="com.example.demo",
            install=True,
            interactive=True,
        )
    assert exc.value.code == "PYTHON_DEPENDENCY_MISSING"
    assert exc.value.params["packages"] == ["demo-missing>=1"]
    assert "uv pip install" in exc.value.params["command"]
    assert prompted == []


def test_install_helper_installs_and_verifies(monkeypatch):
    installed: list[str] = []
    monkeypatch.setattr(deps, "is_frozen", lambda: False)
    monkeypatch.setattr(
        deps,
        "install_with_uv",
        lambda packages, index_url="", uv_path=None: installed.extend(packages),
    )
    monkeypatch.setattr(deps, "missing_packages", lambda specs: [])

    deps.install_python_dependencies(["demo>=1"], index_url="https://mirror.example/simple")
    assert installed == ["demo>=1"]


def test_install_helper_reports_remaining(monkeypatch):
    monkeypatch.setattr(deps, "is_frozen", lambda: False)
    monkeypatch.setattr(deps, "install_with_uv", lambda *args, **kwargs: None)
    monkeypatch.setattr(deps, "missing_packages", lambda specs: list(specs))

    with pytest.raises(GalleryError) as exc:
        deps.install_python_dependencies(["demo>=1"])
    assert exc.value.code == "PYTHON_DEPENDENCY_INSTALL_FAILED"
    assert exc.value.params["packages"] == ["demo>=1"]


def test_frozen_env_reports_supported_workarounds(monkeypatch):
    monkeypatch.setattr(deps, "is_frozen", lambda: True)
    with pytest.raises(GalleryError) as exc:
        deps.install_python_dependencies(["demo>=1"])
    assert exc.value.code == "FROZEN_ENV_UNSUPPORTED"
    assert "vendor/" in str(exc.value.message)


def _runtime(tmp_path: Path, *, install: bool = True) -> GalleryRuntime:
    runtime = GalleryRuntime("gallery", data_dir=tmp_path / "data", install_missing_deps=install)
    runtime.manager = SimpleNamespace(declared_dependencies=lambda plugin_id: ("demo>=1",))
    return runtime


def test_runtime_reports_declared_and_missing(tmp_path: Path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["demo>=1"])
    declared, missing = runtime.plugin_dependencies("com.example.demo")
    assert declared == ("demo>=1",)
    assert missing == ("demo>=1",)


def test_runtime_installs_and_returns_packages(tmp_path: Path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["demo>=1"])
    installed: list[str] = []
    monkeypatch.setattr(
        deps,
        "install_python_dependencies",
        lambda packages, index_url="": installed.extend(packages),
    )
    # 安装后复查：模拟依赖已就绪
    monkeypatch.setattr(deps, "missing_packages", lambda specs: [] if installed else ["demo>=1"])
    assert runtime.install_plugin_dependencies("com.example.demo") == ("demo>=1",)
    assert installed == ["demo>=1"]


def test_runtime_honours_no_install_flag(tmp_path: Path, monkeypatch):
    runtime = _runtime(tmp_path, install=False)
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["demo>=1"])
    monkeypatch.setattr(
        deps,
        "install_python_dependencies",
        lambda *args, **kwargs: pytest.fail("--no-install-deps 下不得调用安装"),
    )
    with pytest.raises(GalleryError) as exc:
        runtime.install_plugin_dependencies("com.example.demo")
    assert exc.value.code == "PYTHON_DEPENDENCY_MISSING"
    assert "--no-install-deps" in str(exc.value.message)


def test_dependency_command_is_copyable(tmp_path: Path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["demo>=1"])
    command = runtime.plugin_dependency_command("com.example.demo")
    assert "uv pip install" in command and "demo>=1" in command
