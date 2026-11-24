"""桌面宠物设置页：复用基座统一设置系统。

宠物偏好以 plugin.sllkgui.pet 命名空间注册：
- 设置页出现在设置窗口的插件分组；
- 值写 settings/plugins/sllkgui.pet.yaml，由 SettingsStore 统一读写；
- 控制器订阅 settings_change_bus 同名命名空间，保存后即时同步；
- 旧的 settings/pet.yaml 在首次加载时迁移一次，随后不再写入。
"""

from __future__ import annotations

from typing import Any

from sllkgui.appcore import Setting, SettingsPage, SettingsSection, plugin_namespace

from .engine.core import PALETTE, SHAPES

PET_PLUGIN_ID = "sllkgui.pet"
PET_NAMESPACE = plugin_namespace(PET_PLUGIN_ID)
PAGE_ID = "pet"
KEY_PREFIX = PET_NAMESPACE + "."

DEFAULTS: dict[str, Any] = {
    "show_pet": True,
    "follow_pointer": True,
    "pinned": True,
    "shape": "blob",
    "color": "green",
    "size": 220,
    "deco_scale": 1.32,
}


def build_pet_page() -> SettingsPage:
    """构造宠物设置页（每次返回新对象，便于测试隔离）。"""
    return SettingsPage(
        page_id=PAGE_ID,
        namespace=PET_NAMESPACE,
        title="猕猴桃桌面宠物",
        hint="常驻桌面宠物的展示、外观与交互。",
        title_key="language.UI.ui_PetSettingsTitle",
        hint_key="language.UI.ui_PetSettingsHint",
        icon="icon_palette",
        order=15,
        sections=(
            SettingsSection(
                section_id="display",
                title="展示",
                hint="控制宠物是否显示以及窗口行为。",
                title_key="language.UI.ui_PetSectionDisplay",
                hint_key="language.UI.ui_PetSectionDisplayHint",
                items=(
                    Setting.switch(
                        "show_pet",
                        True,
                        "显示宠物",
                        label_key="language.UI.ui_PetShow",
                        hint_key="language.UI.ui_PetShowHint",
                    ),
                    Setting.switch(
                        "pinned",
                        True,
                        "窗口置顶",
                        label_key="language.UI.ui_PetPinned",
                        hint_key="language.UI.ui_PetPinnedHint",
                    ),
                    Setting.switch(
                        "follow_pointer",
                        True,
                        "眼睛跟随指针",
                        label_key="language.UI.ui_PetFollow",
                        hint_key="language.UI.ui_PetFollowHint",
                    ),
                ),
            ),
            SettingsSection(
                section_id="appearance",
                title="外观",
                hint="果形、果肉色与特效层大小。",
                title_key="language.UI.ui_PetSectionAppearance",
                hint_key="language.UI.ui_PetSectionAppearanceHint",
                items=(
                    Setting.select(
                        "shape",
                        "blob",
                        "果形",
                        [(k, v.get("label", k)) for k, v in SHAPES.items()],
                        label_key="language.UI.ui_PetShape",
                        hint_key="language.UI.ui_PetShapeHint",
                    ),
                    Setting.select(
                        "color",
                        "green",
                        "果肉色",
                        [(k, v.get("label", k)) for k, v in PALETTE.items()],
                        label_key="language.UI.ui_PetColor",
                        hint_key="language.UI.ui_PetColorHint",
                    ),
                    Setting.number(
                        "size",
                        220,
                        "宠物尺寸(px)",
                        minimum=96,
                        maximum=480,
                        label_key="language.UI.ui_PetSize",
                        hint_key="language.UI.ui_PetSizeHint",
                    ),
                    Setting.number(
                        "deco_scale",
                        1.32,
                        "特效层缩放",
                        minimum=0.55,
                        maximum=1.5,
                        step=0.05,
                        decimals=2,
                        label_key="language.UI.ui_PetDecoScale",
                        hint_key="language.UI.ui_PetDecoScaleHint",
                    ),
                ),
            ),
        ),
    )


def register_pet_page(*, replace: bool = False):
    """把宠物页注册到基座全局设置注册表（幂等）。"""
    from sllkgui.appcore import settings_registry

    return settings_registry().register(build_pet_page(), replace=replace)


__all__ = ["DEFAULTS", "KEY_PREFIX", "PAGE_ID", "PET_NAMESPACE", "PET_PLUGIN_ID", "build_pet_page", "register_pet_page"]
