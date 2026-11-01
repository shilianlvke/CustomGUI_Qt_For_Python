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

from customgui.appcore import Logger

#: Windows 系统字体候选（按优先级；存在即注册）
_WINDOWS_FONT_CANDIDATES = (
    "msyh.ttc",  # 微软雅黑（简体/繁体覆盖最好）
    "msyhbd.ttc",  # 微软雅黑粗体
    "NotoSansSC-VF.ttf",  # 思源黑体（可变字重）
    "segoeui.ttf",  # Segoe UI（拉丁）
    "segoeuib.ttf",  # Segoe UI 粗体
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


def install_system_fonts() -> int:
    """注册常见系统字体（Windows 优先），返回成功数量。

    Qt 的 offscreen 平台（测试与远程会话）常无法自动发现系统字体；此函数
    在那些环境下仍能保持 CJK/Latin 文本可读。
    """
    windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [windir / name for name in _WINDOWS_FONT_CANDIDATES]
    return install_fonts(candidates)


__all__ = ["install_fonts", "install_system_fonts"]
