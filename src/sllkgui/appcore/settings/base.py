"""基座设置页声明：外观 / 界面 / 启动与窗口。

这里是「基座级设置按全局能力分类」的唯一来源。配置值仍落在历史
``settings/user.yaml``（通过 ``storage_key`` 映射），因此升级不需要迁移
旧文件；插件设置则走独立命名空间与独立文件。

页面文本一律给 ``label_key`` / ``hint_key``，由 ``Language`` 在渲染时解析，
语言切换后重建界面即可得到新文案。
"""

from __future__ import annotations

from typing import TypedDict

from .schema import SettingControl, SettingOption, SettingsPage, SettingSpec, SettingsSection


class _CoreDefaults(TypedDict):
    """核心设置页的默认值：类型固定，避免取值后退化为 ``object``。"""

    theme: str
    language: str
    transparency: int


#: 基座页面 ID（左侧导航与测试复用）
PAGE_APPEARANCE = "appearance"
PAGE_INTERFACE = "interface"
PAGE_WINDOW = "window"

#: 基座配置在 user.yaml 中的历史键名
STORAGE_THEME = "theme_name"
STORAGE_LANGUAGE = "language"
STORAGE_MENU_MODE = "menu_mode"
STORAGE_DRAWER_MODE = "drawer_mode"
STORAGE_TRANSPARENCY = "acrylic_transparency"
STORAGE_GLASS_STRENGTH = "glass_strength"
STORAGE_BACKGROUND_IMAGE = "background_image"
STORAGE_BACKGROUND_FIT = "background_fit"
STORAGE_REMEMBER_SIZE = "remember_window_size"

#: 主题实时预览键（宿主据此还原 / 应用）
KEY_THEME = f"core.{PAGE_APPEARANCE}.theme"
KEY_TRANSPARENCY = f"core.{PAGE_APPEARANCE}.transparency"
KEY_GLASS_STRENGTH = f"core.{PAGE_APPEARANCE}.glass_strength"
KEY_BACKGROUND_IMAGE = f"core.{PAGE_APPEARANCE}.background_image"
KEY_BACKGROUND_FIT = f"core.{PAGE_APPEARANCE}.background_fit"
KEY_LANGUAGE = f"core.{PAGE_INTERFACE}.language"
KEY_MENU_MODE = f"core.{PAGE_INTERFACE}.menu_mode"
KEY_DRAWER_MODE = f"core.{PAGE_INTERFACE}.drawer_mode"
KEY_REMEMBER_SIZE = f"core.{PAGE_WINDOW}.remember_size"


#: 语言显示名：不在表里的语言直接显示代码，新增语言无需改动这里
_LANGUAGE_LABELS = {
    "zh_cn": "简体中文",
    "zh_tw": "繁體中文",
    "en_us": "English",
    "ja_jp": "日本語",
}


def _language_options(default: str) -> list[tuple[str, str]]:
    """按当前资源根动态发现语言，避免应用追加语言后设置页看不到。

    ``LANGUAGE_OPTIONS`` 是惰性视图（随 ``configure(resource_dirs=...)`` 变化），
    因此必须运行期读取，不能固化成模块级常量。
    """
    try:
        from ..sysx.modules.language_module import LANGUAGE_OPTIONS

        codes = [str(code) for code in LANGUAGE_OPTIONS]
    except Exception:  # noqa: BLE001 - 配置未就绪时回落到基座内置四种
        codes = ["zh_cn", "zh_tw", "en_us", "ja_jp"]
    if default and default not in codes:
        codes.insert(0, default)
    return [(code, _LANGUAGE_LABELS.get(code, code)) for code in codes]


