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


def test_manifest_requires_current_base_version():
    """示例插件清单的基座版本区间必须与当前版本一致。

    基座升 major 时，示例与夹具里的版本区间要跟着走；否则 lint / 安装
    会因为「版本约束不满足」而失败，而这类失败往往拖到发布前才暴露。
    """
    from gallery_helpers import SLLKGUI_REQUIREMENT

    from sllkgui._version import __version__ as base_version

    major = base_version.split(".")[0]
    assert SLLKGUI_REQUIREMENT == f">={major}.0.0,<{int(major) + 1}.0.0"


def test_example_plugin_manifest_is_satisfied():
    """仓库内的示例插件必须能被当前基座的版本约束接受。"""
    from sllkgui.gallery.manifest import load_manifest

    from sllkgui._version import __version__ as base_version

    manifest = load_manifest(Path(__file__).resolve().parents[1] / "examples" / "plugin-hello")
    major = base_version.split(".")[0]
    assert manifest.requires_sllkgui == f">={major}.0.0,<{int(major) + 1}.0.0"
