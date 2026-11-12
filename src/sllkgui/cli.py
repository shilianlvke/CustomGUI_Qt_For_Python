"""``sllkgui`` 命令行入口。

职责边界：

============  ============================================================
``gallery``   只加载基座内置组件预览，不读插件存储/源、不联网
``run``       加载核心插件 + 已安装插件（+ ``--plugin-dir`` 开发插件）
``plugin``    源搜索、安装、更新、回滚、卸载、启停、校验、lint
``source``    源列表、添加、移除、刷新
``doctor``    路径与安装状态诊断
``scaffold``  生成插件/源仓库骨架
============  ============================================================

``plugin`` / ``source`` / ``doctor`` / ``scaffold`` 不导入 PySide6，可在无
显示环境运行；只有 ``gallery`` / ``run`` 才启动 Qt。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

__all__ = ["build_parser", "main"]


# ----------------------------------------------------------------------
# 通用
# ----------------------------------------------------------------------
def _version() -> str:
    from sllkgui import __version__

    return __version__


def _absolute(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _print(message: str = "") -> None:
    print(message)


def _emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if isinstance(payload, list):
        for item in payload:
            print(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False))
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2) if isinstance(payload, dict) else payload)


def _confirm(args: argparse.Namespace, message: str) -> bool:
    if getattr(args, "yes", False):
        return True
    if not sys.stdin.isatty():
        print(f"✗ {message}（非交互环境请加 --yes）")
        return False
    answer = input(f"{message} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _gallery_dir(args: argparse.Namespace) -> Path:
    from sllkgui.appcore.sysx.config.paths import data_root, gallery_root

    explicit = _absolute(getattr(args, "gallery_dir", None))
    if explicit is not None:
        return explicit
    data = _absolute(getattr(args, "data_dir", None))
    if data is not None:
        return data / "gallery"
    return gallery_root() or (data_root() / "gallery")


def _services(args: argparse.Namespace):
    """构造不依赖 Qt 的 store/state/source/manager。"""
    from sllkgui import __version__
    from sllkgui.gallery.manager import PluginManager
    from sllkgui.gallery.source import SourceManager
    from sllkgui.gallery.state import load_registry, load_sources
    from sllkgui.gallery.store import GalleryStore

    store = GalleryStore(_gallery_dir(args))
    store.ensure_layout()
    state = load_registry(store.registry_file, base_version=__version__)
    sources_state = load_sources(store.sources_file)
    sources = SourceManager(store, sources_state, allow_local=bool(getattr(args, "allow_local", False)))
    sources.ensure_official()
    manager = PluginManager(store, state, sources, base_version=__version__)
    return store, state, sources, manager


# ----------------------------------------------------------------------
# gallery / run
# ----------------------------------------------------------------------
def _cmd_window(args: argparse.Namespace, mode: str) -> int:
    import sllkgui

    data_dir = _absolute(getattr(args, "data_dir", None))
    gallery_dir = _absolute(getattr(args, "gallery_dir", None))
    if data_dir is not None or gallery_dir is not None:
        sllkgui.configure(
            data_dir=data_dir,
            gallery_dir=gallery_dir,
            force_reload=True,
        )

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from sllkgui.appcore import (
        AppLanguages,
        AppSettings,
        AppThemes,
        ColorPalette,
        Language,
        PathFactory,
        get_app_context,
    )

    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = PathFactory.set_ico(AppSettings.logo)
    if icon_path and Path(icon_path).is_file():
        app.setWindowIcon(QIcon(icon_path))

    from sllkgui.window import load_gallery, load_run

    if mode == "gallery":
        window = load_gallery(route=args.surface or "", data_dir=data_dir)
    else:
        window = load_run(
            route=args.surface or "",
            data_dir=data_dir,
            gallery_dir=gallery_dir,
            plugin_dirs=[Path(item).expanduser().resolve() for item in (args.plugin_dir or [])],
            safe_mode=bool(args.safe_mode),
            allow_local=bool(getattr(args, "allow_local", False)),
        )
    window.show()
    return int(app.exec())


def _cmd_gallery(args: argparse.Namespace) -> int:
    return _cmd_window(args, "gallery")


def _cmd_run(args: argparse.Namespace) -> int:
    return _cmd_window(args, "run")


# ----------------------------------------------------------------------
# source
# ----------------------------------------------------------------------
def _cmd_source_list(args: argparse.Namespace) -> int:
    _store, _state, sources, _manager = _services(args)
    rows = [
        {
            "id": item.source_id,
            "url": item.url,
            "trust": item.trust,
            "enabled": item.enabled,
            "last_refresh": item.last_refresh,
            "commit": item.commit,
        }
        for item in sources.list()
    ]
    _emit(rows, args.json)
    return 0


def _cmd_source_add(args: argparse.Namespace) -> int:
    _store, _state, sources, _manager = _services(args)
    record = sources.add(
        args.url,
        source_id=args.id or "",
        trust=args.trust,
        refresh=bool(args.refresh),
    )
    _print(f"✓ 已添加源 {record.source_id}: {record.url}")
    return 0


def _cmd_source_remove(args: argparse.Namespace) -> int:
    _store, _state, sources, _manager = _services(args)
    if not _confirm(args, f"确定移除源 {args.id}？"):
        return 1
    sources.remove(args.id)
    _print(f"✓ 已移除源 {args.id}")
    return 0


def _cmd_source_refresh(args: argparse.Namespace) -> int:
    _store, _state, sources, _manager = _services(args)
    if args.id:
        records = [sources.refresh(args.id)]
    else:
        records = sources.refresh_all()
    for record in records:
        _print(f"✓ {record.source_id} @ {record.commit[:8]}")
    return 0


def _cmd_source_info(args: argparse.Namespace) -> int:
    _store, _state, sources, _manager = _services(args)
    info = sources.info(args.id)
    _emit(
        {
            "id": info.source_id,
            "name": info.name,
            "description": info.description,
            "maintainers": list(info.maintainers),
            "homepage": info.homepage,
            "updated_at": info.updated_at,
            "path": str(info.path or ""),
        },
        args.json,
    )
    return 0


# ----------------------------------------------------------------------
# plugin
# ----------------------------------------------------------------------
def _cmd_plugin_search(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    _emit(manager.search(args.query or "", source_id=args.source or ""), args.json)
    return 0


def _cmd_plugin_info(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    _emit(manager.info(args.id), True)
    return 0


def _cmd_plugin_install(args: argparse.Namespace) -> int:
    _store, _state, sources, manager = _services(args)
    if args.url:
        if not _confirm(args, f"从 {args.url} 安装插件？"):
            return 1
        result = manager.install(url=args.url, ref=args.ref or "", allow_local=bool(args.allow_local))
    else:
        if not args.id:
            _print("✗ 必须提供插件 id 或 --url")
            return 1
        entry = manager.info(args.id)["sources"]
        permissions = ""
        if entry:
            version = next((item for item in entry[0]["versions"] if not item["yanked"]), None)
            permissions = ", ".join(version["permissions"]) if version and "permissions" in version else "-"
        if not _confirm(args, f"安装 {args.id}？权限：{permissions or '-'}"):
            return 1
        result = manager.install(
            args.id,
            version=args.version or "",
            source_id=args.source or "",
            allow_local=bool(sources.allow_local),
        )
    _emit(result, args.json)
    return 0


def _cmd_plugin_list(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    _emit(manager.installed_rows(), args.json)
    return 0


def _cmd_plugin_update(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    if args.all:
        results = manager.update_all(dry_run=bool(args.dry_run))
    else:
        if not args.id:
            _print("✗ 必须提供插件 id 或 --all")
            return 1
        results = [manager.update(args.id, dry_run=bool(args.dry_run))]
    _emit(results, args.json)
    return 0


def _cmd_plugin_rollback(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    _emit(manager.rollback(args.id), args.json)
    return 0


def _cmd_plugin_remove(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    if not _confirm(args, f"确定卸载 {args.id}？"):
        return 1
    _emit(manager.remove(args.id, force=bool(args.force), purge=bool(args.purge)), args.json)
    return 0


def _cmd_plugin_toggle(args: argparse.Namespace, enabled: bool) -> int:
    _store, _state, _sources, manager = _services(args)
    _emit(manager.set_enabled(args.id, enabled), args.json)
    return 0


def _cmd_plugin_verify(args: argparse.Namespace) -> int:
    _store, _state, _sources, manager = _services(args)
    results = manager.verify(args.id or "")
    _emit(results, args.json)
    return 0 if all(item["ok"] for item in results) else 1


def _cmd_plugin_lint(args: argparse.Namespace) -> int:
    from sllkgui.gallery.lint import lint_plugin

    report = lint_plugin(Path(args.path))
    _emit(report.to_dict(), args.json)
    if not report.ok:
        return 1
    return 0


def _cmd_plugin_doctor(args: argparse.Namespace) -> int:
    store, state, sources, _manager = _services(args)
    payload = {
        "base_version": _version(),
        "gallery_dir": str(store.root),
        "registry": str(store.registry_file),
        "sources_file": str(store.sources_file),
        "sources": [item.source_id for item in sources.list()],
        "plugins": [
            {"id": record.plugin_id, "version": record.version, "enabled": record.enabled}
            for record in state.plugins.values()
        ],
    }
    _emit(payload, args.json)
    return 0


# ----------------------------------------------------------------------
# doctor / scaffold
# ----------------------------------------------------------------------
def _cmd_doctor(args: argparse.Namespace) -> int:
    from sllkgui import package_root
    from sllkgui.appcore.sysx.config.paths import data_root, gallery_root, resource_roots

    store, state, sources, _manager = _services(args)
    payload = {
        "version": _version(),
        "package_root": str(package_root()),
        "resource_roots": [str(item) for item in resource_roots()],
        "data_root": str(data_root()),
        "gallery_root": str(gallery_root()),
        "gallery_dir": str(store.root),
        "sources": [item.source_id for item in sources.list()],
        "installed": [
            {"id": record.plugin_id, "version": record.version, "enabled": record.enabled}
            for record in state.plugins.values()
        ],
    }
    if args.json:
        _emit(payload, True)
        return 0
    _print("SllkGUI doctor")
    _print("=" * 56)
    for key, value in payload.items():
        if isinstance(value, list):
            _print(f"{key}:")
            for item in value:
                _print(f"  - {item}")
        else:
            _print(f"{key}: {value}")
    return 0


def _cmd_scaffold(args: argparse.Namespace) -> int:
    from sllkgui.gallery.scaffold import scaffold_plugin, scaffold_source

    if args.source:
        target = scaffold_source(
            Path(args.dir),
            source_id=args.id or "my-team",
            source_name=args.name or "My SllkGUI Source",
        )
    else:
        target = scaffold_plugin(
            Path(args.dir),
            plugin_id=args.id or "com.example.sample",
            name=args.name or "Sample",
        )
    _print(f"✓ 已生成模板: {target}")
    return 0


# ----------------------------------------------------------------------
# 解析器
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sllkgui", description="SllkGUI —— 基于 PySide6 的桌面 UI 基座。")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    sub = parser.add_subparsers(dest="command")

    gallery = sub.add_parser("gallery", help="组件预览模式（只加载内置预览插件）")
    gallery.add_argument("--surface", help="直接打开的路由 plugin_id/surface_id")
    gallery.add_argument("--data-dir", help="可写数据目录")
    gallery.set_defaults(func=_cmd_gallery)

    run = sub.add_parser("run", help="运行模式（核心插件 + 已安装插件）")
    run.add_argument("--surface", help="直接打开的路由 plugin_id/surface_id")
    run.add_argument("--data-dir", help="可写数据目录")
    run.add_argument("--gallery-dir", help="插件安装根目录")
    run.add_argument("--plugin-dir", action="append", help="本地开发插件目录（可重复）")
    run.add_argument("--safe-mode", action="store_true", help="只加载核心插件")
    run.add_argument("--allow-local", action="store_true", help="允许 file:// 插件源")
    run.set_defaults(func=_cmd_run)

    source = sub.add_parser("source", help="插件源管理")
    source_sub = source.add_subparsers(dest="source_command")
    source_common = dict(
        data_dir=("--data-dir", {"help": "可写数据目录"}),
        gallery_dir=("--gallery-dir", {"help": "插件安装根目录"}),
        allow_local=("--allow-local", {"action": "store_true", "help": "允许 file:// 源"}),
        json=("--json", {"action": "store_true", "help": "输出 JSON"}),
    )

    def _with_common(target: argparse.ArgumentParser) -> argparse.ArgumentParser:
        for name, kwargs in source_common.values():
            target.add_argument(name, **kwargs)
        return target

    src_list = _with_common(source_sub.add_parser("list", help="列出源"))
    src_list.set_defaults(func=_cmd_source_list)
    src_add = _with_common(source_sub.add_parser("add", help="添加源"))
    src_add.add_argument("url")
    src_add.add_argument("--id", help="源 id（默认从 URL 推导）")
    src_add.add_argument("--trust", choices=("user", "official"), default="user")
    src_add.add_argument("--refresh", action="store_true", help="添加后立即刷新")
    src_add.add_argument("--yes", action="store_true")
    src_add.set_defaults(func=_cmd_source_add)
    src_remove = _with_common(source_sub.add_parser("remove", help="移除源"))
    src_remove.add_argument("id")
    src_remove.add_argument("--yes", action="store_true")
    src_remove.set_defaults(func=_cmd_source_remove)
    src_refresh = _with_common(source_sub.add_parser("refresh", help="刷新源"))
    src_refresh.add_argument("id", nargs="?")
    src_refresh.add_argument("--all", action="store_true")
    src_refresh.set_defaults(func=_cmd_source_refresh)
    src_info = _with_common(source_sub.add_parser("info", help="源详情"))
    src_info.add_argument("id")
    src_info.set_defaults(func=_cmd_source_info)

    plugin = sub.add_parser("plugin", help="插件管理")
    plugin_sub = plugin.add_subparsers(dest="plugin_command")

    def _plugin_parser(name: str, help_text: str) -> argparse.ArgumentParser:
        target = _with_common(plugin_sub.add_parser(name, help=help_text))
        return target

    p_search = _plugin_parser("search", "搜索插件")
    p_search.add_argument("query", nargs="?")
    p_search.add_argument("--source")
    p_search.set_defaults(func=_cmd_plugin_search)
    p_info = _plugin_parser("info", "插件详情")
    p_info.add_argument("id")
    p_info.set_defaults(func=_cmd_plugin_info)
    p_install = _plugin_parser("install", "安装插件")
    p_install.add_argument("id", nargs="?")
    p_install.add_argument("--version")
    p_install.add_argument("--source")
    p_install.add_argument("--url")
    p_install.add_argument("--ref")
    p_install.add_argument("--yes", action="store_true")
    p_install.set_defaults(func=_cmd_plugin_install)
    p_list = _plugin_parser("list", "列出已安装插件")
    p_list.set_defaults(func=_cmd_plugin_list)
    p_update = _plugin_parser("update", "更新插件")
    p_update.add_argument("id", nargs="?")
    p_update.add_argument("--all", action="store_true")
    p_update.add_argument("--dry-run", action="store_true")
    p_update.add_argument("--yes", action="store_true")
    p_update.set_defaults(func=_cmd_plugin_update)
    p_rollback = _plugin_parser("rollback", "回滚插件")
    p_rollback.add_argument("id")
    p_rollback.set_defaults(func=_cmd_plugin_rollback)
    p_remove = _plugin_parser("remove", "卸载插件")
    p_remove.add_argument("id")
    p_remove.add_argument("--force", action="store_true")
    p_remove.add_argument("--purge", action="store_true")
    p_remove.add_argument("--yes", action="store_true")
    p_remove.set_defaults(func=_cmd_plugin_remove)
    p_enable = _plugin_parser("enable", "启用插件")
    p_enable.add_argument("id")
    p_enable.set_defaults(func=lambda args: _cmd_plugin_toggle(args, True))
    p_disable = _plugin_parser("disable", "禁用插件")
    p_disable.add_argument("id")
    p_disable.set_defaults(func=lambda args: _cmd_plugin_toggle(args, False))
    p_verify = _plugin_parser("verify", "校验已安装插件")
    p_verify.add_argument("id", nargs="?")
    p_verify.set_defaults(func=_cmd_plugin_verify)
    p_lint = _plugin_parser("lint", "检查插件开发规范")
    p_lint.add_argument("path")
    p_lint.set_defaults(func=_cmd_plugin_lint)
    p_doctor = _plugin_parser("doctor", "插件状态诊断")
    p_doctor.set_defaults(func=_cmd_plugin_doctor)

    doctor = _with_common(sub.add_parser("doctor", help="路径与安装状态诊断"))
    doctor.set_defaults(func=_cmd_doctor)

    scaffold = sub.add_parser("scaffold", help="生成插件/源仓库模板")
    scaffold.add_argument("dir")
    scaffold.add_argument("--id")
    scaffold.add_argument("--name")
    scaffold.add_argument("--source", action="store_true", help="生成源仓库模板")
    scaffold.set_defaults(func=_cmd_scaffold)

    return parser


def main(argv: list[str] | None = None) -> int:
    from sllkgui.gallery.errors import GalleryError

    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except GalleryError as exc:
        print(f"✗ {exc.code}: {exc.message}", file=sys.stderr)
        if exc.detail:
            print(f"  {exc.detail}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
