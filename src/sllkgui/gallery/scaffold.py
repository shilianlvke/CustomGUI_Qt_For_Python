"""``sllkgui scaffold``：生成可直接通过 lint 的插件/源仓库模板。"""

from __future__ import annotations

from pathlib import Path

from .errors import PLUGIN_ID_INVALID, GalleryError

_PLUGIN_YML = """schema: 1
api: 1

id: {plugin_id}
name: {name}
version: 0.1.0
description: {name} 插件
license: MIT
entry: plugin.py

requires:
  sllkgui: ">=2.0.0,<3.0.0"
  python: ">=3.12"

surfaces:
  - id: home
    title:
      zh_cn: {name}
      zh_tw: {name}
      en_us: {name}
      ja_jp: {name}
    icon: resource/icon/home.svg
    default: true
    order: 10

permissions:
  - filesystem.write
"""

_PLUGIN_PY = '''"""插件入口：唯一合法导出是 ``PLUGIN`` 实例。"""

from __future__ import annotations

from sllkgui.plugin import GalleryContext, Plugin


def build_home(ctx: GalleryContext):
    from .pages.home import HomePage

    with ctx.timing("home.surface.build"):
        page = HomePage(ctx)
    ctx.event("surface.ready", {{"surface": "home"}})
    return page


class SamplePlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading sample plugin")
        with ctx.timing("sample.load"):
            self.data_file = ctx.data_dir / "state.json"
        ctx.event("sample.loaded")

    def surfaces(self):
        return {{"home": build_home}}

    def on_unload(self) -> None:
        self.ctx.log("unloading sample plugin")
        self.ctx.event("sample.unloaded")


PLUGIN = SamplePlugin()
'''

_HOME_PAGE = '''"""首页：最小可运行 Surface。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from sllkgui.plugin import GalleryContext


class HomePage(QWidget):
    def __init__(self, ctx: GalleryContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(ctx.text("home.title", "Hello SllkGUI")))
'''

_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <rect x="3" y="3" width="18" height="18" rx="4"/>
  <path d="M8 12h8M12 8v8"/>
</svg>
"""

_LANG = {
    "zh_cn": "home:\n  title: 示例插件\n",
    "zh_tw": "home:\n  title: 範例外掛\n",
    "en_us": "home:\n  title: Sample Plugin\n",
    "ja_jp": "home:\n  title: サンプルプラグイン\n",
}

_README = """# {name}

SllkGUI 插件模板。

## 功能

- 一个最小 Surface（`home`）
- 日志/遥测全部接入基座：`ctx.log` / `ctx.event` / `ctx.timing`

## 权限

- `filesystem.write`：仅写入 `ctx.data_dir`

## 数据位置

`ctx.data_dir`（卸载默认保留，`--purge` 才删除）。

## 事件表

| 事件 | 时机 |
| --- | --- |
| `sample.loaded` | 插件加载完成 |
| `sample.unloaded` | 插件卸载 |
| `surface.ready` | Surface 构建完成 |

## 开发

```bash
sllkgui plugin lint .
sllkgui run --plugin-dir ../
```
"""

_LICENSE = """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

_SOURCE_YAML = """schema: 1
id: {source_id}
name: {source_name}
description: 自建 SllkGUI 插件源
maintainers:
  - {maintainer}
homepage: {homepage}
updated_at: {updated_at}
"""

_ENTRY_YAML = """schema: 1
id: {plugin_id}
name: {name}
summary: {name} 插件
description: |
  由 sllkgui scaffold 生成的源条目模板。
author: {author}
license: MIT
repository: {repository}
categories:
  - tools
icon: icon.svg
compliance: 1

versions:
  - version: 0.1.0
    ref: v0.1.0
    commit: 0000000000000000000000000000000000000000
    manifest_sha256: 0000000000000000000000000000000000000000000000000000000000000000
    api: 1
    sllkgui: ">=2.0.0,<3.0.0"
    python: ">=3.12"
    permissions:
      - filesystem.write
    yanked: false
"""


