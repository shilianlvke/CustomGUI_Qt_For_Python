"""桌面宠物设置页：基座原生设置（core 命名空间）。

宠物页已并入 :func:`sllkgui.appcore.settings.base.build_core_pages`，
出现在设置窗口的基座原生分类而非插件栏。本模块保留：
- 与引擎同源的默认值 DEFAULTS；
- 供控制器使用的命名空间/完整键常量（core.pet.*，存储键 pet_*）；
- 兼容旧调用方的 register_pet_page（core 页由 ensure_core_pages 统一注册）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sllkgui.appcore import SettingsPage

#: 基座原生设置命名空间（不再是 plugin.*）
PET_NAMESPACE = "core"
PAGE_ID = "pet"
KEY_PREFIX = "core.pet."

#: 默认偏好（与 base.py 的 pet_* storage_key 一一对应）
DEFAULTS: dict[str, Any] = {
    "show_pet": True,
    "follow_pointer": True,
    "pinned": True,
    "shape": "blob",
    "color": "green",
    "size": 100,
    "deco_scale": 1.32,
}

#: 偏好键 -> user.yaml 存储键
STORAGE_KEYS: dict[str, str] = {
    "show_pet": "pet_show",
    "pinned": "pet_pinned",
    "follow_pointer": "pet_follow_pointer",
    "shape": "pet_shape",
    "color": "pet_color",
    "size": "pet_size",
    "deco_scale": "pet_deco_scale",
}


def build_pet_page() -> SettingsPage:
    """返回基座原生宠物页（与 build_core_pages 中的定义一致）。"""
    from sllkgui.appcore.settings.base import PAGE_PET, _pet_page

    assert PAGE_PET == PAGE_ID
    return _pet_page()


def register_pet_page(*, replace: bool = False):
    """确保宠物页已注册；基座页由 ensure_core_pages 统一注册，这里幂等兜底。"""
    from sllkgui.appcore import ensure_core_pages, settings_registry

    pages = ensure_core_pages()
    for page in pages:
        if page.page_id == PAGE_ID:
            return page
    # 理论上不会发生；防御式地单独注册，保持旧调用方语义
    return settings_registry().register(build_pet_page(), replace=replace)


__all__ = [
    "DEFAULTS",
    "KEY_PREFIX",
    "PAGE_ID",
    "PET_NAMESPACE",
    "STORAGE_KEYS",
    "build_pet_page",
    "register_pet_page",
]
