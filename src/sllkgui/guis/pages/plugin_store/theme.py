"""页面级排版工具：目前只剩通知条的标题栏避让。

自绘件与取色逻辑已全部上移到 ``guicore``（CElidedLabel / CIconTile /
CMetricCard / CSurfacePanel / CText），这里不再保留颜色与字体实现。
"""

from __future__ import annotations


def _toast_offset(window) -> int:
    """通知条避让标题栏：顶部偏移 = 标题栏高度 + 8。"""
    bar = getattr(getattr(window, "ui", None), "title_bar", None)
    return bar.height() + 8 if bar is not None else 56


# ----------------------------------------------------------------------
# 绘制工具
# ----------------------------------------------------------------------
