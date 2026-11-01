"""Apps 应用模组加载器测试（使用临时 Apps 目录注入）。"""

import os
from pathlib import Path

import pytest

from customgui.appcore import Attrs, Language, PluginRegistry
from customgui.guis.app_loader import (
    AppContext,
    apply_apps_language,
    discover_app_dirs,
    load_app_manifest,
    load_apps,
    register_app,
    reset_apps_cache,
)


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app

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
from customgui.appcore import CommandPlugin


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

    from customgui.appcore import get_plugin_registry

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


def test_app_relative_import_of_user_lib_directory(apps_root, qapp):
    """App 内部自定义逻辑目录（lib）可通过相对导入使用。

    ``lib/__init__.py`` 里的 ``from ..calc import add`` 要求：
    - ``_customgui_apps.demo`` 是包（``__path__`` 指向应用目录）；
    - ``calc.py`` 位于 ``<app>/calc.py``。
    """
    app_dir = apps_root / "demo"
    _write_app(app_dir, page_code=None)
    (app_dir / "lib").mkdir(parents=True, exist_ok=True)
    (app_dir / "lib" / "__init__.py").write_text("from ..calc import add\n__all__ = ['add']\n", encoding="utf-8")
    (app_dir / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (app_dir / "gui" / "main.py").write_text(
        '''
from PySide6.QtWidgets import QLabel, QWidget

from ..lib import add


def build_page(app):
    page = QWidget()
    page.setObjectName(app.config.get("page_object") or "demoPage")
    page.result_label = QLabel(str(add(1, 2)))
    return page
''',
        encoding="utf-8",
    )

    registry = PluginRegistry()
    context = register_app(app_dir, registry=registry)

    pages = registry.page_plugins()
    assert len(pages) == 1

    # 调用 build_page：内部相对导入 lib 成功，页面构建成功
    class _Pages:
        def addWidget(self, _widget):
            pass

    class _Ui:
        load_pages = type("Pages", (), {"pages": _Pages()})()

    class _Window:
        ui = _Ui()

    pages[0].loader(_Window())
    assert context is not None


# ==========================================================================
# 插件协议 v2：AppPlugin / AppPage
# ==========================================================================
V2_PLUGIN_CODE = """
from customgui.appcore import AppPage, AppPlugin


class DemoPlugin(AppPlugin):
    def on_load(self, ctx):
        self.loaded_ctx = ctx
        self.hooks = ["load"]

    def pages(self):
        return [
            AppPage(
                button_id="btn_alpha",
                page_object="pageAlpha",
                build=lambda ctx, window: _page("pageAlpha", ctx),
                title_key="language.app.demo.alpha",
                default=True,
            ),
            AppPage(
                button_id="btn_beta",
                page_object="pageBeta",
                build=lambda ctx, window: _page("pageBeta", ctx),
                title_key="language.app.demo.beta",
                show_top=True,
            ),
            AppPage(
                button_id="btn_gamma",
                page_object="pageGamma",
                build=lambda ctx, window: _page("pageGamma", ctx),
                title_key="language.app.demo.gamma",
                show_top=False,
            ),
        ]


def _page(name, ctx):
    from PySide6.QtWidgets import QWidget

    page = QWidget()
    page.seen_ctx = ctx
    return page


PLUGIN = DemoPlugin()
"""

V2_CLASS_ONLY_CODE = """
from customgui.appcore import AppPage, AppPlugin


class SoloPlugin(AppPlugin):
    def pages(self):
        from PySide6.QtWidgets import QWidget

        return [AppPage("btn_solo", "pageSolo", lambda ctx, window: QWidget())]
"""


def _window_stub():
    added = []

    class _Pages:
        def addWidget(self, widget):
            added.append(widget)

    class _Ui:
        load_pages = type("Pages", (), {"pages": _Pages()})()

    class _Window:
        ui = _Ui()

    return _Window(), added


def test_v2_plugin_registers_declared_pages(apps_root):
    """v2 应用按下单顺序注册页面，show_top=False 的页面不注册菜单。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\n')

    registry = PluginRegistry()
    handle = register_app(app_dir, registry=registry, with_handle=True)

    pages = registry.page_plugins()
    assert [page.page_object for page in pages] == ["pageAlpha", "pageBeta", "pageGamma"]
    assert [page.button_id for page in pages] == ["btn_alpha", "btn_beta", "btn_gamma"]
    assert pages[0].default is True
    assert pages[1].default is False

    menus = [plugin_id for plugin_id in registry._menus]
    assert "app.menu.demo.btn_alpha" in menus
    assert "app.menu.demo.btn_beta" in menus
    # show_top=False 的页面不该出现在菜单里
    assert "app.menu.demo.btn_gamma" not in menus

    assert handle.plugin is not None
    assert handle.plugin.loaded_ctx is handle.context


def test_v2_on_load_receives_context_before_pages(apps_root):
    """``on_load`` 在页面构建之前调用，且拿到同一个 ctx。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\n')

    handle = register_app(app_dir, registry=PluginRegistry(), with_handle=True)

    assert handle.plugin.hooks == ["load"]
    assert handle.plugin.ctx is handle.context
    assert handle.plugin.name == "demo"


def test_v2_loader_stacks_page_and_sets_object_name(apps_root):
    """**基座负责** setObjectName 与 addWidget，应用只管 build。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\n')

    registry = PluginRegistry()
    register_app(app_dir, registry=registry)
    page_plugin = registry.page_plugins()[1]  # pageBeta

    window, added = _window_stub()
    page_plugin.loader(window)

    assert len(added) == 1
    assert added[0].objectName() == "pageBeta"
    assert added[0].seen_ctx is not None


def test_v2_page_title_resolution(apps_root):
    """``title_key`` 走语言解析；缺失时回落为键名本身。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\n')

    registry = PluginRegistry()
    register_app(app_dir, registry=registry)
    page_plugin = registry.page_plugins()[0]

    title = page_plugin.title_getter(Language)
    assert isinstance(title, str)
    assert title  # 无论命中与否都要有可显示文本


def test_v2_class_only_entry_is_instantiated(apps_root):
    """模块里只有一个 AppPlugin 子类时自动实例化（约定优于配置）。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_CLASS_ONLY_CODE, 'protocol: 2\n')

    registry = PluginRegistry()
    handle = register_app(app_dir, registry=registry, with_handle=True)

    assert handle.plugin is not None
    assert handle.plugin.__class__.__name__ == "SoloPlugin"
    assert len(registry.page_plugins()) == 1


def test_v2_manifest_can_name_the_plugin_symbol(apps_root):
    """清单 ``plugin`` 字段可显式指定入口符号。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_CLASS_ONLY_CODE, 'protocol: 2\nplugin: SoloPlugin\n')

    handle = register_app(app_dir, registry=PluginRegistry(), with_handle=True)
    assert handle.plugin.__class__.__name__ == "SoloPlugin"