def scaffold_plugin(
    dest: Path,
    plugin_id: str = "com.example.sample",
    name: str = "Sample",
    *,
    author: str = "example",
) -> Path:
    if not plugin_id or not plugin_id.replace(".", "").replace("-", "").replace("_", "").isalnum():
        raise GalleryError(PLUGIN_ID_INVALID, f"非法插件 id: {plugin_id!r}")
    root = Path(dest).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise GalleryError(PLUGIN_ID_INVALID, f"目标目录非空: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "pages").mkdir(exist_ok=True)
    (root / "resource" / "icon").mkdir(parents=True, exist_ok=True)
    (root / "resource" / "lang").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)

    (root / "sllkgui-plugin.yml").write_text(
        _PLUGIN_YML.format(plugin_id=plugin_id, name=name), encoding="utf-8"
    )
    (root / "plugin.py").write_text(_PLUGIN_PY, encoding="utf-8")
    (root / "pages" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pages" / "home.py").write_text(_HOME_PAGE, encoding="utf-8")
    (root / "resource" / "icon" / "home.svg").write_text(_ICON, encoding="utf-8")
    for locale, text in _LANG.items():
        (root / "resource" / "lang" / f"{locale}.yml").write_text(text, encoding="utf-8")
    (root / "README.md").write_text(_README.format(name=name), encoding="utf-8")
    (root / "LICENSE").write_text(_LICENSE.format(year=2026, author=author), encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0\n\n- 初始版本\n", encoding="utf-8")
    (root / "tests" / "test_smoke.py").write_text(
        "def test_manifest_exists():\n    from pathlib import Path\n\n    assert (Path(__file__).parents[1] / 'sllkgui-plugin.yml').is_file()\n",
        encoding="utf-8",
    )
    return root


def scaffold_source(
    dest: Path,
    *,
    source_id: str = "my-team",
    source_name: str = "My SllkGUI Source",
    maintainer: str = "maintainer",
    homepage: str = "https://gitee.com/example/sllkgui-source",
    plugin_id: str = "com.example.sample",
    plugin_name: str = "Sample",
    repository: str = "https://gitee.com/example/sllkgui-sample.git",
) -> Path:
    root = Path(dest).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise GalleryError(PLUGIN_ID_INVALID, f"目标目录非空: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "schema").mkdir(exist_ok=True)
    (root / "plugins" / plugin_id).mkdir(parents=True, exist_ok=True)
    (root / "source.yaml").write_text(
        _SOURCE_YAML.format(
            source_id=source_id,
            source_name=source_name,
            maintainer=maintainer,
            homepage=homepage,
            updated_at="2026-11-12",
        ),
        encoding="utf-8",
    )
    (root / "categories.yaml").write_text(
        "categories:\n  - productivity\n  - tools\n  - system\n  - development\n  - media\n  - utilities\n",
        encoding="utf-8",
    )
    (root / "plugins" / plugin_id / "entry.yaml").write_text(
        _ENTRY_YAML.format(
            plugin_id=plugin_id,
            name=plugin_name,
            author=maintainer,
            repository=repository,
        ),
        encoding="utf-8",
    )
    (root / "plugins" / plugin_id / "icon.svg").write_text(_ICON, encoding="utf-8")
    (root / "README.md").write_text(
        f"# {source_name}\n\nSllkGUI 插件源模板。提交插件请参考 CONTRIBUTING.md。\n",
        encoding="utf-8",
    )
    (root / "CONTRIBUTING.md").write_text(
        "# 提交插件\n\n1. 在插件仓库打 SemVer tag；\n2. 在 `plugins/<id>/entry.yaml` 填写版本、commit 与 manifest_sha256；\n3. 运行 `sllkgui plugin lint <插件仓库>`；\n4. 提交 PR 等待审核。\n",
        encoding="utf-8",
    )
    return root


__all__ = ["scaffold_plugin", "scaffold_source"]
