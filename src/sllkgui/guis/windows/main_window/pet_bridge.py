"""基座操作 → 桌面宠物事件桥。

把基座中的用户操作按宠物事件协议发布为命令/反馈，使宠物能响应主题切换、
设置窗口开关、搜索、菜单/抽屉模式变化等。发布走统一 pet_bus，
遵循事件命名/载荷/错误处理规则；宠物未启动或事件总线异常均静默降级。
"""

from __future__ import annotations

from typing import Any

from sllkgui.appcore import Logger
from sllkgui.guicore.pet.events import (
    CMD_BURST,
    CMD_HOP,
    CMD_SETTING,
    CMD_SPIN,
    CMD_STATE,
    pet_bus,
)

OWNER = "sllkgui.base"


def _publish(topic: str, payload: dict[str, Any] | None = None) -> bool:
    """发布宠物事件；任何失败只告警并返回 False，不影响基座操作。"""
    try:
        return bool(pet_bus().handle(OWNER).publish(topic, payload))
    except Exception as exc:  # noqa: BLE001 - 事件桥绝不打断主流程
        Logger.debug(f"宠物事件桥发布失败 {topic}: {exc}")
        return False


def on_theme_cycled(theme: str) -> bool:
    """主题切换：宠物做出雀跃反馈并切到高兴状态。"""
    _publish(CMD_HOP)
    return _publish(CMD_STATE, {"state": "happy"})


def on_settings_opened() -> bool:
    """打开设置窗口：宠物切到专注/好奇状态。"""
    return _publish(CMD_STATE, {"state": "curious"})


def on_search_opened() -> bool:
    """打开搜索：宠物切到搜索状态。"""
    return _publish(CMD_STATE, {"state": "searching"})


def on_layout_changed(mode: str) -> bool:
    """布局模式变化：转一圈作为视觉反馈。"""
    return _publish(CMD_SPIN)


def on_pet_setting_changed(key: str, value: Any) -> bool:
    """宠物设置页保存项变化时，经事件协议同步到宠物。"""
    return _publish(CMD_SETTING, {"key": key, "value": value})


def on_debug_burst() -> bool:
    """调试/诊断入口：触发粒子特效。"""
    return _publish(CMD_BURST)


__all__ = [
    "on_debug_burst",
    "on_layout_changed",
    "on_pet_setting_changed",
    "on_search_opened",
    "on_settings_opened",
    "on_theme_cycled",
]
