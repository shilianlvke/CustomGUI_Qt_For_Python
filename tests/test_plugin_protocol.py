"""模块说明。"""

from pathlib import Path

import pytest

from AppCore import CommandPlugin, MenuPlugin, PagePlugin, get_plugin_registry
from AppCore.SYS.module.error_module import DomainErrorBoundary


def test_plugin_registry_page_menu_command_flow() -> None:
    """测试用例：test_plugin_registry_page_menu_command_flow。

    职责:
    - 验证目标行为符合预期。
    """
    registry = get_plugin_registry(reset=True)

    registry.register_page(
        PagePlugin(
            plugin_id="test.page.demo",
            button_id="btn_demo",
            page_object="demo_page",
            title_getter=lambda _language: "Demo",
        ),
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
        ),
    )

    state = {"ran": False}

    def _handler(*_args: object, **_kwargs: object) -> None:
        """函数：_handler。"""
        state["ran"] = True

    registry.register_command(
        CommandPlugin(
            plugin_id="test.cmd.demo",
            command_id="cmd_demo",
            handler=_handler,
        ),
    )

    routes = registry.build_page_routes(language=None, title_fallback=lambda _bid: "fallback")
    if routes["btn_demo"][0] != "demo_page":
        pytest.fail("Assertion failed")

    left = registry.apply_menu_plugins([], "LeftMenu")
    if left[0]["btn_id"] != "btn_demo":
        pytest.fail("Assertion failed")

    registry.execute_command("cmd_demo")
    if state["ran"] is not True:
        pytest.fail("Assertion failed")


def test_plugin_registry_duplicate_registration_raises() -> None:
    """测试用例：test_plugin_registry_duplicate_registration_raises。"""
    registry = get_plugin_registry(reset=True)
    plugin = PagePlugin(
        plugin_id="dup.page",
        button_id="btn_dup",
        page_object="dup_page",
        title_getter=lambda _language: "Dup",
    )

    registry.register_page(plugin)
    with pytest.raises(DomainErrorBoundary) as exc_info:
        registry.register_page(plugin)
    if exc_info.value.code != "PLUGIN_DUPLICATE_PAGE":
        pytest.fail("Assertion failed")


def test_plugin_lifecycle_enable_disable_and_unregister() -> None:
    """测试用例：test_plugin_lifecycle_enable_disable_and_unregister。"""
    registry = get_plugin_registry(reset=True)

    registry.register_command(
        CommandPlugin(
            plugin_id="test.cmd.lifecycle",
            command_id="cmd_lifecycle",
            handler=lambda *_args, **_kwargs: "ok",
        ),
    )

    if registry.execute_command("cmd_lifecycle") != "ok":
        pytest.fail("Assertion failed")

    if registry.disable_plugin("test.cmd.lifecycle") is not True:
        pytest.fail("Assertion failed")
    if registry.execute_command("cmd_lifecycle") is not None:
        pytest.fail("Assertion failed")

    if registry.enable_plugin("test.cmd.lifecycle") is not True:
        pytest.fail("Assertion failed")
    if registry.execute_command("cmd_lifecycle") != "ok":
        pytest.fail("Assertion failed")

    if registry.unregister_plugin("test.cmd.lifecycle") is not True:
        pytest.fail("Assertion failed")
    if registry.execute_command("cmd_lifecycle") is not None:
        pytest.fail("Assertion failed")


def test_plugin_protocol_version_mismatch_raises() -> None:
    """测试用例：test_plugin_protocol_version_mismatch_raises。"""
    registry = get_plugin_registry(reset=True)

    with pytest.raises(DomainErrorBoundary) as exc_info:
        registry.register_page(
            PagePlugin(
                plugin_id="test.page.incompatible",
                button_id="btn_incompatible",
                page_object="page_incompatible",
                title_getter=lambda _language: "Incompatible",
                protocol_version="2",
            ),
        )
    if exc_info.value.code != "PLUGIN_PROTOCOL_UNSUPPORTED":
        pytest.fail("Assertion failed")


