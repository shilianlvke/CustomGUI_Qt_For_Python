from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.gallery import dependencies as deps
from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.loader import load_plugin
from sllkgui.gallery.manifest import load_manifest
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.store import GalleryStore

MANIFEST_WITH_DEPS = """schema: 1
api: 1
id: com.example.dep
name: Dep
version: 1.0.0
entry: plugin.py
requires:
  sllkgui: ">=2.0.0,<3.0.0"
python_dependencies:
  - sllkgui-missing-for-test>=1
surfaces:
  - id: home
    title: {en_us: Home}
    icon: resource/icon/home.svg
"""


def _store(tmp_path: Path) -> GalleryStore:
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    return store


def test_manifest_parses_python_dependencies(tmp_path: Path):
    root = write_plugin(tmp_path / "dep", plugin_id="com.example.dep", manifest_text=MANIFEST_WITH_DEPS)
    manifest = load_manifest(root)
    assert manifest.python_dependencies == ("sllkgui-missing-for-test>=1",)


def test_invalid_python_dependency_rejected(tmp_path: Path):
    text = MANIFEST_WITH_DEPS.replace("sllkgui-missing-for-test>=1", "not a requirement!!")
    root = write_plugin(tmp_path / "dep", plugin_id="com.example.dep", manifest_text=text)
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_MANIFEST_INVALID"


def test_missing_packages_detects_installed_and_missing():
    assert deps.missing_packages(["packaging>=20"]) == []
    assert deps.missing_packages(["sllkgui-missing-for-test>=1"]) == ["sllkgui-missing-for-test>=1"]


def test_parse_requirement_rejects_invalid():
    with pytest.raises(GalleryError) as exc:
        deps.parse_requirement("not a requirement!!")
    assert exc.value.code == "PYTHON_DEPENDENCY_MISSING"


def test_loader_isolates_missing_dependency(tmp_path: Path):
    root = write_plugin(tmp_path / "dep", plugin_id="com.example.dep", manifest_text=MANIFEST_WITH_DEPS)
    registry = GalleryRegistry()
    assert load_plugin(root, _store(tmp_path), registry) is None
    assert registry.surface_count() == 0
    error = next(item for item in registry.errors if item["code"] == "PYTHON_DEPENDENCY_MISSING")
    assert "sllkgui-missing-for-test" in error["detail"]


def test_auto_install_uses_mirror(monkeypatch):
    calls: dict[str, object] = {}

    def fake_missing(specs):
        return [] if calls.get("installed") else ["sllkgui-missing-for-test>=1"]

    def fake_install(packages, index_url="", uv_path=None):
        calls.update(packages=list(packages), index=index_url, installed=True)

    monkeypatch.setattr(deps, "missing_packages", fake_missing)
    monkeypatch.setattr(deps, "_ask_choice", lambda **kwargs: "auto")
    monkeypatch.setattr(deps, "ensure_uv", lambda **kwargs: "uv")
    monkeypatch.setattr(deps, "install_with_uv", fake_install)

    result = deps.ensure_python_dependencies(
        ["sllkgui-missing-for-test>=1"],
        plugin_id="com.example.dep",
        install=True,
        interactive=True,
        index_url="https://mirror.example/simple",
    )
    assert result == []
    assert calls["packages"] == ["sllkgui-missing-for-test>=1"]
    assert calls["index"] == "https://mirror.example/simple"


def test_manual_choice_reports_command(monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["sllkgui-missing-for-test>=1"])
    monkeypatch.setattr(deps, "_ask_choice", lambda **kwargs: "manual")
    monkeypatch.setattr(deps, "_show_manual", lambda **kwargs: shown.append(kwargs["command"]))

    with pytest.raises(GalleryError) as exc:
        deps.ensure_python_dependencies(["sllkgui-missing-for-test>=1"], install=True, interactive=True)
    assert exc.value.code == "PYTHON_DEPENDENCY_MISSING"
    assert shown and "sllkgui-missing-for-test" in shown[0]


