"""插件快捷键协议：权限、命名空间、冲突映射、卸载清理与内置项共存。"""

from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import MANIFEST, write_plugin

from sllkgui.gallery.api import Permission
from sllkgui.gallery.context import GalleryContextImpl
from sllkgui.gallery.defaults import PLUGIN_API_VERSION
from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.manifest import PluginManifest
from sllkgui.gallery.store import GalleryStore
from sllkgui.guicore.shortcuts import PRIORITY_BASE, reset_shortcut_registry


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def registry(app):
    table = reset_shortcut_registry()
    yield table
    table.shutdown()


@pytest.fixture(scope="module")
def prepared(app):
    from sllkgui.appcore import (
        AppLanguages,
        AppSettings,
        AppThemes,
        ColorPalette,
        Language,
        get_app_context,
    )

    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)


def _manifest(tmp_path: Path, permissions: tuple[Permission, ...]) -> PluginManifest:
    return PluginManifest(
        schema=1,
        api=PLUGIN_API_VERSION,
        plugin_id="com.example.keys",
        name="Keys",
        version="1.0.0",
        entry="plugin.py",
        root=tmp_path,
        permissions=permissions,
    )


def _context(tmp_path: Path, permissions: tuple[Permission, ...], registry) -> GalleryContextImpl:
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    return GalleryContextImpl(
        _manifest(tmp_path, permissions),
        store,
        shortcuts=registry,
    )


# ----------------------------------------------------------------------
# 权限
# ----------------------------------------------------------------------
def test_context_shortcuts_denied_without_permission(tmp_path: Path, registry):
    ctx = _context(tmp_path, (), registry)
    with pytest.raises(GalleryError) as exc:
        _ = ctx.shortcuts
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"
    assert "shortcuts" in exc.value.detail


def test_handle_still_checks_permission(tmp_path: Path, registry):
    """句柄方法二次校验：即使拿到 bridge 也不能绕过清单声明。"""
    from sllkgui.gallery.shortcuts import ShortcutBridge

    bridge = ShortcutBridge(registry, "com.example.keys", ())
    assert bridge.available() is False
    with pytest.raises(GalleryError) as exc:
        bridge.register("save", "primary+s", lambda: None)
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"


def test_context_shortcuts_unavailable_without_registry(tmp_path: Path):
    store = GalleryStore(tmp_path / "gallery-empty")
    store.ensure_layout()
    ctx = GalleryContextImpl(_manifest(tmp_path, (Permission.SHORTCUTS,)), store, shortcuts=None)
    with pytest.raises(GalleryError) as exc:
        _ = ctx.shortcuts
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"


# ----------------------------------------------------------------------
# 注册 / 更新 / 注销
# ----------------------------------------------------------------------
def test_register_is_namespaced_and_listed(tmp_path: Path, registry):
    ctx = _context(tmp_path, (Permission.SHORTCUTS,), registry)
    handle = ctx.shortcuts.register("save", "primary+shift+s", lambda: None, description="保存")

    assert handle.shortcut_id == "save"
    assert handle.sequence == "primary+shift+s"
    assert handle.enabled is True
    # 注册表内部带插件前缀，插件之间不会撞 id
    assert registry.get("com.example.keys:save") is not None
    assert [item.shortcut_id for item in registry.describe()] == ["com.example.keys:save"]

    binding = ctx.shortcuts.bindings()[0]
    assert binding.shortcut_id == "save"  # 对外只暴露短 id
    assert binding.plugin_id == "com.example.keys"
    assert binding.scope == "global"
    assert binding.description == "保存"


def test_handle_update_and_unregister(tmp_path: Path, registry):
    ctx = _context(tmp_path, (Permission.SHORTCUTS,), registry)
    handle = ctx.shortcuts.register("save", "primary+s", lambda: None)

    assert handle.update(sequence="primary+alt+s", enabled=False) is True
    assert handle.sequence == "primary+alt+s"
    assert handle.enabled is False
    assert ctx.shortcuts.set_enabled("save", True) is True
    assert handle.enabled is True

    handle.unregister()
    assert ctx.shortcuts.bindings() == ()
    assert ctx.shortcuts.unregister("save") is False


def test_clear_removes_every_plugin_binding(tmp_path: Path, registry):
    ctx = _context(tmp_path, (Permission.SHORTCUTS,), registry)
    ctx.shortcuts.register("one", "primary+1", lambda: None)
    ctx.shortcuts.register("two", "primary+2", lambda: None)
    assert registry.count("com.example.keys") == 2

    ctx.clear_shortcuts()
    assert registry.count() == 0


# ----------------------------------------------------------------------
# 冲突与错误码
# ----------------------------------------------------------------------
def test_builtin_conflict_maps_to_plugin_error(tmp_path: Path, registry):
    registry.register("base.search", "primary+k", lambda: None, owner="sllkgui.base", locked=True)
    ctx = _context(tmp_path, (Permission.SHORTCUTS,), registry)

    with pytest.raises(GalleryError) as exc:
        ctx.shortcuts.register("search", "primary+k", lambda: None)
    assert exc.value.code == "PLUGIN_SHORTCUT_CONFLICT"
    assert "base.search" in exc.value.detail
    # 内置项不受影响
    assert [item.shortcut_id for item in registry.describe()] == ["base.search"]


