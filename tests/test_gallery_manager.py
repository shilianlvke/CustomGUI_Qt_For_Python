from __future__ import annotations

from pathlib import Path

import yaml
from gallery_helpers import git, init_repo, manifest_sha256, write_entry, write_plugin, write_source

from sllkgui.gallery.manager import PluginManager
from sllkgui.gallery.source import SourceManager
from sllkgui.gallery.state import RegistryState, SourcesState
from sllkgui.gallery.store import GalleryStore


def _append_version(source_root: Path, plugin_repo: Path, *, version: str, ref: str, commit: str, sha: str) -> None:
    path = source_root / "plugins" / "com.example.hello" / "entry.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["versions"].insert(
        0,
        {
            "version": version,
            "ref": ref,
            "commit": commit,
            "manifest_sha256": sha,
            "api": 1,
            "sllkgui": ">=2.0.0,<3.0.0",
            "python": ">=3.12",
            "permissions": ["filesystem.write"],
            "yanked": False,
        },
    )
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _setup(tmp_path: Path):
    plugin = write_plugin(tmp_path / "plugin", version="1.0.0")
    commit1 = init_repo(plugin, tag="v1.0.0")
    source = write_source(tmp_path / "source")
    write_entry(source, plugin, source_id="test", version="1.0.0", commit=commit1, sha=manifest_sha256(plugin))
    init_repo(source, tag="source-v1")

    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    sources = SourceManager(store, SourcesState(), allow_local=True)
    sources.add(source.as_uri(), source_id="test")
    sources.refresh("test")
    state = RegistryState(base_version="2.0.0")
    manager = PluginManager(store, state, sources, base_version="2.0.0")
    return plugin, source, sources, manager, store


def test_install_update_rollback_remove(tmp_path: Path):
    plugin, source, sources, manager, store = _setup(tmp_path)

    result = manager.install("com.example.hello", source_id="test")
    assert result["version"] == "1.0.0"
    assert store.plugin_path("com.example.hello").is_dir()
    assert manager.state.plugins["com.example.hello"].enabled is True
    assert manager.verify()[0]["ok"] is True

    # 发布 1.1.0
    write_plugin(plugin, version="1.1.0")
    git("add", "-A", cwd=plugin)
    git("commit", "-q", "-m", "bump", cwd=plugin)
    git("tag", "v1.1.0", cwd=plugin)
    commit2 = git("rev-parse", "HEAD", cwd=plugin)
    _append_version(source, plugin, version="1.1.0", ref="v1.1.0", commit=commit2, sha=manifest_sha256(plugin))
    git("add", "-A", cwd=source)
    git("commit", "-q", "-m", "entry", cwd=source)
    sources.refresh("test")

    update = manager.update("com.example.hello")
    assert update["updated"] is True
    assert manager.state.plugins["com.example.hello"].version == "1.1.0"
    assert manager.state.plugins["com.example.hello"].previous["version"] == "1.0.0"

    rollback = manager.rollback("com.example.hello")
    assert rollback["version"] == "1.0.0"
    assert manager.state.plugins["com.example.hello"].version == "1.0.0"

    manager.remove("com.example.hello", purge=True)
    assert "com.example.hello" not in manager.state.plugins
    assert not store.plugin_path("com.example.hello").exists()


def test_install_duplicate_and_missing(tmp_path: Path):
    _plugin, _source, _sources, manager, _store = _setup(tmp_path)
    manager.install("com.example.hello", source_id="test")
    try:
        manager.install("com.example.hello", source_id="test")
    except Exception as exc:  # noqa: BLE001
        assert exc.code == "PLUGIN_ALREADY_INSTALLED"
    else:  # pragma: no cover
        raise AssertionError("duplicate install must fail")


def test_enable_requires_dependencies(tmp_path: Path):
    _plugin, _source, _sources, manager, _store = _setup(tmp_path)
    manager.install("com.example.hello", source_id="test")
    assert manager.set_enabled("com.example.hello", False)["enabled"] is False
    assert manager.set_enabled("com.example.hello", True)["enabled"] is True


def test_verify_missing_directory(tmp_path: Path):
    from sllkgui.gallery.state import InstalledPlugin

    _plugin, _source, _sources, manager, _store = _setup(tmp_path)
    manager.state.plugins["com.example.missing"] = InstalledPlugin(
        plugin_id="com.example.missing", version="1.0.0", path="plugins/com.example.missing"
    )
    result = manager.verify("com.example.missing")[0]
    assert result["ok"] is False
    assert "插件目录不存在" in result["issues"]


def test_remove_required_by_and_force(tmp_path: Path):
    from sllkgui.gallery.state import InstalledPlugin

    _plugin, _source, _sources, manager, _store = _setup(tmp_path)
    manager.state.plugins["com.example.core"] = InstalledPlugin(
        plugin_id="com.example.core", version="1.0.0", path="plugins/com.example.core"
    )
    manager.state.plugins["com.example.user"] = InstalledPlugin(
        plugin_id="com.example.user",
        version="1.0.0",
        path="plugins/com.example.user",
        dependencies={"com.example.core": ">=1.0.0"},
    )
    from sllkgui.gallery.errors import GalleryError

    try:
        manager.remove("com.example.core")
    except GalleryError as exc:
        assert exc.code == "PLUGIN_REMOVE_REQUIRED_BY"
    else:  # pragma: no cover
        raise AssertionError("dependent plugin must block removal")
    manager.remove("com.example.core", force=True)
    assert manager.state.plugins["com.example.user"].enabled is False


def test_enable_fails_when_dependency_disabled(tmp_path: Path):
    from sllkgui.gallery.errors import GalleryError
    from sllkgui.gallery.state import InstalledPlugin

    _plugin, _source, _sources, manager, _store = _setup(tmp_path)
    manager.state.plugins["com.example.core"] = InstalledPlugin(
        plugin_id="com.example.core", version="1.0.0", path="plugins/com.example.core", enabled=False
    )
    manager.state.plugins["com.example.user"] = InstalledPlugin(
        plugin_id="com.example.user",
        version="1.0.0",
        path="plugins/com.example.user",
        dependencies={"com.example.core": ">=1.0.0"},
    )
    try:
        manager.set_enabled("com.example.user", True)
    except GalleryError as exc:
        assert exc.code == "PLUGIN_DEPENDENCY_DISABLED"
    else:  # pragma: no cover
        raise AssertionError("disabled dependency must block enable")
