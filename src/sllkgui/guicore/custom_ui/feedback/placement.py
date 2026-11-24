"""Toast 落位的唯一实现：边距、顶部避让与栈内坐标只在这里算。

历史包袱：同一条提示的位置曾被三处各算一遍——CToast.show_message 的
offset_top、CToast._reflow、ToastBus._reflow。三者的配置来源、标题栏高度取法
与阴影占位处理互不相同，于是同一句提示经不同触发路径落在不同位置：

- 总线直接读 title_bar.height()，窗口尚未完成布局时该值是构造尺寸（实测 480），
  启动期弹出的提示因此整体下移约 440px，落在页面中间且之后不再纠正；
- 组件侧 show_message 从 margin 起算，忽略标题栏，落在标题栏里面；
- 边距只作用到控件外框，而控件外框含一圈透明阴影，卡片实际离窗口边更远。

本模块把三件事收敛成唯一实现：

1. 读配置：feedback.toast_margin / toast_spacing / toast_shadow，异常时回落到
   与 schema 一致的默认值；
2. 量标题栏：按「已布局高度 -> 声明固定高度 -> 父容器固定高度 -> sizeHint」
   逐级降级，保证布局前也不失真；
3. 算坐标：最新在最上面、右对齐、卡片可见边缘距窗口 margin，并保证不越出窗口。

坐标系约定：margin 描述的是**卡片可见边缘**到窗口边缘的距离；CToast 控件本身
含一圈透明阴影，控件落点需要换算。换算只在 stack_points 里做一次，调用方不要
自己再加，否则又会出现「两条路径差几个像素」的老问题。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QWidget

#: 标题栏与第一条通知之间的呼吸间距（像素）
TITLE_BAR_GAP = 8


@dataclass(frozen=True)
class ToastMetrics:
    """落位所需的三个尺寸量（像素）。"""

    #: 卡片可见边缘到窗口边缘的距离
    margin: int
    #: 相邻两条卡片的垂直间距
    spacing: int
    #: 控件内为外阴影预留的透明边距
    shadow: int

    @property
    def inset_x(self) -> int:
        """卡片左（右）边缘相对控件边缘的偏移。"""
        return self.shadow

    @property
    def inset_y(self) -> int:
        """卡片顶边相对控件顶边的偏移，与绘制代码保持同一取整方式。"""
        return self.shadow // 2

    @property
    def inset_bottom(self) -> int:
        """卡片底边到控件底边的距离（阴影只占上边的一半，下边占满）。"""
        return 2 * self.shadow - self.inset_y


#: 配置不可用时的兜底（与 FeedbackSettings 默认值保持一致）
_DEFAULTS = ToastMetrics(margin=20, spacing=8, shadow=5)


def toast_metrics() -> ToastMetrics:
    """读取落位配置；任何异常都折算成默认值，不抛给调用方。"""
    try:
        from sllkgui.appcore import AppSettings

        cfg = AppSettings.feedback
        return ToastMetrics(
            margin=max(0, int(cfg.toast_margin)),
            spacing=max(0, int(cfg.toast_spacing)),
            shadow=max(0, int(cfg.toast_shadow)),
        )
    except Exception:  # noqa: BLE001 - 提示组件不能因配置缺失而不可用
        return _DEFAULTS


def title_bar_widget(anchor: QWidget) -> QWidget | None:
    """锚点窗口的自定义标题栏控件（主窗口 ui.title_bar / 设置窗口 _title_bar）。"""
    for holder in ("ui", "self"):
        try:
            owner = anchor if holder == "self" else getattr(anchor, "ui", None)
        except RuntimeError:
            continue
        if owner is None:
            continue
        for attribute in ("title_bar", "_title_bar"):
            try:
                bar = getattr(owner, attribute, None)
            except RuntimeError:
                bar = None
            if isinstance(bar, QWidget):
                return bar
    return None


def _declared_height(widget: QWidget) -> int:
    """控件声明的固定高度；非固定高度返回 0（此时声明值不具参考意义）。"""
    try:
        minimum = int(widget.minimumHeight())
        maximum = int(widget.maximumHeight())
    except RuntimeError:
        return 0
    return minimum if minimum > 0 and maximum == minimum else 0


def _title_bar_height(bar: QWidget, anchor: QWidget) -> int:
    """标题栏高度：布局前不可信，逐级降级直到拿到稳定值。"""
    try:
        height = int(bar.height())
        anchor_height = int(anchor.height())
        if bar.isVisible() and 0 < height <= max(1, anchor_height):
            return height
    except RuntimeError:
        return 0
    declared = _declared_height(bar)
    if declared > 0:
        return declared
    try:
        parent = bar.parentWidget()
    except RuntimeError:
        parent = None
    if parent is not None:
        declared = _declared_height(parent)
        if declared > 0:
            return declared
    try:
        return max(0, int(bar.sizeHint().height()))
    except RuntimeError:
        return 0


def title_bar_offset(anchor: QWidget | None) -> int:
    """第一条通知需要让开的顶部高度；无自定义标题栏的宿主返回 0。"""
    if anchor is None:
        return 0
    bar = title_bar_widget(anchor)
    if bar is None:
        return 0
    height = _title_bar_height(bar, anchor)
    return height + TITLE_BAR_GAP if height > 0 else 0


def _clamp(value: int, low: int, high: int) -> int:
    if high < low:
        return low
    return max(low, min(high, value))


def stack_points(
    anchor: QWidget,
    sizes: Sequence[QSize],
    offsets: int | Sequence[int] = 0,
    *,
    metrics: ToastMetrics | None = None,
) -> list[QPoint]:
    """按栈顺序（最新在前）计算每条通知的控件落点。

    offsets 可以是单值（全部共用一个顶部避让高度），也可以是与 sizes 等长的
    序列——旧版 show_message 允许每个调用点自己给 offset_top，保留该语义但统一
    走同一套换算。返回的坐标保证：卡片右边缘距窗口右边缘等于 margin；相邻卡片
    间距等于 spacing；且整体不越出锚点窗口。
    """
    resolved = metrics or toast_metrics()
    try:
        anchor_width = max(1, int(anchor.width()))
        # 只为确认锚点仍然有效（销毁后会抛 RuntimeError）
        if int(anchor.height()) <= 0:
            return []
    except RuntimeError:
        return []

    shared = 0 if isinstance(offsets, Sequence) else int(offsets)
    points: list[QPoint] = []
    cursor: int | None = None
    for index, size in enumerate(sizes):
        item_offset = int(offsets[index]) if isinstance(offsets, Sequence) else shared
        # 第一张卡片的可见顶边 = 顶部避让 + 边距；换算到控件顶边要减掉阴影内缩
        start = max(0, item_offset) + resolved.margin - resolved.inset_y
        cursor = start if cursor is None else max(cursor, start)
        width = max(1, int(size.width()))
        height = max(1, int(size.height()))
        y = max(0, cursor)
        # 右对齐：卡片可见右边缘距窗口右边缘恰好 margin
        x = _clamp(anchor_width - resolved.margin - width + resolved.inset_x, 0, anchor_width - width)
        points.append(QPoint(x, y))
        # 下一条的落点 = 本条卡片可见底边 + spacing，换算回控件顶边
        cursor = y + height - resolved.inset_bottom + resolved.spacing - resolved.inset_y
    return points


__all__ = [
    "TITLE_BAR_GAP",
    "ToastMetrics",
    "stack_points",
    "title_bar_offset",
    "title_bar_widget",
    "toast_metrics",
]
