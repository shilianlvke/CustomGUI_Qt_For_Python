from __future__ import annotations

import os
import stat
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


def test_remove_dir_clears_readonly_git_objects(tmp_path: Path):
    """Git 的 pack/idx 在 Windows 上是只读文件，删除/移动前必须清属性。"""
    from sllkgui.gallery.store import remove_dir

    pack = tmp_path / "install" / ".git" / "objects" / "pack"
    pack.mkdir(parents=True)
    locked = pack / "pack-demo.idx"
    locked.write_text("x", encoding="utf-8")
    os.chmod(locked, stat.S_IREAD)

    remove_dir(tmp_path / "install")
    assert not (tmp_path / "install").exists()


def test_move_to_history_survives_locked_directory(tmp_path: Path, monkeypatch):
    """旧目录被占用时：先复制归档，再移入回收站，不能就地删出半个安装。"""
    from sllkgui.gallery import store as store_module

    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    current = store.plugin_path("com.example.hello")
    pack = current / ".git" / "objects" / "pack"
    pack.mkdir(parents=True)
    locked = pack / "pack-demo.idx"
    locked.write_text("x", encoding="utf-8")
    os.chmod(locked, stat.S_IREAD)

    original = store_module._rename_dir
    calls = {"count": 0}

    def flaky(src, dst):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError(13, "denied")
        original(src, dst)

    monkeypatch.setattr(store_module, "_rename_dir", flaky)
    history = store.move_to_history("com.example.hello", "1.0.0", "a" * 40)

    assert history.is_dir()
    assert (history / ".git" / "objects" / "pack" / "pack-demo.idx").is_file()
    assert not current.exists()
    assert list(store.trash_root.glob("com.example.hello-*")) == []

