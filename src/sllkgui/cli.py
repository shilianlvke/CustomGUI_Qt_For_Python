"""``sllkgui`` 命令行入口。

四个子命令，覆盖「装上就能看到东西」到「装错了能自己查」：

=================  ================================================
``run``            用指定（或自动发现）的应用目录启动主窗口
``install-demo``   把包内自带的 10 个示例应用复制到可写目录
``examples``       导出最小可运行工程骨架，作为新项目起点
``doctor``         打印全部路径与发现结果，排查「为什么窗口是空的」
=================  ================================================

``install-demo`` 与 ``examples`` 读的是内置示例目录：wheel 安装时在包内
（由 ``pyproject.toml`` 的 ``force-include`` 注入 ``sllkgui/apps`` 与
``sllkgui/examples``），源码树运行时回落到仓库根的 ``apps/`` 与
``examples/hello_world/`` —— 两种形态下命令行为一致。

设计约定：本模块只做命令行编排，不 import PySide6（``run`` 里延迟导入），
这样 ``sllkgui doctor`` 在没有显示环境的服务器上也能跑。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

__all__ = ["main"]


def _package_dir() -> Path:
    from sllkgui import package_root

    return package_root()


def _absolute(value: str | None) -> str | None:
    """把命令行给的相对路径按**当前工作目录**解析成绝对路径。

    ``--apps-dir apps`` 若原样下传，会被资源解析器当成「资源根下的相对路径」
    去 wheel 包内找，找到的是不存在的目录——用户看到「窗口是空的」而不是
    一条能读懂的报错。路径语义必须在入口处就定死。
    """
    if not value:
        return None
    return str(Path(value).expanduser().resolve())


def _bundled_dir(relative: str) -> Path | None:
    """内置示例目录：包内优先，源码树（仓库根）兜底。"""
    from sllkgui.appcore.sysx.config.paths import source_root

    for base in (_package_dir(), source_root()):
        if base is None:
            continue
        candidate = base / relative
        if candidate.is_dir():
            return candidate
    return None


def _demo_source() -> Path | None:
    """自带的示例应用目录（wheel 在包内，源码树在仓库 ``apps/``）。"""
    return _bundled_dir("apps")


def _example_source() -> Path | None:
    """最小可运行工程骨架目录。"""
    return _bundled_dir("examples/hello_world")


# ----------------------------------------------------------------------
# install-demo
# ----------------------------------------------------------------------
def _cmd_install_demo(args: argparse.Namespace) -> int:
    source = _demo_source()
    if source is None:
        print("✗ 找不到内置示例应用（包内与仓库 apps/ 都不存在）。")
        print("  请改用：sllkgui examples --copy DIR 导出最小工程骨架。")
        return 1

    from sllkgui.appcore.sysx.config.paths import data_root

    dest = Path(args.dest).expanduser().resolve() if args.dest else data_root() / "apps"
    dest.mkdir(parents=True, exist_ok=True)

    copied, skipped = [], []
    for app_dir in sorted(p for p in source.iterdir() if p.is_dir()):
        target = dest / app_dir.name
        if target.exists() and not args.force:
            skipped.append(app_dir.name)
            continue
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(app_dir, target)
        copied.append(app_dir.name)

    print(f"示例应用目录：{dest}")
    for name in copied:
        print(f"  + {name}")
    for name in skipped:
        print(f"  = {name}（已存在，跳过；加 --force 覆盖）")
    if not copied and not skipped:
        print("  （包内没有示例应用）")
    return 0


# ----------------------------------------------------------------------
# examples
# ----------------------------------------------------------------------
def _cmd_examples(args: argparse.Namespace) -> int:
    if not args.copy:
        source = _example_source()
        if source is None:
            print("✗ 找不到内置示例工程。")
            return 1
        print(f"内置示例位置：{source}")
        print("用 sllkgui examples --copy DIR 导出到自己的工程目录。")
        return 0

    source = _example_source()
    if source is None:
        print("✗ 找不到内置示例工程。")
        return 1

    dest = Path(args.copy).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        print(f"✗ 目标目录非空：{dest}")
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    print(f"已导出最小工程到：{dest}")
    print(f"下一步：cd {dest} && python main.py")
    return 0


# ----------------------------------------------------------------------
# doctor
# ----------------------------------------------------------------------
def _mark(ok: bool) -> str:
    return "✓" if ok else "✗"


def _cmd_doctor(args: argparse.Namespace) -> int:
    from sllkgui import __version__
    from sllkgui.appcore.sysx.config.paths import apps_root, data_root, resource_roots

    print("SllkGUI doctor")
    print("=" * 56)
    print(f"{_mark(True)} 版本          : {__version__}")
    print(f"{_mark(True)} 包目录        : {_package_dir()}")

    roots = resource_roots()
    for index, root in enumerate(roots):
        sllkgui = root / "sllkgui"
        print(f"{_mark(sllkgui.is_dir())} 资源根 #{index}     : {root}")
        if not sllkgui.is_dir():
            print("    提示：该根下缺少 sllkgui/ 目录，主题/语言/设置都会缺失")

    data = data_root()
    data_ok = data.exists()
    print(f"{_mark(data_ok)} 数据根        : {data}{'' if data_ok else '（尚未创建）'}")

    # ``--apps-dir`` 显式指定时以它为准：默认应用目录不存在、但用户指了别的
    # 目录时，仍然要打印「发现/加载」结果，否则排查信息在最需要的时候缺席。
    explicit = _absolute(args.apps_dir)
    apps = Path(explicit) if explicit else apps_root()
    apps_ok = apps.is_dir()
    print(f"{_mark(apps_ok)} 应用目录      : {apps}{'' if explicit else '（默认）'}")
    if not apps_ok:
        print("    提示：sllkgui install-demo 可放入示例应用")

    print("-" * 56)
    if apps_ok:
        try:
            from sllkgui.window import discover_app_dirs, load_app_handles

            dirs = discover_app_dirs(explicit)
            print(f"发现应用      : {len(dirs)} 个")
            for app_dir in dirs:
                print(f"  - {app_dir.name}")
            handles = load_app_handles(explicit)
            print(f"成功加载      : {len(handles)} 个")
            for handle in handles:
                module = handle.module.__name__ if handle.module else "（无 gui/main.py）"
                print(f"  + {handle.name}  ->  {module}")
        except Exception as exc:  # noqa: BLE001 - doctor 只做展示，不能自己崩
            print(f"✗ 应用加载失败  : {exc}")
        print("-" * 56)

    try:
        from sllkgui.appcore import AppLanguages, AppSettings, AppThemes, get_app_context

        get_app_context()
        print(f"{_mark(True)} 当前主题      : {AppSettings.theme_name}（共 {len(AppThemes)} 套）")
        print(f"{_mark(True)} 当前语言      : {AppSettings.language}（共 {len(AppLanguages)} 种）")
    except Exception as exc:  # noqa: BLE001
        print(f"✗ 配置加载失败  : {exc}")
        return 1

    print("=" * 56)
    print("排查建议：窗口是空的 → 看「应用目录」是否存在且「发现应用」非 0。")
    return 0


# ----------------------------------------------------------------------
# run
# ----------------------------------------------------------------------
def _cmd_run(args: argparse.Namespace) -> int:
    import sllkgui

    apps_dir = _absolute(args.apps_dir)
    data_dir = _absolute(args.data_dir)
    if apps_dir:
        sllkgui.configure(apps_dir=apps_dir, force_reload=True)
    if data_dir:
        sllkgui.configure(data_dir=data_dir, force_reload=True)

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow

    from sllkgui.appcore import (
        AppLanguages,
        AppSettings,
        AppThemes,
        ColorPalette,
        Language,
        PathFactory,
        get_app_context,
    )
    from sllkgui.window import MainWindowController, SetupMainWindow, UiMainWindow, load_apps

    get_app_context()
    ColorPalette.update(AppThemes[AppSettings.theme_name].data)
    Language.update(AppLanguages[AppSettings.language].data)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = PathFactory.set_ico(AppSettings.logo)
    if icon_path and Path(icon_path).is_file():
        app.setWindowIcon(QIcon(icon_path))

    try:
        load_apps(apps_dir)
    except Exception as exc:  # noqa: BLE001 - 加载失败也要把空态窗口显示出来
        print(f"应用加载失败：{exc}", file=sys.stderr)

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setObjectName("CustomUI")
            self.setMouseTracking(True)
            self.resize(AppSettings.startup_size[0], AppSettings.startup_size[1])
            self.setMinimumSize(AppSettings.minimum_size[0], AppSettings.minimum_size[1])
            self.ui = UiMainWindow()
            self.ui.setup_ui(self)
            SetupMainWindow.setup_gui(self)
            self.controller = MainWindowController(self)
            self.show()

        def btn_clicked(self):  # noqa: ANN201 - Qt 信号槽约定
            btn = SetupMainWindow.setup_btns(self)
            if btn is not None:
                self.controller.handle_button(btn)

        def btn_released(self):  # noqa: ANN201
            SetupMainWindow.setup_btns(self)

        def resizeEvent(self, event):  # noqa: N802 - Qt 命名
            SetupMainWindow.resize_grips(self)

        def mousePressEvent(self, event):  # noqa: N802
            self.dragPos = event.globalPosition().toPoint()
            self.focusNextChild()

    window = MainWindow()  # noqa: F841 - Qt 需要持有引用
    return int(app.exec())


# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sllkgui",
        description="SllkGUI —— 基于 PySide6 的桌面 UI 基座。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="启动主窗口（自动发现应用）")
    run.add_argument("--apps-dir", help="应用目录（默认自动探测）")
    run.add_argument("--data-dir", help="可写数据目录（日志/遥测）")
    run.set_defaults(func=_cmd_run)

    install = sub.add_parser("install-demo", help="安装内置示例应用到数据目录")
    install.add_argument("--dest", help="目标目录（默认 <data_root>/apps）")
    install.add_argument("--force", action="store_true", help="覆盖已存在的同名应用")
    install.set_defaults(func=_cmd_install_demo)

    examples = sub.add_parser("examples", help="查看或导出最小可运行工程")
    examples.add_argument("--copy", metavar="DIR", help="把示例工程复制到 DIR")
    examples.set_defaults(func=_cmd_examples)

    doctor = sub.add_parser("doctor", help="打印路径与配置诊断信息")
    doctor.add_argument("--apps-dir", help="检查指定应用目录")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def _version() -> str:
    from sllkgui import __version__

    return __version__


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
