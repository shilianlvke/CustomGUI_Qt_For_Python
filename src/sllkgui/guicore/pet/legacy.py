"""旧宠物偏好文件迁移：settings/pet.yaml -> 基座统一设置存储。

只迁移一次：读取旧文件后写入 SettingsStore（plugin.sllkgui.pet 命名空间），
无论写入成功与否都会把旧文件改名备份，避免每次启动重复迁移；
备份文件保留在 settings 目录，用户可随时取回。
"""

from __future__ import annotations

from sllkgui.appcore import Logger, settings_store, user_settings_path

from .settings import DEFAULTS, KEY_PREFIX, PET_NAMESPACE

BACKUP_SUFFIX = ".migrated"


def migrate_legacy_pet_preferences() -> bool:
    """迁移旧配置；不存在/已迁移/失败都返回 False，绝不抛异常。"""
    import yaml

    settings_dir = user_settings_path().parent
    legacy = settings_dir / "pet.yaml"
    if not legacy.is_file():
        return False
    try:
        raw = yaml.safe_load(legacy.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        Logger.warning(f"旧宠物配置读取失败，跳过迁移: {exc}")
        return False
    if not isinstance(raw, dict):
        raw = {}
    updates = {KEY_PREFIX + key: raw[key] for key in DEFAULTS if key in raw}
    ok = bool(settings_store().save(PET_NAMESPACE, updates)) if updates else True
    try:
        legacy.rename(legacy.with_suffix(BACKUP_SUFFIX))
    except OSError as exc:
        Logger.warning(f"旧宠物配置备份失败: {exc}")
        return False
    if ok:
        Logger.info("旧宠物配置已迁移到统一设置存储")
    return ok


__all__ = ["migrate_legacy_pet_preferences"]