def test_plugin_load_and_command_fault_isolation() -> None:
    """测试用例：test_plugin_load_and_command_fault_isolation。"""
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
        ],
    )

    expected_loaded = 2
    if report["loaded"] != expected_loaded:
        pytest.fail("Assertion failed")
    if report["failed"] != 0:
        pytest.fail("Assertion failed")

    if registry.execute_command("cmd_ok") != "ok":
        pytest.fail("Assertion failed")
    if registry.execute_command("cmd_bad") is not None:
        pytest.fail("Assertion failed")
    if not (any("test.cmd.bad" in msg for msg in registry.load_errors)):
        pytest.fail("Assertion failed")


def test_page_plugin_loader_fault_isolation() -> None:
    """测试用例：test_page_plugin_loader_fault_isolation。"""
    registry = get_plugin_registry(reset=True)
    calls = []

    def _ok_loader(window: object) -> None:
        """函数：_ok_loader。"""
        calls.append(("ok", window))

    def _bad_loader(_window: object) -> None:
        """函数：_bad_loader。"""
        raise RuntimeError

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
        ],
    )

    marker = object()
    registry.load_page_plugins(marker)

    if calls != [("ok", marker)]:
        pytest.fail("Assertion failed")
    if not (any("test.page.bad" in msg for msg in registry.load_errors)):
        pytest.fail("Assertion failed")


def test_plugin_protocol_compatibility_helpers() -> None:
    """测试用例：test_plugin_protocol_compatibility_helpers。"""
    registry = get_plugin_registry(reset=True)

    if registry.is_protocol_supported("1") is not True:
        pytest.fail("Assertion failed")
    if registry.is_protocol_supported("2") is not False:
        pytest.fail("Assertion failed")
    if "1" not in registry.supported_protocol_versions:
        pytest.fail("Assertion failed")


def test_discover_plugin_modules_from_manifest(tmp_path: Path) -> None:
    """测试用例：test_discover_plugin_modules_from_manifest。"""
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

    if modules != ["demo_plugin_a", "demo_plugin_b"]:
        pytest.fail("Assertion failed")


def test_discover_and_load_plugins_from_module_register_function(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试用例：test_discover_and_load_plugins_from_module_register_function。"""
    registry = get_plugin_registry(reset=True)

    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    module_file = plugin_dir / "demo_plugin.py"
    module_file.write_text(
        """
from AppCore import CommandPlugin


def register_plugins(registry):
    '''函数：register_plugins。

    参数:
    - 按函数签名传入。

    返回:
    - 按函数实现返回。
    '''
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

    if report["modules_loaded"] != 1:
        pytest.fail("Assertion failed")
    if registry.execute_command("cmd_demo") != "ok":
        pytest.fail("Assertion failed")


def test_load_plugins_from_module_missing_entry_records_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试用例：test_load_plugins_from_module_missing_entry_records_error。

    职责:
    - 验证目标行为符合预期。
    """
    registry = get_plugin_registry(reset=True)

    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    module_file = plugin_dir / "bad_plugin.py"
    module_file.write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(plugin_dir))

    report = registry.load_plugins_from_modules(["bad_plugin"])

    if report["modules_failed"] != 1:
        pytest.fail("Assertion failed")
    if not (any("bad_plugin" in msg for msg in registry.load_errors)):
        pytest.fail("Assertion failed")


def test_plugin_protocol_adapter_migrates_legacy_plugin() -> None:
    """测试用例：test_plugin_protocol_adapter_migrates_legacy_plugin。"""
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

    if registry.execute_command("cmd_legacy") != "legacy-ok":
        pytest.fail("Assertion failed")


def test_plugin_protocol_adapter_failure_raises_boundary() -> None:
    """测试用例：test_plugin_protocol_adapter_failure_raises_boundary。"""
    registry = get_plugin_registry(reset=True)

    registry.register_protocol_adapter("0", lambda _plugin: (_ for _ in ()).throw(RuntimeError("cannot adapt")))

    legacy = CommandPlugin(
        plugin_id="legacy.bad",
        command_id="cmd_legacy_bad",
        handler=lambda *_args, **_kwargs: None,
        protocol_version="0",
    )

    with pytest.raises(DomainErrorBoundary) as exc_info:
        registry.register_command(legacy)
    if exc_info.value.code != "PLUGIN_PROTOCOL_ADAPT_FAILED":
        pytest.fail("Assertion failed")
