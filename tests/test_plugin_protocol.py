from AppCore import CommandPlugin, MenuPlugin, PagePlugin, get_plugin_registry
from AppCore.SYS.module.error_module import DomainErrorBoundary


def test_plugin_registry_page_menu_command_flow():
    registry = get_plugin_registry(reset=True)

    registry.register_page(
        PagePlugin(
            plugin_id="test.page.demo",
            button_id="btn_demo",
            page_object="demo_page",
            title_getter=lambda language: "Demo",
        )
    )
    registry.register_menu(
        MenuPlugin(
            plugin_id="test.menu.demo",
            target="LeftMenu",
            item={
                "btn_icon": "icon_home",
                "btn_id": "btn_demo",
                "btn_text": "Demo",
                "btn_tooltip": "Demo",
                "show_top": True,
                "is_active": False,
            },
        )
    )

    state = {"ran": False}

    def _handler(*args, **kwargs):
        state["ran"] = True

    registry.register_command(
        CommandPlugin(
            plugin_id="test.cmd.demo",
            command_id="cmd_demo",
            handler=_handler,
        )
    )

    routes = registry.build_page_routes(language=None, title_fallback=lambda _bid: "fallback")
    assert routes["btn_demo"][0] == "demo_page"

    left = registry.apply_menu_plugins([], "LeftMenu")
    assert left[0]["btn_id"] == "btn_demo"

    registry.execute_command("cmd_demo")
    assert state["ran"] is True


def test_plugin_registry_duplicate_registration_raises():
    registry = get_plugin_registry(reset=True)
    plugin = PagePlugin(
        plugin_id="dup.page",
        button_id="btn_dup",
        page_object="dup_page",
        title_getter=lambda language: "Dup",
    )

    registry.register_page(plugin)
    try:
        registry.register_page(plugin)
        raise AssertionError("Expected duplicate registration to raise")
    except DomainErrorBoundary as exc:
        assert exc.code == "PLUGIN_DUPLICATE_PAGE"


def test_plugin_lifecycle_enable_disable_and_unregister():
    registry = get_plugin_registry(reset=True)

    registry.register_command(
        CommandPlugin(
            plugin_id="test.cmd.lifecycle",
            command_id="cmd_lifecycle",
            handler=lambda *_args, **_kwargs: "ok",
        )
    )

    assert registry.execute_command("cmd_lifecycle") == "ok"

    assert registry.disable_plugin("test.cmd.lifecycle") is True
    assert registry.execute_command("cmd_lifecycle") is None

    assert registry.enable_plugin("test.cmd.lifecycle") is True
    assert registry.execute_command("cmd_lifecycle") == "ok"

    assert registry.unregister_plugin("test.cmd.lifecycle") is True
    assert registry.execute_command("cmd_lifecycle") is None


def test_plugin_protocol_version_mismatch_raises():
    registry = get_plugin_registry(reset=True)

    try:
        registry.register_page(
            PagePlugin(
                plugin_id="test.page.incompatible",
                button_id="btn_incompatible",
                page_object="page_incompatible",
                title_getter=lambda _language: "Incompatible",
                protocol_version="2",
            )
        )
        raise AssertionError("Expected unsupported protocol to raise")
    except DomainErrorBoundary as exc:
        assert exc.code == "PLUGIN_PROTOCOL_UNSUPPORTED"


def test_plugin_load_and_command_fault_isolation():
    registry = get_plugin_registry(reset=True)

    report = registry.load_plugins(
        [
            CommandPlugin(
                plugin_id="test.cmd.ok",
                command_id="cmd_ok",
                handler=lambda *_args, **_kwargs: "ok",
            ),
            CommandPlugin(
                plugin_id="test.cmd.bad",
                command_id="cmd_bad",
                handler=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            ),
        ]
    )

    assert report["loaded"] == 2
    assert report["failed"] == 0

    assert registry.execute_command("cmd_ok") == "ok"
    assert registry.execute_command("cmd_bad") is None
    assert any("test.cmd.bad" in msg for msg in registry.load_errors)


