"""Gallery 测试辅助：生成最小合规插件、源条目与本地 Git 仓库。"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import yaml

ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24"/></svg>'

MANIFEST = """schema: 1
api: 1
id: {plugin_id}
name: {name}
version: {version}
description: test plugin
license: MIT
entry: plugin.py
requires:
  sllkgui: ">=2.0.0,<3.0.0"
  python: ">=3.12"
surfaces:
  - id: home
    title:
      zh_cn: 首页
      zh_tw: 首頁
      en_us: Home
      ja_jp: ホーム
    icon: resource/icon/home.svg
    default: true
    order: 10
permissions:
  - filesystem.write
"""

PLUGIN = '''"""Test plugin."""

from sllkgui.plugin import GalleryContext, Plugin


def build_home(ctx: GalleryContext):
    from PySide6.QtWidgets import QLabel

    with ctx.timing("home.build"):
        page = QLabel(ctx.text("home.title", "Home"))
    ctx.event("surface.ready", {"surface": "home"})
    return page


class HelloPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading hello")
        with ctx.timing("hello.load"):
            self.data = ctx.data_dir
        ctx.event("hello.loaded")

    def surfaces(self):
        return {"home": build_home}

    def on_unload(self) -> None:
        self.ctx.log("unloading hello")
        self.ctx.event("hello.unloaded")


PLUGIN = HelloPlugin()
'''

LANG = {
    "zh_cn": "home:\n  title: 首页\n",
    "zh_tw": "home:\n  title: 首頁\n",
    "en_us": "home:\n  title: Home\n",
    "ja_jp": "home:\n  title: ホーム\n",
}


def write_plugin(
    root: Path,
    plugin_id: str = "com.example.hello",
    version: str = "1.0.0",
    *,
    name: str = "Hello",
    plugin_source: str | None = None,
    manifest_text: str | None = None,
) -> Path:
    root = Path(root)
    (root / "resource" / "icon").mkdir(parents=True, exist_ok=True)
    (root / "resource" / "lang").mkdir(parents=True, exist_ok=True)
    (root / "sllkgui-plugin.yml").write_text(
        manifest_text or MANIFEST.format(plugin_id=plugin_id, name=name, version=version),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(plugin_source or PLUGIN, encoding="utf-8")
    (root / "resource" / "icon" / "home.svg").write_text(ICON, encoding="utf-8")
    for locale, text in LANG.items():
        (root / "resource" / "lang" / f"{locale}.yml").write_text(text, encoding="utf-8")
    return root


def manifest_sha256(root: Path) -> str:
    raw = (Path(root) / "sllkgui-plugin.yml").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def init_repo(root: Path, tag: str = "v1.0.0") -> str:
    root = Path(root)
    if not (root / ".git").exists():
        git("init", "-q", cwd=root)
        git("config", "user.email", "test@example.com", cwd=root)
        git("config", "user.name", "Test", cwd=root)
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "init", cwd=root)
    git("tag", tag, cwd=root)
    return git("rev-parse", "HEAD", cwd=root)


def write_entry(
    source_root: Path,
    plugin_repo: Path,
    *,
    source_id: str = "test",
    plugin_id: str = "com.example.hello",
    version: str = "1.0.0",
    ref: str = "v1.0.0",
    commit: str = "",
    sha: str = "",
    yanked: bool = False,
) -> Path:
    entry_dir = Path(source_root) / "plugins" / plugin_id
    entry_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "id": plugin_id,
        "name": "Hello",
        "summary": "test plugin",
        "description": "test",
        "author": "tester",
        "license": "MIT",
        "repository": plugin_repo.resolve().as_uri(),
        "categories": ["tools"],
        "compliance": 1,
        "versions": [
            {
                "version": version,
                "ref": ref,
                "commit": commit or git("rev-parse", "HEAD", cwd=plugin_repo),
                "manifest_sha256": sha or manifest_sha256(plugin_repo),
                "api": 1,
                "sllkgui": ">=2.0.0,<3.0.0",
                "python": ">=3.12",
                "permissions": ["filesystem.write"],
                "yanked": yanked,
            }
        ],
    }
    (entry_dir / "entry.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (entry_dir / "icon.svg").write_text(ICON, encoding="utf-8")
    return entry_dir


def write_source(source_root: Path, *, source_id: str = "test") -> Path:
    source_root = Path(source_root)
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "source.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": 1,
                "id": source_id,
                "name": "Test Source",
                "description": "test",
                "maintainers": ["tester"],
                "updated_at": "2026-11-12",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (source_root / "categories.yaml").write_text("categories:\n  - tools\n", encoding="utf-8")
    return source_root
