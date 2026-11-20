from __future__ import annotations

from pathlib import Path

from gallery_helpers import init_repo, write_entry, write_plugin, write_source

from sllkgui.gallery.source import SourceManager
from sllkgui.gallery.state import SourcesState
from sllkgui.gallery.store import GalleryStore


def _prepared_source(tmp_path: Path, *, yanked: bool = False):
    plugin = write_plugin(tmp_path / "plugin")
    commit = init_repo(plugin)
    source = write_source(tmp_path / "source")
    write_entry(source, plugin, source_id="test", commit=commit, yanked=yanked)
    init_repo(source, tag="source-v1")
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    manager = SourceManager(store, SourcesState(), allow_local=True)
    manager.add(source.as_uri(), source_id="test", trust="user")
    manager.refresh("test")
    return manager, plugin, commit


def test_source_refresh_and_index(tmp_path: Path):
    manager, plugin, commit = _prepared_source(tmp_path)
    index = manager.index()
    assert "com.example.hello" in index.entries
    entry = index.entries["com.example.hello"][0]
    assert entry.repository == plugin.resolve().as_uri()
    assert entry.latest().commit == commit
    assert entry.latest().version == "1.0.0"


def test_yanked_version_filtered(tmp_path: Path):
    manager, _plugin, _commit = _prepared_source(tmp_path, yanked=True)
    index = manager.index()
    entry = index.entries["com.example.hello"][0]
    assert entry.latest() is None


def test_bad_entry_is_skipped(tmp_path: Path):
    manager, _plugin, _commit = _prepared_source(tmp_path)
    root = manager.store.source_path("test")
    bad = root / "plugins" / "bad.example"
    bad.mkdir(parents=True)
    (bad / "entry.yaml").write_text("schema: 1\nid: bad.example\n", encoding="utf-8")
    index = manager.index()
    assert "bad.example" not in index.entries
    assert "com.example.hello" in index.entries


def test_legacy_api_versions_skipped_but_entry_kept(tmp_path: Path):
    """条目含旧 api 版本时不应整条丢弃，兼容版本仍可被索引与安装。"""
    import yaml

    manager, _plugin, commit = _prepared_source(tmp_path)
    root = manager.store.source_path("test")
    entry_path = root / "plugins" / "com.example.hello" / "entry.yaml"
    entry = yaml.safe_load(entry_path.read_text(encoding="utf-8"))
    legacy = dict(entry["versions"][0])
    legacy["version"] = "0.9.0"
    legacy["ref"] = "v0.9.0"
    legacy["api"] = 1
    entry["versions"].append(legacy)
    entry_path.write_text(yaml.safe_dump(entry, allow_unicode=True), encoding="utf-8")

    manager.refresh("test")
    index = manager.index()
    assert "com.example.hello" in index.entries
    versions = {item.version for item in index.entries["com.example.hello"][0].versions}
    assert versions == {"1.0.0"}
    assert index.entries["com.example.hello"][0].latest().version == "1.0.0"


def test_source_info_and_remove(tmp_path: Path):
    manager, _plugin, _commit = _prepared_source(tmp_path)
    info = manager.info("test")
    assert info.source_id == "test"
    manager.remove("test")
    assert manager.list() == []