def test_page_plugin_loader_fault_isolation():
    registry = get_plugin_registry(reset=True)
    calls = []

    def _ok_loader(window):
        calls.append(("ok", window))

    def _bad_loader(_window):
        raise RuntimeError("load failed")

    registry.load_plugins(
        [
            PagePlugin(
                plugin_id="test.page.ok",
                button_id="btn_ok",
                page_object="page_ok",
                title_getter=lambda _language: "OK",
                loader=_ok_loader,
            ),
            PagePlugin(
                plugin_id="test.page.bad",
                button_id="btn_bad",
                page_object="page_bad",
                title_getter=lambda _language: "BAD",
                loader=_bad_loader,
            ),
        ]
    )

    marker = object()
    registry.load_page_plugins(marker)

    assert calls == [("ok", marker)]
    assert any("test.page.bad" in msg for msg in registry.load_errors)


def test_plugin_protocol_compatibility_helpers():
    registry = get_plugin_registry(reset=True)

    assert registry.is_protocol_supported("1") is True
    assert registry.is_protocol_supported("2") is False
    assert "1" in registry.supported_protocol_versions


def test_discover_plugin_modules_from_manifest(tmp_path):
    registry = get_plugin_registry(reset=True)
    manifest = tmp_path / "plugins.yml"
    manifest.write_text(
        """
plugin_modules:
  - demo_plugin_a
plugins:
  modules:
    - demo_plugin_b
    - demo_plugin_a
""".strip(),
        encoding="utf-8",
    )

    modules = registry.discover_plugin_modules(str(manifest))

    assert modules == ["demo_plugin_a", "demo_plugin_b"]


def test_discover_and_load_plugins_from_module_register_function(tmp_path, monkeypatch):
    registry = get_plugin_registry(reset=True)

    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    module_file = plugin_dir / "demo_plugin.py"
    module_file.write_text(
        """
from AppCore import CommandPlugin


def register_plugins(registry):
    registry.register_command(
        CommandPlugin(
            plugin_id=\"demo.cmd\",
            command_id=\"cmd_demo\",
            handler=lambda *_args, **_kwargs: \"ok\",
        )
    )
""".strip(),
        encoding="utf-8",
    )

    manifest = tmp_path / "plugins.yml"
    manifest.write_text("plugin_modules:\n  - demo_plugin\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(plugin_dir))

    report = registry.discover_and_load_plugins(str(manifest))

    assert report["modules_loaded"] == 1
    assert registry.execute_command("cmd_demo") == "ok"


def test_load_plugins_from_module_missing_entry_records_error(tmp_path, monkeypatch):
    registry = get_plugin_registry(reset=True)

    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    module_file = plugin_dir / "bad_plugin.py"
    module_file.write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(plugin_dir))

    report = registry.load_plugins_from_modules(["bad_plugin"])

    assert report["modules_failed"] == 1
    assert any("bad_plugin" in msg for msg in registry.load_errors)


def test_plugin_protocol_adapter_migrates_legacy_plugin():
    registry = get_plugin_registry(reset=True)

    registry.register_protocol_adapter(
        "0",
        lambda plugin: CommandPlugin(
            plugin_id=plugin.plugin_id,
            command_id=plugin.command_id,
            handler=plugin.handler,
            enabled=plugin.enabled,
            protocol_version="1",
        ),
    )

    legacy = CommandPlugin(
        plugin_id="legacy.cmd",
        command_id="cmd_legacy",
        handler=lambda *_args, **_kwargs: "legacy-ok",
        protocol_version="0",
    )
    registry.register_command(legacy)

    assert registry.execute_command("cmd_legacy") == "legacy-ok"


def test_plugin_protocol_adapter_failure_raises_boundary():
    registry = get_plugin_registry(reset=True)

    registry.register_protocol_adapter("0", lambda _plugin: (_ for _ in ()).throw(RuntimeError("cannot adapt")))

    legacy = CommandPlugin(
        plugin_id="legacy.bad",
        command_id="cmd_legacy_bad",
        handler=lambda *_args, **_kwargs: None,
        protocol_version="0",
    )

    try:
        registry.register_command(legacy)
        raise AssertionError("Expected protocol adapt failure")
    except DomainErrorBoundary as exc:
        assert exc.code == "PLUGIN_PROTOCOL_ADAPT_FAILED"
