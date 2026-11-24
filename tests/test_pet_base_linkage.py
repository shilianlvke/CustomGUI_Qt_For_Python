"""基座操作 → 桌面宠物联动：全部接入点的行为契约测试。

覆盖三层：

1. **协议层**：CMD_REACT 已登记、必需载荷、hold 语义；
2. **事件桥层**：每个基座操作都真的发出了预期命令与载荷；
3. **端到端层**：真实 GalleryWindow 上的操作能改变宠物引擎状态，且瞬态反应
   到期后自动回到常态（这是修复「联动失效」的核心断言）。
"""

from __future__ import annotations

import pytest

from sllkgui.guicore.pet import events as ev
from sllkgui.guicore.pet.events import CMD_REACT, pet_bus, reset_pet_bus


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """固定用户配置目录、重建事件总线并还原全局语言。

    ``Language`` 是进程级单例：本模块会切换语言（联动点之一），若不还原，
    后续按中文断言文案的托盘/菜单用例会全部失败。主题同理
    （``SettingsController._apply_saved_settings`` 会改全局主题管理器）。
    """
    from sllkgui.appcore import Language
    from sllkgui.appcore import user_settings as us

    monkeypatch.setattr(us, "data_root", lambda: tmp_path)
    monkeypatch.setattr(
        "sllkgui.appcore.user_settings.user_settings_path",
        lambda: tmp_path / "settings" / "user.yaml",
    )
    original_language = Language.current()
    us.reset_user_settings_cache()
    reset_pet_bus()
    yield
    us.reset_user_settings_cache()
    if Language.current() != original_language:
        Language.apply(original_language)


@pytest.fixture
def pet(qapp):
    """启动一个真实宠物控制器；用例结束后关闭。"""
    from sllkgui.guicore.pet import MihoutaoPetController

    controller = MihoutaoPetController()
    controller.start()
    try:
        yield controller
    finally:
        controller.shutdown()


def _settle(engine, ms: float = 4000.0, steps: int = 200) -> None:
    """推进引擎时钟，让瞬态反应的到期逻辑真的执行。"""
    for _ in range(steps):
        engine.update(ms / steps / 1000.0)


def _reset_ambient(engine, state: str = "idle") -> None:
    """把引擎放到已知常态，清掉可能残留的反应。"""
    engine.reacting = False
    engine.react_until = 0.0
    engine.set_state(state)
    _settle(engine, 60.0, 6)


def _states() -> set[str]:
    from sllkgui.guicore.pet.engine.core import STATES

    return set(STATES)


# ----------------------------------------------------------------------
# 1. 协议层
# ----------------------------------------------------------------------
def test_react_command_is_registered():
    """CMD_REACT 已登记为合法命令，并要求 state 载荷。"""
    assert CMD_REACT in ev.EVENT_TYPES
    assert ev.REQUIRED_PAYLOAD[CMD_REACT] == ("state",)
    assert CMD_REACT.startswith(ev.COMMAND_PREFIX)


def test_react_requires_state_payload():
    """缺 state 的 react 发布被拒，带 state 时成功。"""
    handle = pet_bus().handle("test.observer")
    assert handle.publish(CMD_REACT, {}) is False
    assert handle.publish(CMD_REACT, {"state": "happy"}) is True


def test_visibility_event_is_published_on_toggle(pet):
    """显隐变化会广播 EVT_VISIBILITY_CHANGED（此前只有常量、无人发布）。"""
    seen: list[dict] = []
    pet_bus().handle("test.observer").subscribe(ev.EVT_VISIBILITY_CHANGED, lambda _t, p: seen.append(p))
    pet.toggle()
    assert seen and seen[-1]["visible"] is False
    pet.toggle()
    assert seen[-1]["visible"] is True


