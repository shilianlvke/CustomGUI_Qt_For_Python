"""Apps 应用模组加载器测试（使用临时 Apps 目录注入）。"""

from pathlib import Path

import pytest

from AppCore import Attrs, Language, PluginRegistry
from Guis.app_loader import (
    AppContext,
    apply_apps_language,
    discover_app_dirs,
    load_app_manifest,
    load_apps,
    register_app,
    reset_apps_cache,
)

PAGE_CODE = """
from PySide6.QtWidgets import QWidget


class DemoPage:
    def load_page(self):
        page = QWidget()
        page.setObjectName("demoPage")
        self.ui.load_pages.pages.addWidget(page)
        return page


PAGE = DemoPage
"""

BUILD_PAGE_CODE = """
from PySide6.QtWidgets import QLabel, QWidget


def build_page(app):
    page = QWidget()
    page.setObjectName(app.config.get("page_object") or "buildPage")
    return page
"""

REGISTER_PLUGINS_CODE = """
from AppCore import CommandPlugin


def register_plugins(registry, app):
    registry.register_command(
        CommandPlugin(
            plugin_id=f"app.cmd.{app.name}",
            command_id=f"cmd_{app.name}",
            handler=lambda *args, **kwargs: app.name,
        )
    )
"""


@pytest.fixture
def apps_root(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMGUI_APPS_DIR", str(tmp_path))
    reset_apps_cache()
    return tmp_path


def _write_app(app_dir: Path, page_code: str | None = None, config_extra: str = ""):
    (app_dir / "gui").mkdir(parents=True, exist_ok=True)
    (app_dir / "resource" / "icon").mkdir(parents=True, exist_ok=True)
    (app_dir / "resource" / "lang").mkdir(parents=True, exist_ok=True)
    (app_dir / "resource" / "icon" / "app_icon.svg").write_text("<svg/>", encoding="utf-8")
    (app_dir / "resource" / "lang" / "zh_cn.yml").write_text(
        'app_text: "演示应用"\napp_tooltip: "演示提示"\n', encoding="utf-8"
    )
    (app_dir / "resource" / "lang" / "en_us.yml").write_text(
        'app_text: "Demo App"\napp_tooltip: "Demo tooltip"\n', encoding="utf-8"
    )
    if page_code is not None:
        (app_dir / "gui" / "main.py").write_text(page_code, encoding="utf-8")

    name = app_dir.name
    config = f'''app_name: "{name}"
app_id: "app.menu.left.{name}"
button_id: "btn_{name}"
page_object: "{name}Page"
app_icon: "icon.app.{name}.app_icon"
app_text: "language.app.{name}.app_text"
app_tooltip: "language.app.{name}.app_tooltip"
app_target: "LeftMenu"
show_top: true
is_active: false
{config_extra}
'''
    (app_dir / "config.yml").write_text(config, encoding="utf-8")


def test_discover_and_manifest(apps_root):
    app_dir = apps_root / "demo"
    _write_app(app_dir, PAGE_CODE)

    dirs = discover_app_dirs()
    assert dirs == [app_dir.resolve()]

    manifest = load_app_manifest(app_dir)
    assert manifest.app_name == "demo"
    assert manifest.button_id == "btn_demo"


def test_register_app_page_protocol(apps_root):
    app_dir = apps_root / "demo"
    _write_app(app_dir, PAGE_CODE)
    registry = PluginRegistry()

    context = register_app(app_dir, registry=registry)

    assert isinstance(context, AppContext)
    # 菜单插件
    assert "app.menu.left.demo" in registry._menus
    item = registry._menus["app.menu.left.demo"].item
    assert item["btn_id"] == "btn_demo"
    assert Path(item["btn_icon"]).is_file()  # 应用内图标绝对路径
    # 页面插件
    pages = registry.page_plugins()
    assert len(pages) == 1
    assert pages[0].plugin_id == "app.page.demo"
    assert pages[0].button_id == "btn_demo"
    assert pages[0].page_object == "demoPage"


def test_register_app_build_page_protocol(apps_root):
    app_dir = apps_root / "demo"
    _write_app(app_dir, BUILD_PAGE_CODE)
    registry = PluginRegistry()

    register_app(app_dir, registry=registry)

    pages = registry.page_plugins()
    assert len(pages) == 1
    assert pages[0].plugin_id == "app.page.demo"


def test_register_app_register_plugins_protocol(apps_root):
    app_dir = apps_root / "demo"
    _write_app(app_dir, REGISTER_PLUGINS_CODE)
    registry = PluginRegistry()

    register_app(app_dir, registry=registry)

    assert registry.execute_command("cmd_demo") == "demo"


def test_apply_apps_language_switches(apps_root):
    app_dir = apps_root / "demo"
    _write_app(app_dir, PAGE_CODE)

    apply_apps_language("zh_cn", [app_dir])
    assert Language.app.demo.app_text == "演示应用"

    apply_apps_language("en_us", [app_dir])
    assert Language.app.demo.app_text == "Demo App"
    assert isinstance(Language.app, Attrs)


def test_load_apps_idempotent_and_missing_main_still_registers_menu(apps_root):
    app_dir = apps_root / "demo"
    _write_app(app_dir, page_code=None)  # 无 gui/main.py

    dirs = load_apps()
    assert dirs == [app_dir.resolve()]

    # 幂等：重复调用直接返回缓存，不重复注册
    again = load_apps()
    assert again == dirs

    from AppCore import get_plugin_registry

    registry = get_plugin_registry()
    assert "app.menu.left.demo" in registry._menus
    assert not any(plugin.plugin_id == "app.page.demo" for plugin in registry.page_plugins())


def test_manifest_defaults(apps_root):
    app_dir = apps_root / "minimal"
    (app_dir / "gui").mkdir(parents=True, exist_ok=True)
    (app_dir / "resource" / "icon").mkdir(parents=True, exist_ok=True)
    (app_dir / "resource" / "lang").mkdir(parents=True, exist_ok=True)
    (app_dir / "resource" / "icon" / "app_icon.svg").write_text("<svg/>", encoding="utf-8")
    (app_dir / "config.yml").write_text('app_name: "minimal"\napp_target: "LeftMenu"\n', encoding="utf-8")
    (app_dir / "gui" / "main.py").write_text(PAGE_CODE, encoding="utf-8")

    registry = PluginRegistry()
    register_app(app_dir, registry=registry)

    item = registry._menus["app.menu.leftmenu.minimal"].item
    assert item["btn_id"] == "app_minimal"
    assert item["btn_text"] == "language.app.minimal.app_text"
    pages = registry.page_plugins()
    assert pages[0].page_object == "minimalPage"
