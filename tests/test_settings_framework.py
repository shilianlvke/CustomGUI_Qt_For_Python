"""统一设置框架：命名空间、存储隔离、会话与变更通知。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sllkgui.appcore import (
    KEY_REMEMBER_SIZE,
    KEY_THEME,
    Setting,
    SettingsConflictError,
    SettingsError,
    SettingsPage,
    SettingsRegistry,
    SettingsSection,
    SettingsSession,
    SettingsStore,
    SettingsValidationError,
    ensure_core_pages,
    plugin_namespace,
)
from sllkgui.gallery.settings import PluginSettings


class _MemoryCore:
    """内存版基座后端，避免测试触碰真实 user.yaml。"""

    def __init__(self) -> None:
        self.data: dict = {}

    def load(self) -> dict:
        return dict(self.data)

    def save(self, updates) -> bool:
        self.data.update(dict(updates))
        return True

    def path(self) -> Path:
        return Path("user.yaml")


@pytest.fixture
def core() -> _MemoryCore:
    return _MemoryCore()


@pytest.fixture
def store(tmp_path, core) -> SettingsStore:
    return SettingsStore(settings_dir=tmp_path, core=core)


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    ensure_core_pages(reg)
    return reg


@pytest.fixture
def session(registry, store) -> SettingsSession:
    return SettingsSession(registry, store)


def test_session_prunes_removed_plugin_keys(registry, store):
    """插件重载后删掉的设置键不能留下无法保存的草稿。"""
    namespace = plugin_namespace("com.example.hot")
    page = SettingsPage(
        page_id="hot",
        title="Hot",
        sections=(
            SettingsSection(
                "A",
                (
                    Setting.switch("keep", True, "Keep"),
                    Setting.switch("drop", True, "Drop"),
                ),
            ),
        ),
    )
    registry.register(page, namespace=namespace)
    session = SettingsSession(registry, store)
    session.set(f"{namespace}.drop", False)
    assert session.is_dirty()

    registry.unregister_namespace(namespace)
    registry.register(
        SettingsPage(
            page_id="hot",
            title="Hot",
            sections=(SettingsSection("A", (Setting.switch("keep", True, "Keep"),)),),
        ),
        namespace=namespace,
    )
    removed = session.prune_namespace(namespace)
    assert removed == (f"{namespace}.drop",)
    assert not session.is_dirty()


def test_core_pages_are_namespaced(registry):
    pages = registry.pages("core")
    assert [page.page_id for page in pages] == ["appearance", "interface", "window", "pet"]
    assert pages[0].full_key("theme") == KEY_THEME == "core.appearance.theme"
    assert pages[2].full_key("remember_size") == KEY_REMEMBER_SIZE


def test_duplicate_key_in_same_namespace_is_rejected(registry):
    page = SettingsPage(
        page_id="dup",
        title="Dup",
        sections=(SettingsSection("A", (Setting.switch("flag", True, "Flag"),)),),
    )
    namespace = plugin_namespace("com.example.dup")
    registry.register(page, namespace=namespace)
    with pytest.raises(SettingsConflictError):
        registry.register(page, namespace=namespace)
    # replace=True 用于插件重载：整体替换而不是报错
    replaced = registry.register(page, namespace=namespace, replace=True)
    assert replaced.page_id == "dup"


def test_plugin_pages_and_keys_are_isolated(tmp_path, core, registry, store):
    first = PluginSettings("com.example.one", registry=registry, store=store)
    second = PluginSettings("com.example.two", registry=registry, store=store)
    for bridge, name in ((first, "One"), (second, "Two")):
        bridge.define(
            SettingsPage(
                page_id="",
                title=name,
                sections=(
                    SettingsSection(
                        "behavior",
                        (
                            Setting.switch("enabled", True, "Enabled"),
                            Setting.number("columns", 4, "Columns", minimum=1, maximum=8),
                        ),
                    ),
                ),
            )
        )
    assert first.set("columns", 6)
    assert second.get("columns") == 4
    assert first.get("columns") == 6
    assert store.path_for(first.namespace) != store.path_for(second.namespace)
    assert store.path_for(first.namespace).is_file()
    assert "columns: 6" in store.path_for(first.namespace).read_text(encoding="utf-8")


def test_session_tracks_save_and_discard(session, core):
    assert session.value(KEY_THEME) == "default"
    assert session.set(KEY_THEME, "bright")
    assert session.is_dirty()
    assert session.dirty_count() == 1
    assert session.changes() == {KEY_THEME: "bright"}

    assert session.save()
    assert core.data["theme_name"] == "bright"
    assert not session.is_dirty()
    assert session.baseline(KEY_THEME) == "bright"

    assert session.set(KEY_THEME, "eye")
    session.discard()
    assert session.value(KEY_THEME) == "bright"
    assert not session.is_dirty()


def test_session_validates_ranges_and_enums(session):
    key = "core.appearance.transparency"
    with pytest.raises(SettingsValidationError):
        session.set(key, 120)
    with pytest.raises(SettingsValidationError):
        session.set("core.interface.menu_mode", "floating")
    assert not session.is_dirty()


def test_reset_page_returns_defaults_without_losing_other_pages(session, core):
    session.set(KEY_THEME, "dracula")
    assert session.save()
    session.set(KEY_REMEMBER_SIZE, False)
    page = next(item for item in session.pages("core") if item.page_id == "appearance")
    assert session.reset_page(page) == 1
    assert session.value(KEY_THEME) == "default"
    assert session.value(KEY_REMEMBER_SIZE) is False
    assert session.save()
    assert core.data["theme_name"] == "default"
    assert core.data["remember_window_size"] is False


def test_save_notifies_plugin_listeners(registry, store):
    bridge = PluginSettings("com.example.listen", registry=registry, store=store)
    bridge.define(
        SettingsPage(
            page_id="",
            title="Listen",
            sections=(SettingsSection("A", (Setting.number("size", 10, "Size", minimum=1, maximum=20),)),),
        )
    )
    received: list[tuple[str, object]] = []
    unsubscribe = bridge.on_changed(lambda key, value: received.append((key, value)))
    session = SettingsSession(registry, store)
    assert session.set("plugin.com.example.listen.size", 16)
    assert session.save()
    assert received == [("size", 16)]
    unsubscribe()
    assert session.set("plugin.com.example.listen.size", 18)
    assert session.save()
    assert received == [("size", 16)]


def test_invalid_stored_value_falls_back_to_default(tmp_path, core, registry):
    core.data["acrylic_transparency"] = 999
    store = SettingsStore(settings_dir=tmp_path, core=core)
    session = SettingsSession(registry, store)
    # 不写死数字：默认值由 acrylic.opacity 推导，断言"回落到声明里的默认值"
    assert session.value("core.appearance.transparency") == _core_spec("transparency").default


def test_plugin_namespace_requires_valid_id():
    assert plugin_namespace("com.example.ok") == "plugin.com.example.ok"
    with pytest.raises(ValueError):
        plugin_namespace("Bad/Id")


def test_action_and_info_rows_are_declarations_only():
    page = SettingsPage(
        page_id="plugin-demo",
        title="Demo",
        sections=(
            SettingsSection(
                "g",
                (Setting.switch("enabled", True, "启用"),),
                info=(Setting.info("stats", "统计", lambda: "3 首"),),
                actions=(Setting.action("open", "打开", lambda: None, button="执行"),),
            ),
        ),
    )
    assert [spec.key for spec in page.specs()] == ["enabled"]
    assert [info.key for info in page.infos()] == ["stats"]
    assert [action.key for action in page.actions()] == ["open"]
    assert page.infos()[0].value() == "3 首"
    assert page.actions()[0].display_button() == "执行"


def test_duplicate_action_or_info_key_is_rejected():
    with pytest.raises(SettingsConflictError):
        SettingsPage(
            page_id="dup-action",
            title="Dup",
            sections=(
                SettingsSection(
                    "g",
                    (Setting.switch("same", True, "Same"),),
                    actions=(Setting.action("same", "Same"),),
                ),
            ),
        )
    with pytest.raises(SettingsConflictError):
        SettingsPage(
            page_id="dup-info",
            title="Dup",
            sections=(
                SettingsSection(
                    "g",
                    info=(Setting.info("info", "Info"),),
                    actions=(Setting.action("info", "Info"),),
                ),
            ),
        )


def test_invalid_action_key_is_rejected():
    with pytest.raises(SettingsError):
        Setting.action("Bad-Key", "x")


def test_info_provider_failure_is_isolated():
    def boom():
        raise RuntimeError("boom")

    assert Setting.info("stats", "统计", boom).value() == "—"


def _core_spec(key: str):
    from sllkgui.appcore.settings.base import build_core_pages

    for page in build_core_pages():
        for section in page.sections:
            for spec in section.items:
                if spec.key == key:
                    return spec
    raise AssertionError(f"核心设置页缺少 {key}")


def test_transparency_default_is_complement_of_acrylic_opacity():
    """``transparency`` 越大越透明，``acrylic.opacity`` 越大越不透明，必须互补。"""
    from sllkgui.appcore.sysx import AppSettings

    spec = _core_spec("transparency")
    assert spec.default == 100 - int(AppSettings.acrylic.opacity)


def test_core_settings_cover_supported_user_fields():
    """SUPPORTED_FIELDS 必须等于「声明过的存储键 ∪ 运行期专用字段」。"""
    from sllkgui.appcore.settings.base import build_core_pages
    from sllkgui.appcore.user_settings import RUNTIME_ONLY_FIELDS, SUPPORTED_FIELDS

    declared = {
        page.storage_key(spec) for page in build_core_pages() for section in page.sections for spec in section.items
    }
    assert set(SUPPORTED_FIELDS) == declared | RUNTIME_ONLY_FIELDS


def test_language_options_follow_resource_discovery():
    """语言下拉必须随 LANGUAGE_OPTIONS 动态发现，而不是写死四种。"""
    from sllkgui.appcore.sysx.modules.language_module import LANGUAGE_OPTIONS

    spec = _core_spec("language")
    assert [option.value for option in spec.options] == [str(code) for code in LANGUAGE_OPTIONS]
