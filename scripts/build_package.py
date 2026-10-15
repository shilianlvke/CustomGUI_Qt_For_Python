import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 仅扫描源码；排除打包产物 / 虚拟环境 / 缓存
SRC_DIRS = ["AppCore", "Apps", "GuiCore", "Guis", "scripts", "tests"]
SRC_FILES = ["main.py"]

# 即使被某些间接依赖引用，纯 QWidget 应用也“可以安全移除”的 Qt 模块家族。
# 注意：本脚本只自动排除那些【源码中完全没用到】的家族；一旦源码用到，就自动保留。
REMOVABLE_FAMILIES = {
    "QtQuick", "QtQuickWidgets", "QtQuickControls2",
    "QtQml", "QtQmlModels", "QtQmlWorkerScript",
    "QtPdf", "QtPdfWidgets",
    "QtNetwork",
    "QtVirtualKeyboard",
}

# 用到的 Qt 子模块 -> 必须随包保留的 Qt6 原生 DLL（含运行时依赖闭包）。
# 例如 QtSvgWidgets 运行时依赖 Qt6Svg.dll，故一并保留；.pyd 由子串过滤处理。
SUBMODULE_TO_DLL = {
    "QtCore": ["Qt6Core.dll"],
    "QtGui": ["Qt6Gui.dll"],
    "QtWidgets": ["Qt6Widgets.dll"],
    "QtSvg": ["Qt6Svg.dll"],
    "QtSvgWidgets": ["Qt6SvgWidgets.dll", "Qt6Svg.dll"],
    "QtOpenGL": ["Qt6OpenGL.dll"],
    "QtOpenGLWidgets": ["Qt6OpenGL.dll", "Qt6Widgets.dll"],
    "QtPrintSupport": ["Qt6PrintSupport.dll"],
    "QtMultimedia": ["Qt6Multimedia.dll"],
    "QtMultimediaWidgets": ["Qt6Multimedia.dll"],
    "QtCharts": ["Qt6Charts.dll"],
    "QtSql": ["Qt6Sql.dll"],
    "QtStateMachine": ["Qt6StateMachine.dll"],
    "QtXml": ["Qt6Xml.dll"],
    "QtNetwork": ["Qt6Network.dll"],
    # QtConcurrent 等归并到核心 DLL
    "QtConcurrent": ["Qt6Core.dll"],
}

# 无论如何都保留的底层 DLL（几乎必然被其他模块传递依赖）
ALWAYS_KEEP = {"Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"}

_IMPORT_RE = re.compile(
    r"^\s*(?:"
    r"from\s+PySide6\.(\w+)\s+import"      # from PySide6.QtXxx import ...
    r"|import\s+PySide6\.(\w+)"            # import PySide6.QtXxx
    r"|from\s+PySide6\s+import\s+(\w+)"    # from PySide6 import QtXxx
    r")",
    re.M,
)


def scan_used_qt_submodules() -> set:
    """扫描源码中实际导入的 PySide6.Qt* 子模块。"""
    used: set = set()
    paths: list = [ROOT / f for f in SRC_FILES]
    for d in SRC_DIRS:
        paths.extend((ROOT / d).rglob("*.py"))
    for p in paths:
        rel = str(p.relative_to(ROOT))
        if "__pycache__" in rel or rel.startswith("."):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _IMPORT_RE.finditer(text):
            mod = m.group(1) or m.group(2) or m.group(3)
            if mod and mod.startswith("Qt"):
                used.add(mod)
    return used


def compute_trim_plan() -> dict:
    """根据源码实际导入，推导：保留的 DLL / 应排除的家族（及对应 Python 模块）。"""
    used = scan_used_qt_submodules()

    keep_dlls = set(ALWAYS_KEEP)
    for mod in used:
        dlls = SUBMODULE_TO_DLL.get(mod)
        if dlls:
            keep_dlls.update(dlls)

    # 仅排除“完全未使用”的家族；用到其一即整体保留（避免漏包）
    exclude_families = {
        fam for fam in REMOVABLE_FAMILIES
        if not any(u == fam or u.startswith(fam) for u in used)
    }
    exclude_modules = sorted(f"PySide6.{f}" for f in exclude_families)

    return {
        "keep_dlls": sorted(keep_dlls),
        "exclude_substr": sorted(exclude_families),
        "exclude_modules": exclude_modules,
        "used": sorted(used),
    }


def _print_plan(plan: dict) -> None:
    print("=" * 60)
    print("[自动裁剪] 根据源码实际 PySide6 导入推导打包裁剪策略")
    print(f"  检测到的 Qt 子模块: {', '.join(plan['used'])}")
    print(f"  保留的 Qt6 DLL   : {', '.join(plan['keep_dlls'])}")
    print(f"  排除的 Qt 家族   : {', '.join(plan['exclude_substr']) or '(无)'}")
    if "QtNetwork" in plan["exclude_substr"]:
        print("  -> 含 QtNetwork 停用，连带移除 OpenSSL 与 tls/networkinformation 插件")
    print("=" * 60)


