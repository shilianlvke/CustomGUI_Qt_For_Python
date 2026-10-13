"""日志/遥测接入整合测试：验证关键路径的事件记录与故障隔离。

覆盖：
- 遥测写失败不影响主程序（尽力而为语义）；
- 插件页面/命令错误、插件模块加载汇总均记录遥测事件；
- UI 主题切换、语言切换（未实现）等交互记录遥测事件。
"""

from types import SimpleNamespace

import pytest

import AppCore.SYS.module.telemetry_module as telemetry
from AppCore import CommandPlugin, PagePlugin, PluginRegistry, record_event
from AppCore.SYS.module.telemetry_module import read_recent_events
from Guis.windows.main_window.controller import MainWindowController, ThemeController


@pytest.fixture
def diagnostics_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))
    return tmp_path


def _event_names(limit: int = 50) -> list[str]:
    return [event["name"] for event in read_recent_events(limit=limit)]


# ---------------------------------------------------------------------------
# 遥测故障隔离
# ---------------------------------------------------------------------------

def test_record_event_swallows_write_failures(diagnostics_dir, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(telemetry, "_update_metrics", _boom)

    # 写失败不得向上抛出；连续失败同样被抑制
    record_event("test.safe_event", payload={"k": "v"})
    record_event("test.safe_event_again")

    assert "test.safe_event" in _event_names()


# ---------------------------------------------------------------------------
# 插件错误路径的日志/遥测
# ---------------------------------------------------------------------------

def test_plugin_page_load_error_is_recorded(diagnostics_dir):
    registry = PluginRegistry()

    def _bad_loader(_window):
        raise RuntimeError("load failed")

    registry.register_page(
        PagePlugin(
            plugin_id="test.page.bad",
            button_id="btn_bad",
            page_object="bad_page",
            title_getter=lambda _language: "BAD",
            loader=_bad_loader,
        )
    )

    registry.load_page_plugins(None)

    assert "plugin.page_load_error" in _event_names()
    assert any("test.page.bad" in msg for msg in registry.load_errors)


def test_plugin_command_error_is_recorded(diagnostics_dir):
    registry = PluginRegistry()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    registry.register_command(
        CommandPlugin(
            plugin_id="test.cmd.bad",
            command_id="cmd_bad",
            handler=_boom,
        )
    )

    assert registry.execute_command("cmd_bad") is None
    assert registry.execute_command("cmd_missing") is None

    assert "plugin.command_error" in _event_names()


def test_plugin_modules_load_summary_is_recorded(diagnostics_dir):
    registry = PluginRegistry()

    report = registry.load_plugins_from_modules([])

    assert report["modules_loaded"] == 0
    assert "plugin.modules_loaded" in _event_names()


# ---------------------------------------------------------------------------
# UI 交互的遥测
# ---------------------------------------------------------------------------

class _StubMainFunctions:
    @staticmethod
    def get_title_bar_btn(_window, name):
        raise AttributeError(name)


def test_controller_language_switch_is_recorded(diagnostics_dir):
    from Guis.language_service import apply_language

    apply_language("zh_cn")  # 重置语言状态，确保切换方向确定

    window = SimpleNamespace(
        ui=SimpleNamespace(left_menu=SimpleNamespace(deselect_all_tab=lambda: None))
    )
    controller = MainWindowController(
        window=window,
        main_functions=_StubMainFunctions,
        plugin_registry_getter=lambda: PluginRegistry(),
        logger=SimpleNamespace(debug=lambda *_a, **_k: None, warning=lambda *_a, **_k: None),
    )
    btn = SimpleNamespace(objectName=lambda: "btn_language")

    controller.handle_button(btn)

    names = _event_names()
    assert "ui.language_switch" in names
    switch_events = [e for e in read_recent_events(limit=10) if e["name"] == "ui.language_switch"]
    assert switch_events[-1]["payload"]["language"] == "en_us"


def test_theme_controller_records_theme_switch(diagnostics_dir):
    window = SimpleNamespace(ui=SimpleNamespace(window=SimpleNamespace(setStyleSheet=lambda _s: None)))

    class _Palette:
        def update(self, _data):
            pass

    class _Styles:
        def __init__(self):
            self.style = "demo"

    controller = ThemeController(
        window=window,
        color_palette=_Palette(),
        app_themes={"eye": SimpleNamespace(data={"x": 1})},
        style_factory=_Styles,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
    )

    controller.cycle_theme()

    theme_events = [e for e in read_recent_events(limit=10) if e["name"] == "ui.theme_switch"]
    assert theme_events
    assert theme_events[-1]["payload"]["theme"] == "eye"
