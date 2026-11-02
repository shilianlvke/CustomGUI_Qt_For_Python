"""四向抽屉的标题条几何。

左 / 顶 / 底三列（``CLeftColumn`` / ``CTopColumn`` / ``CBottomColumn``）的标题条
都是"贴着区域背景卡片顶部的一整条"：与卡片同宽、同顶，因此

* 标题条**上**的两个圆角必须等于卡片圆角（``radius.window``），否则方角会顶出
  卡片的圆角轮廓；
* 标题条**下**沿是卡片内部的接缝（标题条下接内容区），必须是直角，圆角会在
  接缝处啃掉两块底色。

按项目约定，圆角这类与主题无关的几何量不进 ``styles.py``，由组件本地用一条只含
几何属性的样式表提供；三列共用这一条生成函数，避免三份手写圆角慢慢跑偏。
"""

from __future__ import annotations


def title_strip_style(object_name: str, radius: int) -> str:
    """生成标题条的几何样式（只含四个圆角，颜色仍由全局样式表提供）。"""
    return (
        f"#{object_name} {{"
        f" border-top-left-radius: {radius}px;"
        f" border-top-right-radius: {radius}px;"
        f" border-bottom-left-radius: 0px;"
        f" border-bottom-right-radius: 0px; }}"
    )


__all__ = ["title_strip_style"]
