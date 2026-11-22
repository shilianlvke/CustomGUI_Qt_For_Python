"""Toast 协议层测试：不启动 Qt，用记录型宿主断言契约。

覆盖：级别归一、句柄收敛、回调分发、卸载拦截、空实现与无 Qt 导入。
"""

from __future__ import annotations

import sys

import pytest

from sllkgui.appcore.feedback import (
    ToastAnchor,
    ToastCode,
    ToastLevel,
    ToastState,
    clamp_text,
    default_life,
    normalize_level,
    resolve_life,
)
from sllkgui.gallery.api import NOOP_TOAST, GalleryContext
from sllkgui.gallery.toast import RecordingHost, ToastRouter


@pytest.fixture
def host() -> RecordingHost:
    return RecordingHost()


@pytest.fixture
def router(host) -> ToastRouter:
    router = ToastRouter(host=host)
    yield router
    router.shutdown()


def test_protocol_layer_does_not_import_qt():
    """协议层必须能在无 Qt 的环境里导入（CLI / 插件校验）。"""
    import subprocess

    code = (
        "import sys;"
        "import sllkgui.appcore.feedback, sllkgui.gallery.api, sllkgui.gallery.toast;"
        "bad=[m for m in sys.modules if m.startswith('PySide6')];"
        "assert not bad, bad"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_level_aliases_and_fallback():
    assert normalize_level("warning") == (ToastLevel.WARN, False)
    assert normalize_level("danger") == (ToastLevel.ERROR, False)
    assert normalize_level("critical") == (ToastLevel.ERROR, False)
    assert normalize_level("primary") == (ToastLevel.INFO, False)
    assert normalize_level("loading") == (ToastLevel.LOADING, False)
    # 未知值回落 info，并标记为非法规避（不抛异常）
    assert normalize_level("wat") == (ToastLevel.INFO, True)
    assert normalize_level(None) == (ToastLevel.INFO, True)


def test_life_policy_by_level():
    assert default_life(ToastLevel.SUCCESS, 3000) == 3000
    assert default_life(ToastLevel.WARN, 3000) == 6000
    assert default_life(ToastLevel.ERROR, 3000) == 7800
    assert default_life(ToastLevel.NEUTRAL, 3000) == 1980
    assert default_life(ToastLevel.LOADING, 3000) == 0
    assert resolve_life(ToastLevel.INFO, 999_999, 3000) == (15_000, True)
    assert resolve_life(ToastLevel.LOADING, 5000, 3000) == (0, True)


def test_text_is_truncated():
    text, truncated = clamp_text("x" * 900)
    assert truncated is True
    assert len(text) == 500
    assert text.endswith("…")


def test_show_sets_scope_and_returns_handle(router, host):
    toast = router.handle("com.example.notes")
    handle = toast.show("已保存", level="success", channel="notes", code="NOTES_SAVED")
    assert handle.result.ok is True
    assert handle.toast_id.startswith("t-com-example-notes-")
    request = host.requests[handle.toast_id]
    assert request.scope == "com.example.notes"
    assert request.level is ToastLevel.SUCCESS
    assert request.channel == "notes"
    assert request.code == "NOTES_SAVED"


def test_loading_then_succeed_uses_same_handle(router, host):
    toast = router.handle("com.example.notes")
    handle = toast.loading("正在连接…", channel="webdav")
    assert handle.result.ok is True
    assert host.requests[handle.toast_id].life == 0
    assert host.requests[handle.toast_id].level is ToastLevel.LOADING

    result = handle.succeed("连接成功")
    assert result.ok is True
    _, patch = host.updates[-1]
    assert patch["text"] == "连接成功"
    assert patch["level"] is ToastLevel.SUCCESS
    assert patch["persist"] is False


def test_fail_carries_code_and_detail(router, host):
    toast = router.handle("com.example.notes")
    handle = toast.loading("正在测试…", channel="webdav")
    handle.fail("连接失败", code="WEBDAV_401", detail="unauthorized")
    _, patch = host.updates[-1]
    assert patch["level"] is ToastLevel.ERROR
    assert patch["code"] == "WEBDAV_401"
    assert patch["detail"] == "unauthorized"


def test_progress_advance(router, host):
    toast = router.handle("com.example.notes")
    handle = toast.progress("导入中", 0.0, channel="import")
    handle.advance(0.42, "导入中 42%")
    _, patch = host.updates[-1]
    assert patch["progress"] == 0.42
    assert patch["text"] == "导入中 42%"


def test_dismiss_and_action_callbacks(router, host):
    toast = router.handle("com.example.notes")
    seen: list[tuple[str, bool]] = []
    actions: list[str] = []
    handle = toast.show("可撤销", level="warn", actions=())
    handle.on_dismiss(lambda dismiss: seen.append((str(dismiss.reason), dismiss.by_user)))
    handle.on_action(actions.append)
    host.emit_action(handle.toast_id, "undo")
    host.emit_dismiss(handle.toast_id, "action", by_user=True)
    assert actions == ["undo"]
    assert seen == [("action", True)]


def test_callback_after_dismiss_is_replayed(router, host):
    """先关闭、后订阅：立即补发最后一次关闭载荷，避免调用方漏掉。"""
    toast = router.handle("com.example.notes")
    handle = toast.show("已完成", level="success")
    host.emit_dismiss(handle.toast_id, "timeout")
    seen = []
    handle.on_dismiss(lambda dismiss: seen.append(str(dismiss.reason)))
    assert seen == ["timeout"]


def test_unload_blocks_updates_and_callbacks(router, host):
    toast = router.handle("com.example.notes")
    handle = toast.show("处理中", level="loading", life=0)
    called: list[str] = []
    handle.on_dismiss(lambda dismiss: called.append("dismiss"))
    assert router.clear_plugin("com.example.notes") >= 1
    assert handle.update(text="不应生效").code == str(ToastCode.PLUGIN_UNLOADED)
    host.emit_dismiss(handle.toast_id, "timeout")
    assert called == []


def test_host_unavailable(router):
    router.bind(None)
    toast = router.handle("com.example.notes")
    handle = toast.show("任意")
    assert handle.result.ok is False
    assert handle.result.code == str(ToastCode.HOST_UNAVAILABLE)
    assert handle.state is ToastState.CLOSED


def test_noop_toast_is_safe():
    handle = NOOP_TOAST.show("任意")
    assert handle.result.ok is False
    assert handle.result.code == str(ToastCode.NOOP)
    assert handle.update(text="x").ok is False
    assert handle.dismiss() is False
    assert NOOP_TOAST.clear() == 0
    assert NOOP_TOAST.active() == ()
    assert NOOP_TOAST.capabilities() == frozenset()


def test_context_defaults_to_noop_toast():
    """旧上下文子类不覆写 ``toast`` 时也能实例化（非抽象属性）。"""

    from pathlib import Path

    class _Ctx(GalleryContext):
        plugin_id = "x"
        plugin_version = "1"
        data_dir = Path(".")
        cache_dir = Path(".")
        locale = "zh_cn"
        theme = "default"
        permissions = ()

        def resource(self, *parts):
            return Path(".")

        def open_surface(self, surface_id):
            return False

        def text(self, key, default=None, **kwargs):
            return default or key

        def log(self, message, level="info"):
            pass

        @property
        def logger(self):
            import logging

            return logging.getLogger("test")

        def event(self, name, payload=None, level="info"):
            pass

        def timing(self, name, payload=None):
            raise NotImplementedError

        def report_error(self, code, message, detail=None):
            pass

        def parent_window(self):
            return None

        @property
        def tray(self):
            raise NotImplementedError

        @property
        def shortcuts(self):
            raise NotImplementedError

        @property
        def settings(self):
            raise NotImplementedError

        @property
        def storage(self):
            raise NotImplementedError

        @property
        def events(self):
            raise NotImplementedError

        @property
        def services(self):
            raise NotImplementedError

    ctx = _Ctx()
    assert ctx.toast is NOOP_TOAST


def test_anchor_defaults_to_auto(router, host):
    toast = router.handle("com.example.notes")
    toast.show("任意", level="info")
    assert host.requests[toast.active()[0].toast_id].anchor is ToastAnchor.AUTO