def test_replace_cannot_override_locked_builtin(tmp_path: Path, registry):
    registry.register("base.search", "primary+k", lambda: None, owner="sllkgui.base", locked=True)
    ctx = _context(tmp_path, (Permission.SHORTCUTS,), registry)

    with pytest.raises(GalleryError) as exc:
        ctx.shortcuts.register("search", "primary+k", lambda: None, conflict="replace")
    assert exc.value.code == "PLUGIN_SHORTCUT_LOCKED"
    assert registry.count() == 1


def test_invalid_sequence_maps_to_plugin_error(tmp_path: Path, registry):
    ctx = _context(tmp_path, (Permission.SHORTCUTS,), registry)
    with pytest.raises(GalleryError) as exc:
        ctx.shortcuts.register("bad", "ctrl+", lambda: None)
    assert exc.value.code == "PLUGIN_SHORTCUT_INVALID"


def test_conflicts_view_hides_other_plugins(tmp_path: Path, registry):
    from sllkgui.gallery.shortcuts import ShortcutBridge

    first = ShortcutBridge(registry, "com.example.a", (Permission.SHORTCUTS,))
    second = ShortcutBridge(registry, "com.example.b", (Permission.SHORTCUTS,))
    first.register("open", "primary+alt+o", lambda: None)
    second.register("open", "primary+alt+o", lambda: None, conflict="shadow")

    mine = second.conflicts()
    assert len(mine) == 1
    assert mine[0].sequence == "primary+alt+o"
    # 自己的条目用短 id，其他归属保留完整 id 以便定位
    assert set(mine[0].shortcut_ids) == {"open", "com.example.a:open"}
    # 冠军是先后顺序里更高优先级的一条（同优先级取先注册）
    assert mine[0].winner == "com.example.a:open"


# ----------------------------------------------------------------------
# 生命周期：加载 / 卸载
# ----------------------------------------------------------------------
PLUGIN_WITH_SHORTCUT = """
from sllkgui.plugin import GalleryContext, Plugin


def build_home(ctx: GalleryContext):
    from PySide6.QtWidgets import QLabel

    return QLabel("home")


class ShortcutPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.shortcuts.register("open", "primary+alt+h", lambda: None, description="hello")

    def surfaces(self):
        return {"home": build_home}


PLUGIN = ShortcutPlugin()
"""


def test_loader_clears_shortcuts_on_unload(tmp_path: Path, registry):
    from sllkgui.gallery.loader import load_plugin, unload_plugin
    from sllkgui.gallery.registry import GalleryRegistry

    # 清单里声明 shortcuts 权限，其余与公共样板一致
    manifest_text = MANIFEST.format(
        plugin_id="com.example.keys",
        name="Keys",
        version="1.0.0",
    ).replace("  - filesystem.write", "  - shortcuts")
    root = write_plugin(
        tmp_path / "keys",
        plugin_id="com.example.keys",
        plugin_source=PLUGIN_WITH_SHORTCUT,
        manifest_text=manifest_text,
    )
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()

    record = load_plugin(root, store, GalleryRegistry(), shortcuts=registry)
    assert record is not None
    assert registry.count("com.example.keys") == 1
    assert registry.describe()[0].sequence == "primary+alt+h"

    unload_plugin(record)
    assert registry.count() == 0


# ----------------------------------------------------------------------
# 内置快捷键
# ----------------------------------------------------------------------
class _StubController:
    def __init__(self) -> None:
        self.searches = 0
        self.settings = 0

    def open_search_palette(self) -> bool:
        self.searches += 1
        return True

    def open_settings_window(self) -> bool:
        self.settings += 1
        return True


def test_builtin_shortcuts_are_locked_and_highest_priority(registry):
    from PySide6.QtWidgets import QWidget

    from sllkgui.guicore.shortcuts import KeyBinding
    from sllkgui.guis.windows.main_window.builtin_shortcuts import (
        BASE_OWNER,
        install_builtin_shortcuts,
        uninstall_builtin_shortcuts,
    )

    controller = _StubController()
    window = QWidget()
    assert install_builtin_shortcuts(window, controller) == 2

    entries = registry.describe(owner=BASE_OWNER)
    assert {item.shortcut_id for item in entries} == {"base.search", "base.settings"}
    assert all(item.locked and item.priority == PRIORITY_BASE for item in entries)

    binding = KeyBinding.parse("primary+k")
    assert registry.activate(binding.key, binding.modifiers, window) == "base.search"
    assert controller.searches == 1

    # 幂等：重复装配不会堆叠条目
    assert install_builtin_shortcuts(window, controller) == 2
    assert registry.count(BASE_OWNER) == 2

    assert uninstall_builtin_shortcuts() == 2
    assert registry.count() == 0


def test_builtin_shortcuts_skip_hosts_without_entry_points(registry):
    from sllkgui.guis.windows.main_window.builtin_shortcuts import install_builtin_shortcuts

    class _Bare:
        pass

    assert install_builtin_shortcuts(None, _Bare()) == 0
    assert registry.count() == 0


def test_gallery_window_registers_and_releases_builtin_shortcuts(tmp_path: Path, prepared):
    from sllkgui.guicore.shortcuts import shortcut_registry
    from sllkgui.window import load_gallery

    window = load_gallery(data_dir=tmp_path / "gallery-keys")
    try:
        ids = {item.shortcut_id for item in shortcut_registry().describe()}
        assert {"base.search", "base.settings"} <= ids
        assert window._builtin_shortcuts >= 1
    finally:
        window._force_close = True
        window.close()
    assert shortcut_registry().count() == 0