def test_v2_without_plugin_class_raises(apps_root):
    """protocol=2 但入口没有 AppPlugin 时必须报错，而不是静默不显示页面。"""
    from customgui.appcore import AppPluginError

    app_dir = apps_root / "demo"
    _write_app(app_dir, PAGE_CODE, 'protocol: 2\n')

    with pytest.raises(AppPluginError) as excinfo:
        register_app(app_dir, registry=PluginRegistry())
    assert excinfo.value.code == "APP_PLUGIN_MISSING"


def test_unsupported_protocol_version_raises(apps_root):
    from customgui.appcore import AppPluginError

    app_dir = apps_root / "demo"
    _write_app(app_dir, PAGE_CODE, 'protocol: "9"\n')

    with pytest.raises(AppPluginError) as excinfo:
        register_app(app_dir, registry=PluginRegistry())
    assert excinfo.value.code == "APP_PROTOCOL_UNSUPPORTED"


def test_core_dir_missing_raises(apps_root):
    from customgui.appcore import AppPluginError

    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\ncore: launchercore\n')

    with pytest.raises(AppPluginError) as excinfo:
        register_app(app_dir, registry=PluginRegistry())
    assert excinfo.value.code == "APP_CORE_MISSING"


def test_core_dir_exposed_on_context(apps_root):
    """声明并创建 core 目录后，``ctx.core_dir`` 指向它。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\ncore: launchercore\n')
    core = app_dir / "launchercore"
    core.mkdir()
    (core / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")

    context = register_app(app_dir, registry=PluginRegistry())

    assert context.core_name == "launchercore"
    assert context.core_dir == core
    module = context.import_module("launchercore")
    assert module.VALUE == 42


def test_app_name_mismatch_raises(apps_root):
    """目录名与 app_name 不一致必须显式报错（否则应用内导入会静默失效）。"""
    from customgui.appcore import AppPluginError

    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\n')
    (app_dir / "config.yml").write_text(
        (app_dir / "config.yml").read_text(encoding="utf-8").replace(
            'app_name: "demo"', 'app_name: "other"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(AppPluginError) as excinfo:
        register_app(app_dir, registry=PluginRegistry())
    assert excinfo.value.code == "APP_NAME_MISMATCH"


def test_context_import_module_uses_app_namespace(apps_root):
    """``ctx.import_module`` 让调用方不必知道私有命名空间的存在。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, 'protocol: 2\n')
    (app_dir / "helper").mkdir()
    (app_dir / "helper" / "__init__.py").write_text("GREETING = 'hi'\n", encoding="utf-8")

    context = register_app(app_dir, registry=PluginRegistry())

    assert context.module_name is not None
    module = context.import_module("helper")
    assert module.GREETING == "hi"