# ----------------------------------------------------------------------
# 2. 事件桥层：每个基座操作都发得出预期命令
# ----------------------------------------------------------------------
def test_base_operations_publish_pet_events(qapp):
    """基座操作按协议发布宠物事件，命名/载荷一致。"""
    from sllkgui.guis.windows.main_window.pet_bridge import (
        on_layout_changed,
        on_page_switched,
        on_search_opened,
        on_settings_opened,
        on_theme_cycled,
    )

    seen: list[tuple[str, dict]] = []
    handle = pet_bus().handle("observer")
    for topic in (ev.CMD_STATE, ev.CMD_HOP, ev.CMD_SPIN, ev.CMD_REACT):
        handle.subscribe(topic, lambda t, p: seen.append((t, p)))

    assert on_theme_cycled("dracula") is True
    assert on_settings_opened() is True
    assert on_search_opened() is True
    assert on_layout_changed("overlay") is True
    assert on_page_switched("btn_home") is True

    states = [p["state"] for t, p in seen if t == ev.CMD_REACT]
    assert "happy" in states and "curious" in states and "searching" in states
    assert any(t == ev.CMD_HOP for t, _ in seen)
    assert any(t == ev.CMD_SPIN for t, _ in seen)
    assert all(p["from"] == "sllkgui.base" for _, p in seen)
    assert all(p["seq"] > 0 for _, p in seen)


def test_pet_bridge_errors_do_not_break_base(qapp, monkeypatch):
    """事件总线异常时基座操作不被打断。"""
    from sllkgui.guis.windows.main_window import pet_bridge

    def broken_bus():
        raise RuntimeError("bus down")

    monkeypatch.setattr(pet_bridge, "pet_bus", broken_bus)
    assert pet_bridge.on_theme_cycled("default") is False
    assert pet_bridge.on_search_opened() is False
    assert pet_bridge.on_plugin_operation("install", plugin_id="p") is False


def test_plugin_operation_matrix_covers_core_actions():
    """插件管理的核心操作都在反应表里，且 ok/fail 两阶段齐全。"""
    from sllkgui.guis.windows.main_window.pet_bridge import PLUGIN_OPERATION_REACTIONS

    states = _states()
    for action in (
        "install",
        "update",
        "rollback",
        "remove",
        "enable",
        "disable",
        "source-add",
        "source-remove",
        "source-refresh",
        "refresh",
        "reload",
    ):
        phases = PLUGIN_OPERATION_REACTIONS[action]
        assert "ok" in phases and "fail" in phases, action
        for state, hold_ms in phases.values():
            assert state in states, action
            assert hold_ms > 0, action


# ----------------------------------------------------------------------
# 3. 引擎 / 控制器：瞬态反应语义
# ----------------------------------------------------------------------
def test_transient_reaction_returns_to_ambient(pet):
    """瞬态反应到期后回到反应前的常态，而不是被永久钉住。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    assert pet.react("searching", hold_ms=800) is True
    assert engine.state == "searching"
    _settle(engine, 2000)
    assert engine.state == "idle", "反应到期后必须回到常态"
    assert engine.reacting is False


def test_hold_reaction_survives_until_cleared(pet):
    """hold_ms<=0 是保持语义：不会自动到期，需要显式解除。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    assert pet.react("curious", hold_ms=0) is True
    _settle(engine, 6000)
    assert engine.state == "curious", "保持型反应不应自动到期"
    engine.clear_react()
    assert engine.state == "idle"


def test_repeated_reaction_does_not_lose_ambient(pet):
    """反应期间连续触发只延长时长，常态快照保持不变。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    pet.react("searching", hold_ms=800)
    pet.react("celebrate", hold_ms=800)
    assert engine.state == "celebrate"
    assert engine.ambient_state == "idle"
    _settle(engine, 2000)
    assert engine.state == "idle"


def test_explicit_state_selection_still_persists(pet):
    """用户显式选情绪仍是保持语义，不被反应机制改掉。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    pet.set_state("angry")
    _settle(engine, 5000)
    assert engine.state == "angry"
    assert engine.reacting is False


def test_explicit_selection_cancels_pending_reaction(pet):
    """反应期内用户显式选情绪：立刻生效且不被反应到期覆盖（"选了没生效"）。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    pet.react("searching", hold_ms=5000)
    assert engine.state == "searching"
    pet.set_state("angry")
    assert engine.state == "angry"
    assert engine.reacting is False
    _settle(engine, 8000)
    assert engine.state == "angry", "用户显式选择不应被已取消的反应覆盖"


def test_react_after_explicit_selection_returns_to_it(pet):
    """显式选了情绪之后再触发反应，到期应回到用户选的那个情绪。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    pet.set_state("proud")
    pet.react("celebrate", hold_ms=800)
    assert engine.state == "celebrate"
    _settle(engine, 2000)
    assert engine.state == "proud"


def test_reaction_rejects_unknown_state(pet):
    """非法状态名返回 False，不改变任何状态。"""
    engine = pet.engine
    _reset_ambient(engine, "idle")
    assert pet.react("not-a-state") is False
    assert engine.state == "idle"