# 完整 PyInstaller spec 模板。__KEEP_QT6__ / __EXCLUDE_QT_SUBSTR__ / __EXCLUDES__
# 由本脚本按源码导入自动替换；路径类占位符替换为绝对路径，避免 cwd / spec 位置歧义。
# 本模板在每次打包时写入 build/CustomGUI.spec 后由 PyInstaller 执行，无需提交到仓库。
SPEC_TEMPLATE = r'''# -*- mode: python ; coding: utf-8 -*-
# 本文件由 scripts/build_package.py 在打包时自动生成，请勿手工编辑 / 提交。
_KEEP_QT6 = __KEEP_QT6__
_EXCLUDE_QT_SUBSTR = __EXCLUDE_QT_SUBSTR__

a = Analysis(
    ['__MAIN__'],
    pathex=['__PATH__'],
    binaries=[],
    datas=[('__RES__', 'resource'), ('__APPS__', 'Apps')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=__EXCLUDES__,
    noarchive=False,
    optimize=0,
)

# --- 裁剪：剔除运行时不需要的二进制与数据 ---
# 1) OpenSSL（libcrypto / libssl）：应用无网络 / SSL 需求时移除
# 2) 未使用的 Qt 模块原生 DLL 与对应 PySide6 .pyd（纯 QWidget 应用，无 QML/PDF/网络）。
#    PyInstaller 的 PySide6 钩子会无条件拷贝所有 Qt6*.dll，模块级 excludes 拦不住，
#    必须在 a.binaries 里按文件名过滤。保留清单 _KEEP_QT6 由源码导入自动推导。
# 3) Qt 网络相关插件（tls / networkinformation）：随 QtNetwork 一并移除
# 4) Qt 翻译文件：应用自带语言系统（AppCore Language），无需 Qt 内置翻译

_NETWORK_EXCLUDED = 'QtNetwork' in _EXCLUDE_QT_SUBSTR
# opengl32sw.dll = 软件 OpenGL 光栅器；纯 QWidget 应用走 raster 引擎，运行时不会加载，
# 属死重（约 20MB），直接无条件剔除。若日后引入 QOpenGLWidget 需重新评估。
_EXCLUDE_BIN_NAMES = {'opengl32sw.dll'}
if _NETWORK_EXCLUDED:
    # 无网络需求：连带移除 OpenSSL 与网络相关插件
    _EXCLUDE_BIN_NAMES.update({'libcrypto-3-x64.dll', 'libssl-3-x64.dll'})
_EXCLUDE_BIN_SUBPATHS = ('plugins/tls', 'plugins/networkinformation') if _NETWORK_EXCLUDED else ()


def _norm(p):
    return p.replace('\\', '/')


def _keep_binary(t):
    dest = _norm(t[0])
    base = dest.rsplit('/', 1)[-1]
    if base in _EXCLUDE_BIN_NAMES:
        return False
    # 未保留的 Qt6 原生 DLL 一律剔除
    if base.startswith('Qt6') and base not in _KEEP_QT6:
        return False
    # 未使用 Qt 模块的 Python 扩展（.pyd）一并剔除
    if any(sub in base for sub in _EXCLUDE_QT_SUBSTR):
        return False
    if any(sub in dest for sub in _EXCLUDE_BIN_SUBPATHS):
        return False
    return True


a.binaries = [t for t in a.binaries if _keep_binary(t)]
a.datas = [t for t in a.datas if 'translations' not in _norm(t[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CustomGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CustomGUI',
)
'''


def _render_spec(plan: dict) -> str:
    """把自动推导的裁剪清单与绝对路径填入模板，生成完整可用的 spec 源码。"""
    return (
        SPEC_TEMPLATE
        .replace("__KEEP_QT6__", repr(set(plan["keep_dlls"])))
        .replace("__EXCLUDE_QT_SUBSTR__", repr(tuple(plan["exclude_substr"])))
        .replace("__EXCLUDES__", repr(list(plan["exclude_modules"])))
        .replace("__MAIN__", (ROOT / "main.py").as_posix())
        .replace("__PATH__", ROOT.as_posix())
        .replace("__RES__", (ROOT / "resource").as_posix())
        .replace("__APPS__", (ROOT / "Apps").as_posix())
    )


def main() -> int:
    os.chdir(ROOT)

    plan = compute_trim_plan()
    _print_plan(plan)

    # 不再依赖仓库内的 CustomGUI.spec（已被 .gitignore 排除）。
    # 每次打包时在本 build/ 目录内生成 spec 并运行，构建逻辑全部内聚于此脚本。
    build_dir = ROOT / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    spec_path = build_dir / "CustomGUI.spec"
    spec_path.write_text(_render_spec(plan), encoding="utf-8")

    dist_dir = ROOT / "dist"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        str(spec_path),
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
