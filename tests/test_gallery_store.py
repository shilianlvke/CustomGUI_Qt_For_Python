from __future__ import annotations

from pathlib import Path

import pytest

from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.state import (
    InstalledPlugin,
    RegistryState,
    SourceRecord,
    SourcesState,
    load_registry,
    load_sources,
    save_registry,
    save_sources,
)
from sllkgui.gallery.store import GalleryStore


def test_store_layout_and_paths(tmp_path: Path):
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    assert store.plugins_dir.is_dir()
    assert store.staging_root.is_dir()
    assert store.data_dir("com.example.hello") == store.root / "data" / "com.example.hello"
    with pytest.raises(GalleryError):
        store.plugin_path("../escape")


def test_promote_history_and_trash(tmp_path: Path):
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    staging = store.new_staging()
    (staging / "old.txt").write_text("v1", encoding="utf-8")
    target = store.promote(staging, "com.example.hello", version="1.0.0", commit="a" * 40)
    assert (target / "old.txt").read_text(encoding="utf-8") == "v1"

    staging2 = store.new_staging()
    (staging2 / "new.txt").write_text("v2", encoding="utf-8")
    store.promote(staging2, "com.example.hello", version="2.0.0", commit="b" * 40)
    assert (store.plugin_path("com.example.hello") / "new.txt").is_file()
    history = list(store.history_dir("com.example.hello").iterdir())
    assert len(history) == 1 and (history[0] / "old.txt").is_file()

    trash = store.move_to_trash("com.example.hello")
    assert trash.is_dir() and not store.plugin_path("com.example.hello").exists()
    store.purge("com.example.hello")
    assert not store.data_dir("com.example.hello").exists()


def test_registry_roundtrip_and_corruption_backup(tmp_path: Path):
    path = tmp_path / "registry.json"
    state = RegistryState(base_version="2.0.0")
    state.plugins["com.example.hello"] = InstalledPlugin(
        plugin_id="com.example.hello",
        version="1.0.0",
        enabled=True,
        permissions=["filesystem.write"],
    )
    save_registry(path, state)
    loaded = load_registry(path)
    assert loaded.plugins["com.example.hello"].version == "1.0.0"

    path.write_text("{broken", encoding="utf-8")
    reset = load_registry(path)
    assert reset.plugins == {}
    assert list(tmp_path.glob("registry.json.broken-*"))


def test_sources_roundtrip(tmp_path: Path):
    path = tmp_path / "sources.json"
    save_sources(path, SourcesState(sources=[SourceRecord(source_id="official", url="https://example.com/x.git", trust="official")]))
    loaded = load_sources(path)
    assert loaded.get("official").trust == "official"


def test_store_helpers(tmp_path: Path):
    from sllkgui.gallery.errors import GalleryError

    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    data, cache = store.ensure_plugin_data("com.example.hello")
    assert data.is_dir() and cache.is_dir()
    staging = store.new_staging()
    (staging / "tmp.txt").write_text("x", encoding="utf-8")
    store.truncate_staging()
    assert not staging.exists()
    assert str(GalleryError("CODE", "message")) == "CODE: message"

