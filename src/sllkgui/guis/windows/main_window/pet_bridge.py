"""基座操作 → 桌面宠物事件桥。

把基座中的用户操作按宠物事件协议发布为命令/反馈，使宠物能响应主题切换、
设置窗口开关、搜索、页面切换、语言切换、布局模式变化与插件管理操作等。
发布走统一 pet_bus，遵循事件命名/载荷/错误处理规则；宠物未启动或事件总线
异常均静默降级，绝不打断基座操作。

两条发布语义（对应控制器里的两个分支）：

- :data:`CMD_REACT`：**瞬态**反馈。宠物切到指定情绪，``hold_ms`` 后自动回到
  操作前的常态。基座操作一律用它——用户不该因为点了一次搜索就被永久钉在
  searching 状态。
- :data:`CMD_STATE` / 其余命令：**保持**语义，只有用户显式选择情绪时才用。
"""

from __future__ import annotations

from typing import Any

from sllkgui.appcore import Logger
from sllkgui.guicore.pet.events import (
    CMD_BURST,
    CMD_HOP,
    CMD_REACT,
    CMD_SETTING,
    CMD_SPIN,
    pet_bus,
)

OWNER = "sllkgui.base"

#: 瞬态反馈的默认持续时长（毫秒）。到期后宠物回到操作前的常态情绪。
DEFAULT_REACT_MS = 1600
#: 长耗时操作（安装 / 更新 / 重载）的反馈时长：足够让用户看到，但不至于长期卡住。
LONG_REACT_MS = 2600

