from __future__ import annotations

from pathlib import Path

from gallery_helpers import write_plugin

from sllkgui.gallery.lint import lint_plugin

BAD_PLUGIN = '''from sllkgui.plugin import GalleryContext, Plugin


def build_home(ctx):
    print("hello")
    return None


class Bad(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        pass

    def surfaces(self):
        return {"home": build_home}


PLUGIN = Bad()
'''

BAD_MANIFEST = """schema: 1
api: 1
id: com.example.bad
name: Bad
version: 1.0.0
entry: plugin.py
surfaces:
  - id: home
    title: {en_us: Home}
    icon: resource/icon/home.svg
permissions: []
"""


def test_lint_rejects_print_and_missing_telemetry(tmp_path: Path, monkeypatch):
    root = write_plugin(tmp_path / "bad", manifest_text=BAD_MANIFEST, plugin_source=BAD_PLUGIN)
    report = lint_plugin(root)
    codes = {item.code for item in report.warnings} | {item.code for item in report.errors}
    assert report.ok is False
    assert "PRINT" in codes
    assert "TELEMETRY_LOG" in codes
    assert "TELEMETRY_EVENT" in codes
    assert "TELEMETRY_TIMING" in codes


def test_lint_rejects_missing_language(tmp_path: Path):
    root = write_plugin(tmp_path / "hello")
    (root / "resource" / "lang" / "ja_jp.yml").unlink()
    report = lint_plugin(root)
    assert any(item.code == "I18N_MISSING" for item in report.errors)
    assert report.ok is False


def test_lint_accepts_compliant_plugin(tmp_path: Path):
    root = write_plugin(tmp_path / "hello")
    report = lint_plugin(root)
    assert report.ok is True, report.to_dict()
    assert report.plugin_id == "com.example.hello"


def test_scaffold_is_compliant(tmp_path: Path):
    from sllkgui.gallery.scaffold import scaffold_plugin

    root = scaffold_plugin(tmp_path / "sample", plugin_id="com.example.sample", name="Sample")
    report = lint_plugin(root)
    assert report.ok is True, report.to_dict()


def test_scaffold_source_template(tmp_path: Path):
    from sllkgui.gallery.scaffold import scaffold_source

    root = scaffold_source(tmp_path / "source", source_id="my-team", plugin_id="com.example.sample")
    assert (root / "source.yaml").is_file()
    assert (root / "categories.yaml").is_file()
    assert (root / "plugins" / "com.example.sample" / "entry.yaml").is_file()
    assert (root / "CONTRIBUTING.md").is_file()