def test_skip_install_when_disabled(monkeypatch):
    monkeypatch.setattr(deps, "missing_packages", lambda specs: ["sllkgui-missing-for-test>=1"])
    with pytest.raises(GalleryError) as exc:
        deps.ensure_python_dependencies(["sllkgui-missing-for-test>=1"], install=False)
    assert exc.value.code == "PYTHON_DEPENDENCY_MISSING"
    assert exc.value.params["packages"] == ["sllkgui-missing-for-test>=1"]


def test_tool_status_dict_keys():
    payload = deps.tool_status().to_dict()
    assert set(payload) == {"uv", "git", "pip"}


def test_ensure_tools_non_interactive_does_not_raise(monkeypatch):
    empty = deps.ToolStatus()
    monkeypatch.setattr(deps, "tool_status", lambda: empty)
    assert deps.ensure_tools(interactive=False) == empty


def test_ask_choice_non_interactive_returns_skip(monkeypatch):
    monkeypatch.setattr(deps.sys.stdin, "isatty", lambda: False)
    assert deps._ask_choice(title="t", message="m", detail="d", parent=None, interactive=True) == "skip"


def test_manual_command_contains_mirror(monkeypatch):
    monkeypatch.setattr(deps, "find_uv", lambda: "uv")
    assert "--index-url https://mirror.example/simple" in deps.manual_command(
        ["foo>=1"], "https://mirror.example/simple"
    )
    monkeypatch.setattr(deps, "find_uv", lambda: "")
    assert deps.manual_command(["foo>=1"]).startswith("python -m pip install")


def test_install_with_uv_builds_command(monkeypatch):
    captured: dict[str, object] = {}

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        captured["command"] = list(command)
        return Result()

    monkeypatch.setattr(deps.subprocess, "run", fake_run)
    deps.install_with_uv(["psutil>=6"], index_url="https://mirror.example/simple", uv_path="uv.exe")
    command = captured["command"]
    assert command[:4] == ["uv.exe", "pip", "install", "--python"]
    assert "--index-url" in command
    assert command[-1] == "psutil>=6"


def test_install_with_uv_failure_raises(monkeypatch):
    class Result:
        returncode = 1
        stderr = "boom"
        stdout = ""

    monkeypatch.setattr(deps.subprocess, "run", lambda command, **kwargs: Result())
    with pytest.raises(GalleryError) as exc:
        deps.install_with_uv(["psutil>=6"], uv_path="uv.exe")
    assert exc.value.code == "PYTHON_DEPENDENCY_INSTALL_FAILED"


def test_ensure_tools_auto_install(monkeypatch):
    empty = deps.ToolStatus()
    monkeypatch.setattr(deps, "tool_status", lambda: empty)
    monkeypatch.setattr(deps, "_ask_choice", lambda **kwargs: "auto")
    monkeypatch.setattr(deps, "_install_uv", lambda: "uv.exe")
    monkeypatch.setattr(deps, "_install_git", lambda: "git.exe")
    status = deps.ensure_tools(interactive=True)
    assert status.uv == "uv.exe"
    assert status.git == "git.exe"


def test_ensure_tools_manual_shows_both_commands(monkeypatch):
    empty = deps.ToolStatus()
    shown: list[str] = []
    monkeypatch.setattr(deps, "tool_status", lambda: empty)
    monkeypatch.setattr(deps, "_ask_choice", lambda **kwargs: "manual")
    monkeypatch.setattr(deps, "_show_manual", lambda **kwargs: shown.append(kwargs["command"]))
    deps.ensure_tools(interactive=True)
    assert shown and "uv:" in shown[0] and "Git:" in shown[0]


def test_config_pip_index_url_precedence(monkeypatch):
    from sllkgui.config import AppConfig

    monkeypatch.setenv("SLLKGUI_PIP_INDEX_URL", "https://env.example/simple")
    assert AppConfig().resolved_pip_index_url() == "https://env.example/simple"
    assert AppConfig(pip_index_url="https://explicit.example/simple").resolved_pip_index_url() == (
        "https://explicit.example/simple"
    )
    assert AppConfig(env_fallback=False).resolved_pip_index_url() == ""
