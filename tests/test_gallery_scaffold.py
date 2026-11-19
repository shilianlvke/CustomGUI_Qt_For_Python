"""脚手架产物必须真的能被加载，而不只是"看起来合规"。

历史缺陷：模板里的 ``{{"home": build_home}}`` 被原样写盘，lint（只做文本扫描）
通过，但导入时抛 ``TypeError: unhashable type: 'dict'``。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sllkgui.gallery.manifest import load_manifest
from sllkgui.gallery.scaffold import scaffold_plugin


def test_scaffold_entry_is_importable(tmp_path: Path):
    root = scaffold_plugin(tmp_path / "sample", plugin_id="com.example.sample", name="Sample")

    module_name = "sllkgui_scaffold_probe"
    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "plugin.py",
        submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # {{...}} 会在这里炸

    plugin = module.PLUGIN
    assert set(plugin.surfaces()) == {"home"}


def test_scaffold_manifest_declares_existing_impl(tmp_path: Path):
    root = scaffold_plugin(tmp_path / "sample", plugin_id="com.example.sample", name="Sample")
    manifest = load_manifest(root)

    surface = manifest.surface("home")
    assert surface is not None
    assert surface.impl == "pages/home.py"
    assert (root / surface.impl).is_file()
