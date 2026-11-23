"""基座托盘：分组计划、字段校验、注册表与关闭到托盘。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sllkgui.gallery.api import Permission, TrayGroup
from sllkgui.gallery.context import GalleryContextImpl
from sllkgui.gallery.defaults import PLUGIN_API_VERSION
from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.manifest import PluginManifest
from sllkgui.gallery.store import GalleryStore
from sllkgui.gallery.tray import (
    MAX_PLUGIN_ACTIONS,
    MAX_QUICK_ROWS,
    MAX_STATUS_ROWS,
    MAX_TOOLS_ROWS,
    TrayAction,
    TrayHandle,
    TrayService,
    plan_menu,
)


@pytest.fixture(scope="module")
def prepared(qapp):
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
        plugin_id="com.example.tray",
        name="Tray",
        version="1.0.0",
        entry="plugin.py",
        root=tmp_path,
        permissions=permissions,
    )


def _context(tmp_path: Path, permissions: tuple[Permission, ...]) -> GalleryContextImpl:
    store = GalleryStore(tmp_path / "gallery")
    store.ensure_layout()
    return GalleryContextImpl(_manifest(tmp_path, permissions), store, tray=TrayService())


def test_tray_actions_are_registered_per_plugin():
    service = TrayService()
    service.add_action("a:one", "One", lambda: None, order=10, plugin_id="a")
    service.add_action("b:two", "Two", lambda: None, order=20, plugin_id="b")
    assert service.action_count() == 2
    assert service.action_count("a") == 1
    service.remove_plugin("a")
    assert service.action_count("a") == 0
    assert service.action_count() == 1


def test_tray_handle_requires_permissions(tmp_path: Path):
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", ())
    with pytest.raises(GalleryError) as exc:
        handle.add_action("toggle", "Toggle", lambda: None)
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"

    without_notifications = TrayHandle(service, "com.example.tray", (Permission.TRAY,))
    with pytest.raises(GalleryError) as exc:
        without_notifications.show_message("t", "m")
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"


def test_tray_handle_clear_removes_actions():
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", (Permission.TRAY,))
    handle.add_action("toggle", "Toggle", lambda: None)
    handle.add_action("save", "Save", lambda: None)
    assert service.action_count("com.example.tray") == 2
    handle.clear()
    assert service.action_count("com.example.tray") == 0


def test_tray_api_has_no_icon_control():
    """图标与悬停提示是基座品牌，插件 API 里不应存在修改入口。"""
    from sllkgui.gallery.api import GalleryTray

    for name in ("set_icon", "set_tooltip"):
        assert not hasattr(GalleryTray, name)
        assert not hasattr(TrayHandle, name)


def test_tray_action_errors_are_isolated():
    service = TrayService()

    def boom() -> None:
        raise RuntimeError("boom")

    service.add_action("com.example.tray:boom", "Boom", boom, plugin_id="com.example.tray")
    action = service._actions["com.example.tray:boom"]
    service._invoke(action)  # 不应向上抛异常


def test_runtime_bootstrap_starts_resident_tray(tmp_path: Path, prepared, monkeypatch):
    """托盘由基座常驻：即使没有插件注册动作，bootstrap 也要拉起。"""
    calls: list[str] = []
    monkeypatch.setattr(TrayService, "ensure_visible", lambda self: calls.append("visible") or True)

    from sllkgui.window import load_gallery

    window = load_gallery(data_dir=tmp_path / "gallery-resident")
    try:
        assert calls == ["visible"]
    finally:
        window._force_close = True
        window.close()


def test_context_tray_denied_without_permission(tmp_path: Path):
    ctx = _context(tmp_path, ())
    with pytest.raises(GalleryError) as exc:
        _ = ctx.tray
    assert exc.value.code == "PLUGIN_PERMISSION_DENIED"


def test_context_tray_available_with_permission(tmp_path: Path):
    ctx = _context(tmp_path, (Permission.TRAY,))
    assert ctx.tray is not None
    assert ctx.tray.available() in (True, False)


def test_window_close_hides_to_tray_when_active(tmp_path: Path, prepared):
    from sllkgui.window import load_gallery

    window = load_gallery(data_dir=tmp_path / "gallery-data")
    window.runtime.tray.is_active = lambda: True  # type: ignore[method-assign]
    window.show()
    window.close()
    assert window.isVisible() is False
    assert window.runtime.records, "关闭到托盘时不应卸载插件"
    window._force_close = True
    window.close()
    assert window.runtime.records == []


def test_close_to_tray_releases_ui_caches(tmp_path: Path, prepared):
    """托盘隐藏期间释放背景图解码缓存，重新显示时按路径恢复。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    from sllkgui.window import load_gallery

    window = load_gallery(data_dir=tmp_path / "gallery-trim")
    surface = window.ui.window
    image = QImage(320, 200, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    wallpaper = tmp_path / "wallpaper.jpg"
    assert image.save(str(wallpaper), "JPG")
    assert surface.set_background_image(str(wallpaper), "fill")
    assert not surface._background_pixmap.isNull()

    window.runtime.tray.is_active = lambda: True  # type: ignore[method-assign]
    window.show()
    window.close()
    assert window.isVisible() is False
    assert surface._background_pixmap.isNull()

    window.show()
    assert not surface._background_pixmap.isNull()

    window._force_close = True
    window.close()


# ----------------------------------------------------------------------
# 分组计划：槽预算、块形态与兜底桶
# ----------------------------------------------------------------------
def _action(plugin_id, action_id, text, *, group="tools", order=100, submenu=None, enabled=True, name=""):
    return TrayAction(
        action_id=f"{plugin_id}:{action_id}",
        text=text,
        callback=lambda: None,
        order=order,
        plugin_id=plugin_id,
        plugin_name=name or plugin_id,
        group=str(group),
        submenu=submenu,
        enabled=enabled,
    )


def test_plan_empty_registry_has_no_items():
    assert plan_menu([]).items == ()


def test_plan_single_plugin_keeps_slot_flat():
    """独占槽的插件不产生子菜单：单插件时零层级。"""
    plan = plan_menu([_action("a", "one", "清空历史"), _action("a", "two", "打开目录", order=20)])
    assert [item.kind for item in plan.items] == ["action", "action", "separator"]
    assert plan.submenu_blocks == 0


def test_plan_two_plugins_collapse_into_submenus():
    plan = plan_menu(
        [
            _action("a", "one", "A1", name="甲", order=10),
            _action("b", "one", "B1", name="乙", order=20),
        ]
    )
    assert [item.kind for item in plan.items] == ["submenu", "submenu", "separator"]
    assert [item.text for item in plan.items if item.kind == "submenu"] == ["甲", "乙"]


def test_plan_submenu_false_keeps_small_block_inline():
    """显式 submenu=False 且块内动作不多时，允许在槽内保留内联块。"""
    plan = plan_menu(
        [
            _action("a", "one", "A1", name="甲", order=10, submenu=False),
            _action("b", "one", "B1", name="乙", order=20),
            _action("b", "two", "B2", name="乙", order=30),
        ]
    )
    kinds = [item.kind for item in plan.items]
    assert kinds == ["action", "submenu", "separator"]


def test_plan_quick_over_budget_demotes_to_tools():
    actions = [_action("a", f"q{i}", f"Q{i}", group="quick", order=i) for i in range(MAX_QUICK_ROWS + 2)]
    plan = plan_menu(actions)
    assert plan.quick_rows == MAX_QUICK_ROWS
    assert plan.demoted == 2
    # 降级不等于丢弃：7 条动作全部还在菜单里
    assert len([item for item in plan.items if item.kind == "action"]) == MAX_QUICK_ROWS + 2


def test_plan_tools_over_budget_uses_bucket():
    actions = []
    for index in range(9):
        actions.append(_action(f"p{index}", "one", f"P{index}-1", name=f"插件{index}", order=10))
        actions.append(_action(f"p{index}", "two", f"P{index}-2", name=f"插件{index}", order=20))
    plan = plan_menu(actions)
    assert plan.tools_blocks == 9
    submenus = [item for item in plan.items if item.kind == "submenu"]
    bucket = [item for item in plan.items if item.kind == "more"]
    # 顶层 tools 段（子菜单 + 兜底桶）= 预算行数，插件再多也不外溢
    assert len(submenus) + len(bucket) == MAX_TOOLS_ROWS
    assert plan.overflow_blocks == 3
    assert plan.bucketed == 6
    assert bucket[0].children[0].text.startswith("插件6 · ")
    # 桶内平铺，不再嵌套第三层
    assert all(child.kind == "action" for child in bucket[0].children)


def test_plan_status_is_read_only_and_truncated():
    actions = [_action("a", f"s{i}", f"S{i}", group="status", order=i) for i in range(MAX_STATUS_ROWS + 2)]
    plan = plan_menu(actions)
    assert plan.status_rows == MAX_STATUS_ROWS
    assert plan.truncated_status == 2
    assert all(not item.enabled for item in plan.items if item.kind == "action")
    assert [item.kind for item in plan.items] == ["action"] * MAX_STATUS_ROWS + ["separator"]


# ----------------------------------------------------------------------
# 句柄：字段校验、配额与实际落位
# ----------------------------------------------------------------------
def test_tray_handle_validates_fields():
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", (Permission.TRAY,), "示例")
    cases = [
        ({"action_id": "bad id", "text": "x"}, "PLUGIN_TRAY_ACTION_INVALID"),
        ({"action_id": "ok", "text": "   "}, "PLUGIN_TRAY_ACTION_INVALID"),
        ({"action_id": "ok", "text": "x" * 41}, "PLUGIN_TRAY_ACTION_INVALID"),
        ({"action_id": "ok", "text": "x", "order": -1}, "PLUGIN_TRAY_ACTION_INVALID"),
        ({"action_id": "ok", "text": "x", "order": True}, "PLUGIN_TRAY_ACTION_INVALID"),
        ({"action_id": "ok", "text": "x", "group": "nope"}, "PLUGIN_TRAY_GROUP_INVALID"),
        ({"action_id": "ok", "text": "x", "group": "base"}, "PLUGIN_TRAY_GROUP_FORBIDDEN"),
        ({"action_id": "ok", "text": "x", "submenu": "yes"}, "PLUGIN_TRAY_ACTION_INVALID"),
    ]
    for kwargs, code in cases:
        with pytest.raises(GalleryError) as exc:
            handle.add_action(callback=lambda: None, **kwargs)
        assert exc.value.code == code, kwargs
    assert service.action_count() == 0


def test_tray_handle_rejects_quota():
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", (Permission.TRAY,), "示例")
    for index in range(MAX_PLUGIN_ACTIONS):
        handle.add_action(f"a{index}", f"A{index}", lambda: None)
    with pytest.raises(GalleryError) as exc:
        handle.add_action("overflow", "Overflow", lambda: None)
    assert exc.value.code == "PLUGIN_TRAY_QUOTA_EXCEEDED"


def test_tray_handle_accepts_group_enum():
    service = TrayService()
    handle = TrayHandle(service, "com.example.tray", (Permission.TRAY,), "示例")
    handle.add_action("speed", "立即测速", lambda: None, group=TrayGroup.QUICK)
    assert service.action_count(group=TrayGroup.QUICK) == 1


def test_tray_entries_report_rendered_location():
    service = TrayService()
    first = TrayHandle(service, "com.example.first", (Permission.TRAY,), "甲")
    first.add_action("start", "开始专注", lambda: None, order=10)
    first.add_action("pause", "暂停", lambda: None, order=20)
    assert [entry.rendered_as for entry in first.entries()] == ["inline", "inline"]

    second = TrayHandle(service, "com.example.second", (Permission.TRAY,), "乙")
    second.add_action("go", "前往", lambda: None)
    after = first.entries()
    assert [entry.rendered_as for entry in after] == ["submenu", "submenu"]
    assert after[0].action_id == "start"
    assert after[0].path == ("甲", "开始专注")


def test_menu_items_group_plugins_and_append_base(qapp):
    """菜单项树：插件块 → 分隔线 → 基座固定项；卸载回到内联形态。"""
    service = TrayService()
    first = TrayHandle(service, "a", (Permission.TRAY,), "甲")
    first.add_action("x", "X", lambda: None, order=10)
    first.add_action("y", "Y", lambda: None, order=20)
    second = TrayHandle(service, "b", (Permission.TRAY,), "乙")
    second.add_action("z", "Z", lambda: None)

    service.attach_window(lambda: None, lambda: None, lambda: None)
    items = service.menu_items()
    labels = [item.label for item in items]
    assert labels[:2] == ["甲", "乙"]
    assert labels[-3:] == ["显示主窗口", "设置…", "退出"]
    assert [child.label for child in items[0].items] == ["X", "Y"]

    second.clear()
    assert [item.label for item in service.menu_items()] == [
        "X",
        "Y",
        "",
        "显示主窗口",
        "设置…",
        "退出",
    ]


def test_menu_trigger_dispatches_plugin_action(qapp):
    service = TrayService()
    called: list[str] = []
    handle = TrayHandle(service, "a", (Permission.TRAY,), "甲")
    handle.add_action("x", "X", lambda: called.append("x"))

    menu = service.menu()
    item = next(entry for entry in service.menu_items() if entry.key == "a:x")
    menu.triggered.emit(item)
    assert called == ["x"]


def test_base_section_includes_settings_when_available(qapp):
    service = TrayService()
    calls: list[str] = []
    service.attach_window(lambda: None, lambda: None, lambda: calls.append("settings"))
    items = service.menu_items()
    assert [item.label for item in items] == ["显示主窗口", "设置…", "退出"]
    items[1].command()
    assert calls == ["settings"]


def test_window_wires_settings_opener_into_tray(tmp_path: Path, prepared):
    """宿主必须在 controller 就绪后接入托盘，否则「设置…」会缺失。"""
    from sllkgui.window import load_gallery

    window = load_gallery(data_dir=tmp_path / "gallery-settings")
    try:
        assert callable(window.runtime.tray._open_settings_cb)
    finally:
        window._force_close = True
        window.close()


def test_menu_activation_runs_action_once(qapp):
    """插件动作只走 triggered 派发：command 与信号不能各执行一次。"""
    service = TrayService()
    called: list[str] = []
    handle = TrayHandle(service, "a", (Permission.TRAY,), "甲")
    handle.add_action("x", "X", lambda: called.append("x"))

    from PySide6.QtCore import QPoint

    menu = service.menu()
    menu.set_items(service.menu_items())
    menu.popup(QPoint(80, 80))
    try:
        menu.set_active_index(0)
        assert menu.activate_active() is True
    finally:
        menu.dismiss()
    assert called == ["x"]