# ----------------------------------------------------------------------
# 4. 插件管理操作 → 宠物反应
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("action", "ok", "expected"),
    [
        ("install", True, "celebrate"),
        ("install", False, "sad"),
        ("update", True, "celebrate"),
        ("rollback", True, "waking"),
        ("remove", True, "proud"),
        ("enable", True, "excited"),
        ("disable", True, "drowsy"),
        ("source-add", True, "spawning"),
        ("source-remove", True, "powering-down"),
        ("source-refresh", True, "listening"),
        ("refresh", True, "listening"),
        ("reload", True, "happy"),
        ("unknown-action", True, "working"),
    ],
)
def test_plugin_operation_reactions(pet, action, ok, expected):
    """每个插件管理操作都给出可感知的情绪反馈，并自动回到常态。"""
    from sllkgui.guis.windows.main_window.pet_bridge import on_plugin_operation

    engine = pet.engine
    _reset_ambient(engine)
    assert on_plugin_operation(action, plugin_id="com.example.x", ok=ok) is True
    assert engine.state == expected
    _settle(engine, 4000)
    assert engine.state == "idle"


@pytest.mark.parametrize(
    ("action", "expected"),
    [("install", "loading"), ("update", "uploading"), ("reload", "loading"), ("rollback", "loading")],
)
def test_plugin_operation_started_reactions(pet, action, expected):
    """长耗时操作开始时给出处理中反馈。"""
    from sllkgui.guis.windows.main_window.pet_bridge import on_plugin_operation_started

    engine = pet.engine
    _reset_ambient(engine)
    assert on_plugin_operation_started(action, plugin_id="p") is True
    assert engine.state == expected
    _settle(engine, 4000)
    assert engine.state == "idle"


def test_success_bursts_but_failure_does_not(pet):
    """成功时放粒子；失败时不放，避免错误提示显得不可信。"""
    from sllkgui.guis.windows.main_window.pet_bridge import on_plugin_operation

    engine = pet.engine
    for action in ("install", "unknown-action"):
        _reset_ambient(engine)
        engine.parts.clear()
        on_plugin_operation(action, plugin_id="p", ok=False)
        assert engine.parts == [], action
        on_plugin_operation(action, plugin_id="p", ok=True)
        assert len(engine.parts) > 0, action


def test_react_payload_carries_operation_context(pet):
    """react 载荷带上 action / plugin，便于插件侧排查与二次联动。"""
    from sllkgui.guis.windows.main_window.pet_bridge import on_plugin_operation

    seen: list[dict] = []
    pet_bus().handle("test.observer").subscribe(CMD_REACT, lambda _t, p: seen.append(p))
    on_plugin_operation("update", plugin_id="com.example.demo", ok=True)
    assert seen
    assert seen[-1]["action"] == "update"
    assert seen[-1]["plugin"] == "com.example.demo"
    assert seen[-1]["state"] == "celebrate"


# ----------------------------------------------------------------------
# 5. 端到端：真实 GalleryWindow 内的操作真的改变宠物
# ----------------------------------------------------------------------
@pytest.fixture
def gallery(qapp, tmp_path):
    """真实组合根窗口 + 宠物；用例结束后**完整**释放。

    ``GalleryWindow`` 会把自己订阅到全局 ``ThemeManager``。只调 ``_stop_pet``
    和 ``runtime.shutdown`` 不会退订：窗口对象仍活着，弱引用订阅继续触发
    样式重建，后续用例测量 ``Styles()`` 构造次数时会莫名其妙多出好几次。
    因此这里走真正的关闭路径（``_force_close`` + ``close()``），让
    ``closeEvent`` 里的 ``settings_controller.detach()`` 生效。
    """
    from sllkgui.gallery.runtime import GalleryRuntime
    from sllkgui.gallery.window import GalleryWindow

    runtime = GalleryRuntime("gallery", data_dir=tmp_path / "data")
    runtime.bootstrap()
    window = GalleryWindow(runtime)
    try:
        yield window
    finally:
        window._force_close = True
        window.close()
        window.deleteLater()
        runtime.shutdown()


def test_e2e_theme_save_reaches_pet(gallery):
    """设置窗口保存主题 → 宠物进入 happy 反应，到期回常态。"""
    engine = gallery._pet.engine
    _reset_ambient(engine)
    gallery.controller.settings_controller._apply_saved_settings({"core.appearance.theme": "bright"})
    assert engine.state == "happy"
    _settle(engine, 4000)
    assert engine.state == "idle"


