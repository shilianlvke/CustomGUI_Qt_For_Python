from __future__ import annotations

from pathlib import Path

import sllkgui
from sllkgui import package_root


def test_legacy_app_protocol_files_removed():
    root = package_root()
    for relative in (
        "guis/app_context.py",
        "guis/app_loader.py",
        "guis/app_manifest.py",
        "guis/app_namespace.py",
        "guis/app_state.py",
        "guis/app_v2.py",
        "appcore/sysx/modules/app_protocol.py",
        "appcore/sysx/modules/plugin_module.py",
    ):
        assert not (root / relative).exists(), relative


def test_legacy_exports_removed():
    import sllkgui.appcore as appcore

    for name in ("AppPlugin", "AppPage", "PluginRegistry", "MenuPlugin", "PagePlugin", "apps_root"):
        assert not hasattr(appcore, name), name


def test_apps_dir_env_no_longer_used(tmp_path: Path, monkeypatch):
    target = tmp_path / "apps"
    target.mkdir()
    monkeypatch.setenv("SLLKGUI_APPS_DIR", str(target))
    from sllkgui.appcore.sysx.config.paths import gallery_root

    sllkgui.reset_config()
    try:
        sllkgui.configure(env_fallback=False, force_reload=True)
        assert gallery_root() != target.resolve()
    finally:
        sllkgui.reset_config()
        sllkgui.configure(env_fallback=True, force_reload=True)