def test_v1_apps_still_work_without_protocol_field(apps_root):
    """v1 应用清单没有 ``protocol`` 字段，必须照旧工作（回归门禁）。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, PAGE_CODE)  # 不传 config_extra

    registry = PluginRegistry()
    context = register_app(app_dir, registry=registry)

    assert context.icon_path is not None
    assert context.icon_path.is_file()
    assert len(registry.page_plugins()) == 1
    assert registry.page_plugins()[0].plugin_id == "app.page.demo"


def test_context_icon_path_is_none_when_missing(apps_root):
    """没有图标文件时 ``icon_path`` 为 ``None``，而不是空 ``Path``。"""
    app_dir = apps_root / "demo"
    _write_app(app_dir, BUILD_PAGE_CODE, 'protocol: 1\n')
    (app_dir / "resource" / "icon" / "app_icon.svg").unlink()

    context = register_app(app_dir, registry=PluginRegistry())

    assert context.icon_path is None


# ==========================================================================
# 命名空间 Finder：多个应用并存时不串台
# ==========================================================================
def test_multiple_apps_do_not_share_modules(apps_root):
    """两个应用的内部模块必须各走各的目录，不能串台。"""
    for name, value in (("alpha", 1), ("beta", 2)):
        app_dir = apps_root / name
        (app_dir / "gui").mkdir(parents=True)
        (app_dir / "resource" / "icon").mkdir(parents=True)
        (app_dir / "resource" / "lang").mkdir(parents=True)
        (app_dir / "shared").mkdir()
        (app_dir / "shared" / "__init__.py").write_text(f"VALUE = {value}\n", encoding="utf-8")
        (app_dir / "gui" / "main.py").write_text(
            """
from customgui.appcore import AppPage, AppPlugin


class P(AppPlugin):
    def pages(self):
        from PySide6.QtWidgets import QWidget

        from ..shared import VALUE
        return [AppPage("btn_x", "pageX", lambda ctx, window: QWidget(), title=str(VALUE))]
""",
            encoding="utf-8",
        )
        (app_dir / "config.yml").write_text(
            f'app_name: "{name}"\nprotocol: 2\nbutton_id: "btn_x"\n', encoding="utf-8"
        )

    alpha = register_app(apps_root / "alpha", registry=PluginRegistry())
    beta = register_app(apps_root / "beta", registry=PluginRegistry())

    assert alpha.import_module("shared").VALUE == 1
    assert beta.import_module("shared").VALUE == 2
    # 两个模块是不同对象，不是缓存串台
    assert alpha.import_module("shared") is not beta.import_module("shared")


def test_namespace_finder_is_installed_once(apps_root):
    """Finder 全局唯一，多次加载应用不能重复插进 meta_path。"""
    import sys

    from customgui.guis.app_loader import _NamespacePackageFinder

    app_dir = apps_root / "demo"
    _write_app(app_dir, V2_PLUGIN_CODE, "protocol: 2\n")
    for _ in range(3):
        register_app(app_dir, registry=PluginRegistry())

    finders = [f for f in sys.meta_path if isinstance(f, _NamespacePackageFinder)]
    assert len(finders) == 1


def test_namespace_finder_ignores_foreign_modules(apps_root):
    """Finder 只处理自己的私有命名空间，不能拦截常规导入。"""
    from customgui.guis.app_loader import _APP_NAMESPACE, _NamespacePackageFinder

    finder = _NamespacePackageFinder()
    assert finder.find_spec("json") is None
    assert finder.find_spec("customgui.appcore") is None
    assert finder.find_spec(_APP_NAMESPACE) is None  # 根命名空间本身不处理


def test_unknown_app_module_returns_none(apps_root):
    """未登记的应用名不应被 Finder 命中（返回 None 而不是乱猜路径）。"""
    from customgui.guis.app_loader import _APP_NAMESPACE, _NamespacePackageFinder

    finder = _NamespacePackageFinder()
    assert finder.find_spec(f"{_APP_NAMESPACE}.never_registered.something") is None
