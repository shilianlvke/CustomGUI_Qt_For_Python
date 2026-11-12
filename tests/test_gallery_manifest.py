from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import write_plugin

from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.manifest import load_manifest


def test_load_valid_manifest(tmp_path: Path):
    root = write_plugin(tmp_path / "hello")
    manifest = load_manifest(root)
    assert manifest.plugin_id == "com.example.hello"
    assert manifest.version == "1.0.0"
    assert len(manifest.surfaces) == 1
    assert manifest.surfaces[0].default is True
    assert len(manifest.manifest_sha256) == 64


def test_invalid_id_rejected(tmp_path: Path):
    root = write_plugin(tmp_path / "hello", plugin_id="Bad Id")
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_ID_INVALID"


def test_invalid_version_rejected(tmp_path: Path):
    root = write_plugin(tmp_path / "hello", version="not-a-version")
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_VERSION_INVALID"


def test_empty_surfaces_rejected(tmp_path: Path):
    text = """schema: 1
api: 1
id: com.example.empty
name: Empty
version: 1.0.0
entry: plugin.py
surfaces: []
"""
    root = write_plugin(tmp_path / "hello", manifest_text=text)
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_SURFACE_EMPTY"


def test_path_escape_rejected(tmp_path: Path):
    text = """schema: 1
api: 1
id: com.example.escape
name: Escape
version: 1.0.0
entry: ../plugin.py
surfaces:
  - id: home
    title: {en_us: Home}
"""
    root = write_plugin(tmp_path / "hello", manifest_text=text)
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_PATH_ESCAPE"


def test_unknown_permission_rejected(tmp_path: Path):
    text = """schema: 1
api: 1
id: com.example.perm
name: Perm
version: 1.0.0
entry: plugin.py
surfaces:
  - id: home
    title: {en_us: Home}
permissions: [root]
"""
    root = write_plugin(tmp_path / "hello", manifest_text=text)
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_MANIFEST_INVALID"


def test_unsupported_api_rejected(tmp_path: Path):
    text = """schema: 1
api: 9
id: com.example.api
name: Api
version: 1.0.0
entry: plugin.py
surfaces:
  - id: home
    title: {en_us: Home}
"""
    root = write_plugin(tmp_path / "hello", manifest_text=text)
    with pytest.raises(GalleryError) as exc:
        load_manifest(root)
    assert exc.value.code == "PLUGIN_API_UNSUPPORTED"


def test_requires_unsatisfied(tmp_path: Path):
    text = """schema: 1
api: 1
id: com.example.req
name: Req
version: 1.0.0
entry: plugin.py
requires:
  sllkgui: ">=9.0.0"
surfaces:
  - id: home
    title: {en_us: Home}
"""
    root = write_plugin(tmp_path / "hello", manifest_text=text)
    with pytest.raises(GalleryError) as exc:
        load_manifest(root, current_sllkgui="2.0.0")
    assert exc.value.code == "PLUGIN_REQUIRES_UNSATISFIED"
