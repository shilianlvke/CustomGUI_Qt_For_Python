from __future__ import annotations

import sys
from pathlib import Path

from gallery_helpers import write_plugin

from sllkgui.gallery.loader import load_plugin, unload_plugin
from sllkgui.gallery.registry import GalleryRegistry
from sllkgui.gallery.store import GalleryStore


def _store(tmp_path: Path) -> GalleryStore:
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    return store


def test_load_plugin_and_context(tmp_path: Path, qapp):
    root = write_plugin(tmp_path / "hello")
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    assert record.plugin_id == "com.example.hello"
    assert registry.surface_count() == 1
    route = registry.default_route()
    assert route == "com.example.hello/home"
    surface = registry.get(route)
    assert surface.plugin.context.text("home.title", "?") in {"首页", "Home"}
    widget = surface.factory(surface.plugin.context)
    assert widget is not None
    unload_plugin(record)


def test_missing_plugin_export_is_isolated(tmp_path: Path):
    root = write_plugin(tmp_path / "bad", plugin_source="VALUE = 1\n")
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is None
    assert registry.surface_count() == 0
    assert any(item["code"] == "PLUGIN_LOAD_FAILED" for item in registry.errors)


def test_duplicate_plugin_skipped(tmp_path: Path):
    root = write_plugin(tmp_path / "hello")
    store = _store(tmp_path)
    registry = GalleryRegistry()
    assert load_plugin(root, store, registry) is not None
    assert load_plugin(root, store, registry) is None


def test_unload_purges_modules_imported_from_plugin_root(tmp_path: Path):
    """插件仓库内的子包必须随卸载清理，否则更新后仍命中旧模块。"""
    helper_name = "gallery_test_helper_pkg"
    root = write_plugin(tmp_path / "hello")
    helper = root / helper_name
    helper.mkdir()
    (helper / "__init__.py").write_text("VALUE = 'v1'\n", encoding="utf-8")
    source = (root / "plugin.py").read_text(encoding="utf-8")
    # 相对导入：插件不再把自身目录插进 sys.path（3.0 起）
    (root / "plugin.py").write_text(
        f"{source}\nfrom . import {helper_name}\n\nHELPER_VALUE = {helper_name}.VALUE\n",
        encoding="utf-8",
    )

    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    loaded = [name for name in sys.modules if name.endswith(f".{helper_name}")]
    assert loaded and sys.modules[loaded[0]].VALUE == "v1"

    unload_plugin(record)
    assert not [name for name in sys.modules if name.endswith(f".{helper_name}")]

    # 模拟插件更新：同一路径换成新代码后重载，应读到新模块而不是缓存
    (helper / "__init__.py").write_text("VALUE = 'v2'\nUPDATED = True\n", encoding="utf-8")
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    loaded = [name for name in sys.modules if name.endswith(f".{helper_name}")]
    assert loaded and sys.modules[loaded[0]].VALUE == "v2"
    unload_plugin(record)


def test_loading_plugin_never_touches_sys_path(tmp_path: Path):
    """插件目录绝不能进入 ``sys.path``。

    插到 ``sys.path[0]`` 等于把插件根排到标准库之前：插件里一个 ``json.py``
    就能在全进程劫持 ``import json``。3.0 起加载插件不得改动 ``sys.path``。
    """
    root = write_plugin(tmp_path / "hello")
    before = list(sys.path)
    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None
    assert sys.path == before, "加载插件不得改动 sys.path"
    unload_plugin(record)
    assert sys.path == before, "卸载插件不得改动 sys.path"


def test_plugin_shadowing_stdlib_does_not_win(tmp_path: Path):
    """插件自带的同名模块不得遮蔽标准库。

    插件里放一个 ``json.py``，基座的 ``import json`` 仍必须拿到标准库那份。
    """
    root = write_plugin(tmp_path / "hello")
    (root / "json.py").write_text("MARKER = 'hijacked'\n", encoding="utf-8")
    source = (root / "plugin.py").read_text(encoding="utf-8")
    (root / "plugin.py").write_text(
        f"{source}\nfrom . import json as plugin_json\n\nHELPER_VALUE = plugin_json.MARKER\n",
        encoding="utf-8",
    )

    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is not None

    import json

    assert not hasattr(json, "MARKER"), "标准库 json 被插件遮蔽了"
    unload_plugin(record)


def test_absolute_import_inside_plugin_gets_relative_hint(tmp_path: Path):
    """插件内写绝对导入时，报错要指向相对导入的写法。"""
    root = write_plugin(tmp_path / "hello")
    (root / "mylib.py").write_text("VALUE = 1\n", encoding="utf-8")
    source = (root / "plugin.py").read_text(encoding="utf-8")
    (root / "plugin.py").write_text(f"{source}\nimport mylib\n", encoding="utf-8")

    registry = GalleryRegistry()
    record = load_plugin(root, _store(tmp_path), registry)
    assert record is None
    errors = registry._errors
    assert errors
    assert "相对导入" in errors[0]["detail"], errors[0]["detail"]