def test_e2e_language_save_reaches_pet(gallery):
    """保存语言 → 宠物哼一声。"""
    engine = gallery._pet.engine
    _reset_ambient(engine)
    gallery.controller.settings_controller._apply_saved_settings({"core.interface.language": "en_us"})
    assert engine.state == "humming"


def test_e2e_layout_change_spins_pet(gallery):
    """抽屉/菜单模式变化 → 宠物转一圈。"""
    engine = gallery._pet.engine
    for key in ("core.interface.drawer_mode", "core.interface.menu_mode"):
        before = engine.spin.t
        gallery.controller.settings_controller._apply_saved_settings({key: "overlay"})
        assert engine.spin.t == before + 360, key


def test_e2e_search_button_reaches_pet(gallery):
    """标题栏搜索按钮（此前完全没有接线）→ searching，收起后离开该状态。"""
    from PySide6.QtWidgets import QPushButton

    engine = gallery._pet.engine
    _reset_ambient(engine)
    button = gallery.ui.title_bar.findChild(QPushButton, "btn_search")
    assert button is not None
    gallery.controller._handle_search_button(button)
    assert engine.state == "searching"
    gallery.controller._search_palette.hide()
    assert engine.state != "searching", "收起搜索后不应停在 searching"


def test_e2e_settings_window_open_and_close(gallery):
    """打开设置窗口 → 好奇（保持）；关闭 → 回到常态。"""
    engine = gallery._pet.engine
    _reset_ambient(engine)
    controller = gallery.controller.settings_controller
    assert controller.open_settings_window() is True
    assert engine.state == "curious"
    assert engine.react_until == 0.0, "打开期间应为保持语义"
    controller.close_settings_window()
    assert engine.state == "idle"


def test_e2e_page_switch_reaches_pet(gallery):
    """切页 → 宠物好奇。"""
    engine = gallery._pet.engine
    _reset_ambient(engine)
    gallery.controller.page_router.switch_page(
        "btn_native_plugin_store",
        "page_native_plugin_store",
        "Plugins",
    )
    assert engine.state == "curious"


def test_e2e_window_hide_and_show(gallery):
    """收进托盘 → drowsy；重新显示 → waking。"""
    from sllkgui.guis.windows.main_window.pet_bridge import on_window_hidden, on_window_shown

    engine = gallery._pet.engine
    _reset_ambient(engine)
    on_window_hidden()
    assert engine.state == "drowsy"
    _reset_ambient(engine)
    on_window_shown()
    assert engine.state == "waking"


def test_e2e_startup_show_keeps_onboarding(gallery, qapp):
    """启动首次显示不能打断 onboarding（只有托盘恢复才上报 waking）。"""
    engine = gallery._pet.engine
    # 重新进入 onboarding，模拟刚启动的状态
    engine.set_mode("onboarding")
    before = engine.mode
    gallery.show()
    qapp.processEvents()
    if gallery.runtime.tray.is_active():
        # 托盘可用时 closeEvent 会收进托盘，显示即"恢复"——这是用户操作，应当上报
        assert engine.state == "waking"
    else:
        assert engine.mode == before, "无托盘时首次显示不应改写运行模式"
        assert engine.state != "waking"


def test_e2e_plugin_store_page_reaches_pet(gallery):
    """插件管理页的真实操作入口（启用/安装）→ 宠物反应。"""
    from PySide6.QtWidgets import QWidget

    engine = gallery._pet.engine
    gallery.controller.page_router.switch_page(
        "btn_native_plugin_store",
        "page_native_plugin_store",
        "Plugins",
    )
    page = gallery.ui.load_pages.pages.findChild(QWidget, "page_native_plugin_store")
    assert page is not None
    _reset_ambient(engine)
    page._pet_operation("enable", plugin_id="com.example.one")
    assert engine.state == "excited"
    _reset_ambient(engine)
    page._pet_operation("install", plugin_id="com.example.two", ok=False)
    assert engine.state == "sad"


def test_e2e_pet_absent_does_not_break_operations(qapp):
    """宠物未启动时基座操作照常完成（事件桥静默降级）。"""
    from sllkgui.guis.windows.main_window import pet_bridge

    assert pet_bridge.on_plugin_operation("install", plugin_id="p") is True
    assert pet_bridge.on_search_opened() is True
    assert pet_bridge.on_settings_closed() is True