#: 插件管理操作 → 宠物反应。``start`` 是操作开始时，``ok`` / ``fail`` 是结果。
#: 未登记的动作走通用 ``WORKING`` 反应，保证新增操作也有反馈而不是静默。
PLUGIN_OPERATION_REACTIONS: dict[str, dict[str, tuple[str, int]]] = {
    "install": {
        "start": ("loading", LONG_REACT_MS),
        "ok": ("celebrate", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "update": {
        "start": ("uploading", LONG_REACT_MS),
        "ok": ("celebrate", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "rollback": {
        "start": ("loading", LONG_REACT_MS),
        "ok": ("waking", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "remove": {
        "start": ("powering-down", LONG_REACT_MS),
        "ok": ("proud", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "enable": {
        "start": ("thinking", DEFAULT_REACT_MS),
        "ok": ("excited", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "disable": {
        "start": ("thinking", DEFAULT_REACT_MS),
        "ok": ("drowsy", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "source-add": {
        "start": ("loading", LONG_REACT_MS),
        "ok": ("spawning", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
    "source-remove": {
        "start": ("working", DEFAULT_REACT_MS),
        "ok": ("powering-down", DEFAULT_REACT_MS),
        "fail": ("sad", DEFAULT_REACT_MS),
    },
    "source-refresh": {
        "start": ("radar", LONG_REACT_MS),
        "ok": ("listening", DEFAULT_REACT_MS),
        "fail": ("sad", DEFAULT_REACT_MS),
    },
    "refresh": {
        "start": ("listening", DEFAULT_REACT_MS),
        "ok": ("listening", DEFAULT_REACT_MS),
        "fail": ("sad", DEFAULT_REACT_MS),
    },
    "reload": {
        "start": ("loading", LONG_REACT_MS),
        "ok": ("happy", LONG_REACT_MS),
        "fail": ("sad", LONG_REACT_MS),
    },
}

#: 未登记动作的兜底反应：仍然给一次可感知的"我在干活"反馈
FALLBACK_PLUGIN_REACTION = ("working", DEFAULT_REACT_MS)


def _publish(topic: str, payload: dict[str, Any] | None = None) -> bool:
    """发布宠物事件；任何失败只告警并返回 False，不影响基座操作。"""
    try:
        return bool(pet_bus().handle(OWNER).publish(topic, payload))
    except Exception as exc:  # noqa: BLE001 - 事件桥绝不打断主流程
        Logger.debug(f"宠物事件桥发布失败 {topic}: {exc}")
        return False


def _react(state: str, hold_ms: int = DEFAULT_REACT_MS, **extra: Any) -> bool:
    """发布一次瞬态情绪反应；``extra`` 作为可选载荷原样透传。"""
    return _publish(CMD_REACT, {"state": state, "hold_ms": int(hold_ms), **extra})


# ----------------------------------------------------------------------
# 主题 / 外观
# ----------------------------------------------------------------------
def on_theme_cycled(theme: str) -> bool:
    """主题循环切换：宠物做一次雀跃反馈（跳到开心，到期自动还原）。"""
    hopped = _publish(CMD_HOP)
    reacted = _react("happy", DEFAULT_REACT_MS, theme=str(theme))
    return hopped and reacted


def on_theme_changed(theme: str) -> bool:
    """主题正式变更（设置窗口保存 / 预览落地）：转一圈并短暂开心。"""
    spun = _publish(CMD_SPIN)
    reacted = _react("happy", DEFAULT_REACT_MS, theme=str(theme))
    return spun and reacted


# ----------------------------------------------------------------------
# 设置窗口
# ----------------------------------------------------------------------
def on_settings_opened() -> bool:
    """打开设置窗口：宠物切到好奇状态（保持，直到窗口关闭）。"""
    return _publish(CMD_REACT, {"state": "curious", "hold_ms": 0, "hold": True})


def on_settings_closed() -> bool:
    """关闭设置窗口：结束"保持"型好奇，回到常态。"""
    return _react("idle", DEFAULT_REACT_MS)


# ----------------------------------------------------------------------
# 搜索
# ----------------------------------------------------------------------
def on_search_opened() -> bool:
    """打开搜索（标题栏按钮或快捷键）：切到搜索状态。"""
    return _react("searching", DEFAULT_REACT_MS)


def on_search_closed(result_btn: str = "") -> bool:
    """搜索面板收起 / 命中结果：给一次轻反馈后回到常态。"""
    if result_btn:
        return _react("listening", DEFAULT_REACT_MS, page=str(result_btn))
    return _react("idle", DEFAULT_REACT_MS)


# ----------------------------------------------------------------------
# 布局 / 导航
# ----------------------------------------------------------------------
def on_layout_changed(mode: str) -> bool:
    """布局模式变化（菜单 / 抽屉）：转一圈作为视觉反馈。"""
    return _publish(CMD_SPIN, {"mode": str(mode)})


def on_page_switched(btn_name: str) -> bool:
    """主窗口切页：宠物好奇地看一眼当前页面。"""
    return _react("curious", 1000, page=str(btn_name))


def on_language_changed(language: str) -> bool:
    """界面语言切换：宠物哼一声表示"听懂新语言了"。"""
    return _react("humming", DEFAULT_REACT_MS, language=str(language))


# ----------------------------------------------------------------------
# 插件管理
# ----------------------------------------------------------------------
def on_plugin_operation(action: str, *, plugin_id: str = "", ok: bool = True) -> bool:
    """插件管理操作的结果反馈（安装/卸载/启停/更新/回滚/来源等）。

    ``action`` 取 :data:`PLUGIN_OPERATION_REACTIONS` 的键；未登记动作走兜底
    反应，保证"新增操作也有反馈"而不是静默。成功时附加一次粒子特效。
    """
    reaction = PLUGIN_OPERATION_REACTIONS.get(str(action), {}).get("ok" if ok else "fail")
    if reaction is None:
        reaction = FALLBACK_PLUGIN_REACTION
    state, hold_ms = reaction
    reacted = _react(state, hold_ms, action=str(action), plugin=str(plugin_id))
    if ok:
        # 成功才放粒子：失败时同时撒花会让错误提示显得不可信。
        # 未登记动作同样放：兜底反应代表"这次操作成功了"，语义一致。
        _publish(CMD_BURST)
    return reacted


def on_plugin_operation_started(action: str, *, plugin_id: str = "") -> bool:
    """插件管理操作开始（长任务）：宠物进入"处理中"的瞬态反馈。"""
    reaction = PLUGIN_OPERATION_REACTIONS.get(str(action), {}).get("start", FALLBACK_PLUGIN_REACTION)
    state, hold_ms = reaction
    return _react(state, hold_ms, action=str(action), plugin=str(plugin_id), phase="start")


# ----------------------------------------------------------------------
# 宠物自身设置 / 诊断
# ----------------------------------------------------------------------
def on_pet_setting_changed(key: str, value: Any) -> bool:
    """宠物设置页保存项变化时，经事件协议同步到宠物。"""
    return _publish(CMD_SETTING, {"key": key, "value": value})


def on_debug_burst() -> bool:
    """诊断入口：只触发粒子特效，不改变情绪（程序化调用，无固定 UI 落点）。"""
    return _publish(CMD_BURST)


# ----------------------------------------------------------------------
# 窗口生命周期
# ----------------------------------------------------------------------
def on_window_shown() -> bool:
    """主窗口从托盘恢复：宠物"醒过来"看一眼。"""
    return _react("waking", DEFAULT_REACT_MS)


def on_window_hidden() -> bool:
    """主窗口收进托盘：宠物打个盹表示"待命中"。"""
    return _react("drowsy", DEFAULT_REACT_MS)


def on_quit() -> bool:
    """应用退出：宠物播一次关机反应。"""
    return _publish(CMD_REACT, {"state": "powering-down", "hold_ms": LONG_REACT_MS})


__all__ = [
    "DEFAULT_REACT_MS",
    "FALLBACK_PLUGIN_REACTION",
    "LONG_REACT_MS",
    "OWNER",
    "PLUGIN_OPERATION_REACTIONS",
    "on_debug_burst",
    "on_language_changed",
    "on_layout_changed",
    "on_page_switched",
    "on_pet_setting_changed",
    "on_plugin_operation",
    "on_plugin_operation_started",
    "on_quit",
    "on_search_closed",
    "on_search_opened",
    "on_settings_closed",
    "on_settings_opened",
    "on_theme_changed",
    "on_theme_cycled",
    "on_window_hidden",
    "on_window_shown",
]
