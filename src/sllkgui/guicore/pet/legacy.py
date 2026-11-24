"""旧宠物偏好迁移：pet.yaml / plugin.sllkgui.pet.yaml -> core user.yaml。

一次性迁移两种历史来源：
1. settings/pet.yaml（最早版本）；
2. settings/plugins/sllkgui.pet.yaml（4.1–4.4 的插件命名空间版本）。
迁移后把旧文件改名 .migrated 备份；core 键落 user.yaml。
"""

from __future__ import annotations

from sllkgui.appcore import Logger, settings_store, user_settings_path

from .settings import DEFAULTS, STORAGE_KEYS

BACKUP_SUFFIX = ".migrated"
LEGACY_PLUGIN_ID = "sllkgui.pet"


def _migrate_file(source, updates: dict) -> bool:
    """把一个旧文件的值写入 core；无论成功与否都备份，避免重复迁移。"""
    import yaml

    if not source.is_file():
        return False
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        Logger.warning(f"旧宠物配置读取失败，跳过迁移: {source}: {exc}")
        return False
    if isinstance(raw, dict):
        for key in DEFAULTS:
            if key in raw:
                updates[STORAGE_KEYS[key]] = raw[key]
    try:
        source.rename(source.with_suffix(BACKUP_SUFFIX))
    except OSError as exc:
        Logger.warning(f"旧宠物配置备份失败: {source}: {exc}")
        return False
    return True


def migrate_legacy_pet_preferences() -> bool:
    """迁移所有历史来源；失败只告警，绝不抛异常。"""
    settings_dir = user_settings_path().parent
    updates: dict[str, object] = {}
    migrated = _migrate_file(settings_dir / "pet.yaml", updates)
    migrated = _migrate_file(settings_dir / "plugins" / (LEGACY_PLUGIN_ID + ".yaml"), updates) or migrated
    if not updates:
        return migrated
    ok = bool(settings_store().save("core", updates))
    if ok:
        Logger.info("旧宠物配置已迁移到基座原生设置")
    return ok


__all__ = ["migrate_legacy_pet_preferences"]
