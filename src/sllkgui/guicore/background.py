"""背景图运行期状态：供样式层判断是否把各层表面转为半透明。

``CWindow`` 设置/清除背景图时写入这里；``Styles`` 在生成 QSS 时读取。
与亚克力状态分开，才能在没有系统模糊的平台上也让背景图透出。
"""

from __future__ import annotations

_ACTIVE = False


def background_image_active() -> bool:
    """当前窗口是否启用了背景图。"""
    return _ACTIVE


def set_background_image_active(active: bool) -> None:
    """由 ``CWindow.set_background_image()`` 调用；不直接对外暴露。"""
    global _ACTIVE
    _ACTIVE = bool(active)


__all__ = ["background_image_active", "set_background_image_active"]
