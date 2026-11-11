"""字体注册工具：把系统/自定义字体显式注册到 Qt（反哺自 PyCL2）。

为什么需要
----------
Qt 的 ``offscreen`` 平台（测试、远程会话、某些打包环境）不一定能自动发现
系统字体，导致 CJK 文本渲染成豆腐块。把字体文件显式注册后即可正常显示，
而不必把字体打进应用包。

这些函数依赖 PySide6，因此放在 ``guicore``（表现层基础设施）而不是
``appcore``（零 Qt 依赖）。
"""

from __future__ import annotations

import os
from pathlib import Path

from sllkgui.appcore import Logger

#: Windows 系统字体候选：按「字体族 → 候选文件」分组，每组只注册一个文件。
#:
#: 逐个文件无条件注册会让 Qt 把整套字体展开到内存：微软雅黑 + 粗体 +
#: 思源黑体三份 CJK 字体合计约 50 MB 文件，实测常驻内存会增加约 270 MB。
#: Windows 原生平台本来就能发现这些字体，因此只在字体族缺失时才补一份。
_WINDOWS_FONT_GROUPS = (
    (("Microsoft YaHei", "Noto Sans SC"), ("msyh.ttc", "msyhbd.ttc", "NotoSansSC-VF.ttf")),
    (("Segoe UI",), ("segoeui.ttf", "segoeuib.ttf")),
)


def install_fonts(paths) -> int:
    """把给定字体文件注册到 Qt，返回成功注册的数量。

    *paths* 是路径（``str`` / ``Path``）的可迭代对象；不存在的文件静默跳过。
    """
    try:
        from PySide6.QtGui import QFontDatabase
    except Exception as exc:  # noqa: BLE001 - 无 Qt 环境时直接放弃
        Logger.debug(f"无法导入 QFontDatabase，跳过字体注册: {exc}")
        return 0

    registered = 0
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            result = QFontDatabase.addApplicationFont(str(path))
            if result >= 0:
                registered += 1
        except Exception as exc:  # noqa: BLE001 - 单个字体失败不影响其余
            Logger.debug(f"注册字体失败: {path}（{exc}）")
    if registered:
        Logger.debug(f"已注册 {registered} 个字体")
    return registered


def _available_families() -> set[str]:
    """当前 Qt 已能发现的字体族（小写）；无 Qt 环境时返回空集合。"""
    try:
        from PySide6.QtGui import QFontDatabase
    except Exception as exc:  # noqa: BLE001 - 无 Qt 环境时按“全部缺失”处理
        Logger.debug(f"无法导入 QFontDatabase，按字体缺失处理: {exc}")
        return set()
    try:
        return {str(name).casefold() for name in QFontDatabase.families()}
    except Exception as exc:  # noqa: BLE001 - 查询失败时按“全部缺失”处理
        Logger.debug(f"读取字体族失败，按字体缺失处理: {exc}")
        return set()


def _select_system_fonts(font_dir: Path, available: set[str]) -> list[Path]:
    """按字体族补齐缺失字体：每组最多选一个已存在的文件。

    Windows 正常桌面环境里 CJK 与拉丁字体都已由系统提供，返回空列表；
    只有 offscreen / 精简打包环境缺少字体族时才返回需要补注册的文件。
    """
    normalized = {str(name).casefold() for name in available}
    selected: list[Path] = []
    for families, candidates in _WINDOWS_FONT_GROUPS:
        if any(family.casefold() in normalized for family in families):
            continue
        for name in candidates:
            path = font_dir / name
            if path.is_file():
                selected.append(path)
                break
    return selected


def install_system_fonts() -> int:
    """按需注册系统字体，返回成功数量。

    Qt 的 offscreen 平台（测试与远程会话）常无法自动发现系统字体；此函数
    只在这些字体族确实缺失时才注册一个替代文件，避免 Windows 桌面上重复
    加载整套 CJK 字体（实测可省下约 270 MB 常驻内存）。
    """
    windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    selected = _select_system_fonts(windir, _available_families())
    if not selected:
        Logger.debug("系统字体族齐全，跳过字体文件注册")
        return 0
    return install_fonts(selected)


__all__ = ["install_fonts", "install_system_fonts"]