def _defaults() -> _CoreDefaults:
    """从当前配置读取默认值；配置不可用时回落到硬编码值。"""
    theme = "default"
    language = "zh_cn"
    transparency = 40
    try:
        from ..sysx import AppSettings

        theme = str(AppSettings.theme_name)
        language = str(AppSettings.language)
        # ``acrylic.opacity`` 越大越不透明，而设置项 ``transparency`` 越大越透明，
        # 两者互为补数——直接拿 opacity 当默认值会让"打开设置未改动就保存"改变观感。
        transparency = 100 - int(AppSettings.acrylic.opacity)
    except Exception:  # noqa: BLE001 - 配置未就绪时组件仍可构造
        pass
    transparency = max(0, min(100, transparency))
    return {"theme": theme, "language": language, "transparency": transparency}


def build_core_pages() -> tuple[SettingsPage, ...]:
    """构造三张基座设置页（每次调用返回新对象，便于测试隔离）。"""
    defaults = _defaults()

    appearance = SettingsPage(
        page_id=PAGE_APPEARANCE,
        title="外观",
        hint="调整主题、材质与背景。",
        title_key="language.UI.ui_SettingsPageAppearance",
        hint_key="language.UI.ui_SettingsPageAppearanceHint",
        icon="icon_palette",
        order=10,
        sections=(
            SettingsSection(
                section_id="theme",
                title="主题",
                hint="选择界面配色。",
                title_key="language.UI.ui_Theme",
                hint_key="language.UI.ui_ThemeHint",
                items=(
                    SettingSpec.theme(
                        "theme",
                        str(defaults["theme"]),
                        "配色方案",
                        label_key="language.UI.ui_SettingsThemeScheme",
                        hint_key="language.UI.ui_SettingsThemeSchemeHint",
                        storage_key=STORAGE_THEME,
                    ),
                ),
            ),
            SettingsSection(
                section_id="material",
                title="材质与通透度",
                hint="调整窗口的通透感与模糊质感。",
                title_key="language.UI.ui_Material",
                hint_key="language.UI.ui_MaterialHint",
                items=(
                    SettingSpec.slider(
                        "transparency",
                        int(defaults["transparency"]),
                        "窗口透明度",
                        hint="数值越大，桌面内容透出越明显。",
                        label_key="language.UI.ui_Transparency",
                        hint_key="language.UI.ui_TransparencyHint",
                        live_preview=True,
                        storage_key=STORAGE_TRANSPARENCY,
                    ),
                    SettingSpec.slider(
                        "glass_strength",
                        0,
                        "亚克力质感强度",
                        hint="数值越大，模糊质感越明显。",
                        label_key="language.UI.ui_GlassStrength",
                        hint_key="language.UI.ui_GlassStrengthHint",
                        live_preview=True,
                        storage_key=STORAGE_GLASS_STRENGTH,
                    ),
                ),
            ),
            SettingsSection(
                section_id="background",
                title="背景",
                hint="设置窗口背景图片与显示方式。",
                title_key="language.UI.ui_SettingsSectionBackground",
                hint_key="language.UI.ui_BackgroundHint",
                items=(
                    SettingSpec.path(
                        "background_image",
                        "",
                        "背景图片",
                        hint="选择图片作为窗口背景。",
                        label_key="language.UI.ui_SettingsBackgroundImage",
                        hint_key="language.UI.ui_SettingsBackgroundImageHint",
                        live_preview=True,
                        storage_key=STORAGE_BACKGROUND_IMAGE,
                    ),
                    SettingSpec.select(
                        "background_fit",
                        "fill",
                        "适应模式",
                        [
                            SettingOption("fill", "填充", "language.UI.ui_FitFill"),
                            SettingOption("fit", "适应", "language.UI.ui_FitFit"),
                            SettingOption("stretch", "拉伸", "language.UI.ui_FitStretch"),
                            SettingOption("tile", "平铺", "language.UI.ui_FitTile"),
                            SettingOption("center", "居中", "language.UI.ui_FitCenter"),
                        ],
                        hint="选择图片的填充方式。",
                        label_key="language.UI.ui_BackgroundFit",
                        hint_key="language.UI.ui_SettingsBackgroundFitHint",
                        live_preview=True,
                        storage_key=STORAGE_BACKGROUND_FIT,
                    ),
                ),
            ),
        ),
    )

    interface = SettingsPage(
        page_id=PAGE_INTERFACE,
        title="界面",
        hint="设置界面语言与布局方式。",
        title_key="language.UI.ui_SettingsPageInterface",
        hint_key="language.UI.ui_SettingsPageInterfaceHint",
        icon="icon_config",
        order=20,
        sections=(
            SettingsSection(
                section_id="language",
                title="语言与区域",
                hint="选择界面显示语言。",
                title_key="language.UI.ui_SettingsSectionLanguage",
                hint_key="language.UI.ui_LanguageHint",
                items=(
                    SettingSpec.select(
                        "language",
                        str(defaults["language"]),
                        "界面语言",
                        _language_options(str(defaults["language"])),
                        hint="",
                        label_key="language.UI.ui_Language",
                        hint_key="",
                        storage_key=STORAGE_LANGUAGE,
                    ),
                ),
            ),
            SettingsSection(
                section_id="layout",
                title="布局模式",
                hint="选择抽屉的展开方式。",
                title_key="language.UI.ui_SettingsSectionLayout",
                hint_key="language.UI.ui_SettingsSectionLayoutHint",
                items=(
                    SettingSpec.select(
                        "menu_mode",
                        "static",
                        "左侧菜单",
                        [
                            SettingOption("static", "固定", "language.UI.ui_ModeStatic"),
                            SettingOption("overlay", "浮层", "language.UI.ui_ModeOverlay"),
                        ],
                        hint="图标菜单的展开方式，不影响页面内容宽度。",
                        label_key="language.UI.ui_MenuMode",
                        hint_key="language.UI.ui_MenuModeHint",
                        control=SettingControl.SEGMENTED,
                        storage_key=STORAGE_MENU_MODE,
                    ),
                    SettingSpec.select(
                        "drawer_mode",
                        "static",
                        "抽屉模式",
                        [
                            SettingOption("static", "固定", "language.UI.ui_ModeStatic"),
                            SettingOption("overlay", "浮层", "language.UI.ui_ModeOverlay"),
                        ],
                        hint="选择侧边抽屉的展开方式。",
                        label_key="language.UI.ui_DrawerMode",
                        hint_key="language.UI.ui_DrawerModeHint",
                        control=SettingControl.SEGMENTED,
                        storage_key=STORAGE_DRAWER_MODE,
                    ),
                ),
            ),
        ),
    )

    window = SettingsPage(
        page_id=PAGE_WINDOW,
        title="启动与窗口",
        hint="设置窗口尺寸与启动行为。",
        title_key="language.UI.ui_SettingsPageWindow",
        hint_key="language.UI.ui_SettingsPageWindowHint",
        icon="icon_widget",
        order=30,
        sections=(
            SettingsSection(
                section_id="startup",
                title="启动",
                hint="控制下次启动时的窗口尺寸。",
                title_key="language.UI.ui_SettingsSectionStartup",
                hint_key="language.UI.ui_SettingsSectionStartupHint",
                items=(
                    SettingSpec.switch(
                        "remember_size",
                        True,
                        "记住窗口尺寸",
                        hint="关闭后，下次启动使用默认窗口尺寸。",
                        label_key="language.UI.ui_SettingsRememberWindowSize",
                        hint_key="language.UI.ui_SettingsRememberWindowSizeHint",
                        storage_key=STORAGE_REMEMBER_SIZE,
                    ),
                ),
            ),
        ),
    )

    return (appearance, interface, window)


__all__ = [
    "KEY_BACKGROUND_FIT",
    "KEY_BACKGROUND_IMAGE",
    "KEY_DRAWER_MODE",
    "KEY_GLASS_STRENGTH",
    "KEY_LANGUAGE",
    "KEY_MENU_MODE",
    "KEY_REMEMBER_SIZE",
    "KEY_THEME",
    "KEY_TRANSPARENCY",
    "PAGE_APPEARANCE",
    "PAGE_INTERFACE",
    "PAGE_WINDOW",
    "build_core_pages",
]
