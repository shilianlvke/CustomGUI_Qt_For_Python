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


def test_lint_runs_without_qt(tmp_path):
    """插件规范校验必须能在无 PySide6 的环境运行。

    源仓库 CI 用它做插件准入，校验方不该被迫安装约 200 MB 的 GUI 依赖。
    这里拦截 ``PySide6`` 导入，若 appcore / gallery 的校验链偷偷依赖 Qt，
    导入即失败。
    """
    import builtins
    import importlib
    import sys

    for name in [key for key in sys.modules if key.startswith("sllkgui.gallery.lint")]:
        del sys.modules[name]

    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError(f"PySide6 is not available: {name}")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = guarded
    try:
        module = importlib.import_module("sllkgui.gallery.lint")
        report = module.lint_plugin(Path("examples/plugin-hello"))
        assert report.ok
    finally:
        builtins.__import__ = real_import
        for name in [key for key in sys.modules if key.startswith("sllkgui.gallery.lint")]:
            del sys.modules[name]


def test_lint_flags_absolute_import_of_local_module(tmp_path):
    """插件内对本仓库模块的绝对导入必须被指出（3.0 起不再支持）。"""
    root = tmp_path / "abs"
    root.mkdir()
    (root / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "plugin.py").write_text(
        "import helper\nfrom helper import VALUE\nimport os\n", encoding="utf-8"
    )
    (root / "sllkgui-plugin.yml").write_text(
        """schema: 1
api: 1
id: com.example.abs
name: Abs
version: 1.0.0
entry: plugin.py
requires:
  sllkgui: ">=3.0.0,<4.0.0"
surfaces:
  - id: home
    title: {en_us: Home}
""",
        encoding="utf-8",
    )

    report = lint_plugin(root)
    messages = [issue.message for issue in report.warnings if issue.code == "ABSOLUTE_IMPORT"]
    assert len(messages) == 2, messages
    assert any("import helper" in m for m in messages)


def test_lint_allows_standard_library_absolute_import(tmp_path):
    """标准库的绝对导入是正确写法，不能误报。"""
    root = tmp_path / "std"
    root.mkdir()
    (root / "plugin.py").write_text(
        "import os\nimport json\nfrom pathlib import Path\n", encoding="utf-8"
    )
    (root / "sllkgui-plugin.yml").write_text(
        """schema: 1
api: 1
id: com.example.std
name: Std
version: 1.0.0
entry: plugin.py
requires:
  sllkgui: ">=3.0.0,<4.0.0"
surfaces:
  - id: home
    title: {en_us: Home}
""",
        encoding="utf-8",
    )

    report = lint_plugin(root)
    assert not [issue for issue in report.warnings if issue.code == "ABSOLUTE_IMPORT"]
