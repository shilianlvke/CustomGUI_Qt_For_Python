"""类型化配置模型与通用强制转换引擎（纯标准库）。

设计思路（对齐现代配置框架，如 pydantic-settings / dataclass-json，但不依赖第三方库）：

1. 每种配置对应一个 :class:`dataclasses.dataclass`，字段即 schema，
   IDE 可获得补全与静态类型检查；
2. :func:`from_mapping` 是通用引擎：按字段类型注解递归转换、
   校验 YAML 解析出的原始字典，错误信息带字段路径；
3. 跨字段约束放在 ``__post_init__`` 中校验。

YAML 文件只是「存储格式」，解析后的字典经过本模块转换为
强类型模型；校验失败统一抛 :class:`ValueError`，由注册表层
包装为 :class:`DomainErrorBoundary`。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, dataclass, fields, is_dataclass
from dataclasses import field as dataclass_field
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from ..config.mapping import Attrs, to_attrs

_NONE_TYPE = type(None)

# 字段级约束标记：``Annotated[int, _NON_NEGATIVE]`` 表示该整数必须非负。
# 普通 ``int`` 不再隐含符号约束——历史上引擎对所有整数强制非负，属隐藏约束，
# 会让将来新增的有符号字段（如 offset）莫名报错。
_NON_NEGATIVE = "non_negative"

#: 非负整数字段类型别名（尺寸 / 边距 / 字号等配置项使用）。
NonNegativeInt = Annotated[int, _NON_NEGATIVE]


# ---------------------------------------------------------------------------
# 通用强制转换引擎
# ---------------------------------------------------------------------------


def _missing_fields(cls, data: Mapping) -> list[str]:
    missing: list[str] = []
    for field in fields(cls):
        required = field.default is MISSING and field.default_factory is MISSING
        if required and field.name not in data:
            missing.append(field.name)
    return missing


def _coerce_int(value: Any, label: str, *, non_negative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} 必须为整数")
    if non_negative and value < 0:
        raise ValueError(f"{label} 必须是非负整数")
    return value


def _coerce_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 必须是非空字符串")
    return value


def _coerce_size_list(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} 必须是长度为 2 的数组")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        raise ValueError(f"{label} 必须仅包含整数")
    if value[0] <= 0 or value[1] <= 0:
        raise ValueError(f"{label} 宽高必须大于 0")
    return value[0], value[1]


def _coerce_str_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} 必须是数组")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] 必须是非空字符串")
        result.append(item)
    return result


def coerce_value(annotation: Any, value: Any, label: str) -> Any:
    """按类型注解将原始值转换为目标类型，失败抛 :class:`ValueError`。"""
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Annotated[X, ...]：解包约束元数据后按基础类型递归
    if origin is Annotated:
        base, *metadata = args
        if base is int:
            return _coerce_int(value, label, non_negative=_NON_NEGATIVE in metadata)
        return coerce_value(base, value, label)

    # Optional[X] / X | None：空值直接放行，其余按非空分支递归
    if origin is Union or origin is UnionType:
        if value is None and _NONE_TYPE in args:
            return None
        real_ann = next((arg for arg in args if arg is not _NONE_TYPE), None)
        if real_ann is None:
            return None
        return coerce_value(real_ann, value, label)

    if annotation is Any:
        return to_attrs(value)

    if annotation is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{label} 必须是布尔值")
        return value

    if annotation is int:
        return _coerce_int(value, label)

    if annotation is str:
        return _coerce_str(value, label)

    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} 必须为数值")
        return float(value)

    # list[str]
    if origin is list and args == (str,):
        return _coerce_str_list(value, label)

    # tuple[int, int]（尺寸数组）
    if origin is tuple and args == (int, int):
        return _coerce_size_list(value, label)

    # 嵌套 dataclass
    if is_dataclass(annotation):
        return from_mapping(annotation, value, label=label)

    # 未参数化的容器原样透传
    if origin in (dict, list, tuple, set):
        return to_attrs(value)

    raise ValueError(f"{label} 不支持的类型注解 {annotation!r}")


def _warn_unknown_fields(cls, data: Mapping, label: str) -> None:
    """对配置中未在模型声明的键发出告警。

    防止 YAML 中的拼写错误（如 ``custom_bg_active_1``）被静默忽略，
    导致颜色 / 参数悄悄丢失。Logger 延迟导入，本模块不产生导入期依赖。
    """
    known = {field.name for field in fields(cls)}
    unknown = [str(key) for key in data if key not in known]
    if not unknown:
        return
    from ..modules.logger_module import Logger

    Logger.warning(f"{label} 存在未声明的字段（已忽略）: {', '.join(unknown)}")


def from_mapping(cls, data: Any, *, label: str) -> Any:
    """将原始映射转换为 ``cls`` 实例（含完整校验）。

    Args:
        cls: 目标 dataclass 类型。
        data: YAML 解析出的原始数据（dict / Attrs 等映射）。
        label: 错误信息中的字段前缀（如 ``"AppSettings"`` 或 ``"AppSettings.lef_menu_size"``）。
    """
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} 必须是字典结构")

    _warn_unknown_fields(cls, data, label)

    missing = _missing_fields(cls, data)
    if missing:
        raise ValueError(f"{label} 缺少关键字段: {', '.join(missing)}")

    # from __future__ import annotations 下 field.type 是字符串，需统一解析；
    # include_extras=True 保留 Annotated 约束元数据（默认会被剥离）
    type_hints = get_type_hints(cls, include_extras=True)

    kwargs: dict[str, Any] = {}
    for field in fields(cls):
        if field.name not in data:
            continue
        kwargs[field.name] = coerce_value(type_hints[field.name], data[field.name], f"{label}.{field.name}")

    # __post_init__ 中的跨字段校验错误（ValueError）原样向上传播
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# 应用配置模型（settings 目录内全部 yaml 合并后的扁平结构）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SizeRange:
    """尺寸区间（minimum/maximum）。"""

    minimum: NonNegativeInt
    maximum: NonNegativeInt

    def __post_init__(self):
        if self.minimum > self.maximum:
            raise ValueError(f"minimum 不能大于 maximum (minimum={self.minimum}, maximum={self.maximum})")


@dataclass(frozen=True)
class PageTransitionSettings:
    """栏目切换动画时间线（毫秒，按 擦除旧页 -> 旧按钮 -> 新按钮 -> 展开新页 串联）。

    任一段为 0 表示跳过该阶段；四段全为 0 时切换退化为瞬切。
    """

    page_out: NonNegativeInt = 120
    menu_out: NonNegativeInt = 90
    menu_in: NonNegativeInt = 110
    page_in: NonNegativeInt = 150
    #: 各阶段缓动曲线（``QEasingCurve.Type`` 枚举名，如 OutCubic / InOutQuad）
    easing: str = "InOutQuad"


@dataclass(frozen=True)
class FeedbackSettings:
    """消息通知与骨架屏参数（毫秒 / 像素）。"""

    #: Toast 停留时长
    toast_life: NonNegativeInt = 3000
    #: 同屏最多条数，超出时挤掉最旧的一条
    toast_max: NonNegativeInt = 4
    #: Toast 进出动画时长
    toast_duration: NonNegativeInt = 180
    #: Toast 距窗口边缘的距离
    toast_margin: NonNegativeInt = 20
    #: Toast 之间的间距
    toast_spacing: NonNegativeInt = 8
    #: 骨架屏微光扫过一圈的时长
    skeleton_duration: NonNegativeInt = 1400
    #: 单条 Toast 的宽度
    toast_width: NonNegativeInt = 340
    #: Toast 外阴影占用的边距
    toast_shadow: NonNegativeInt = 5
    #: 消息条图标尺寸
    message_icon_size: NonNegativeInt = 20


@dataclass(frozen=True)
class OverlaySettings:
    """对话框/抽屉的动画与遮罩参数。"""

    #: 对话框淡入淡出时长
    dialog_duration: NonNegativeInt = 160
    #: 抽屉滑入滑出时长
    drawer_duration: NonNegativeInt = 200
    #: 遮罩背后内容的压暗程度（0-255）
    mask_alpha: NonNegativeInt = 120


@dataclass(frozen=True)
class PanelSettings:
    """面板 / 标签页 / 分割器的动画与几何参数。"""

    #: 标签指示条滑动时长
    tab_duration: NonNegativeInt = 180
    #: 手风琴与面板的展开收起时长
    collapse_duration: NonNegativeInt = 180
    #: 分割条宽度
    splitter_handle: NonNegativeInt = 8
    #: 分割条握把长度
    splitter_grip: NonNegativeInt = 28
    #: 面板圆角半径
    radius: NonNegativeInt = 8
    #: 手风琴标题栏高度
    accordion_header_height: NonNegativeInt = 44
    #: Fieldset 顶部留白
    fieldset_border_top: NonNegativeInt = 10
    #: Fieldset 图例高度
    fieldset_legend_height: NonNegativeInt = 20
    #: Fieldset 图例与内容的间距
    fieldset_legend_gap: NonNegativeInt = 6
    #: 标签页关闭按钮宽度
    tabs_close_width: NonNegativeInt = 20
    #: 标签页图标与文字间距
    tabs_icon_gap: NonNegativeInt = 7


@dataclass(frozen=True)
class ButtonSettings:
    """按钮交互与几何参数（毫秒 / 像素 / 0-1）。"""

    #: 悬停 / 按下时的颜色过渡时长（Fluent 控件状态切换约 0.12s）
    hover_duration: NonNegativeInt = 120
    #: 圆角半径（Fluent 标准控件 4px）
    radius: NonNegativeInt = 4
    #: 图标与文字间距
    icon_gap: NonNegativeInt = 8
    #: 加载指示器旋转一圈的时长
    spin_period: NonNegativeInt = 1600
    #: 加载指示器的刷新间隔
    spin_interval: NonNegativeInt = 16
    #: 禁用态整体透明度（0-1，Fluent 禁用内容 38%）
    disabled_opacity: float = 0.38

    def __post_init__(self):
        if not 0.0 <= self.disabled_opacity <= 1.0:
            raise ValueError(f"button.disabled_opacity 必须在 0-1 之间 (当前 {self.disabled_opacity})")


@dataclass(frozen=True)
class GlassSettings:
    """亚克力玻璃层的不透明度（0-1）。

    数值越大越接近实色；0 表示该层完全透明（只透出下层）。
    """

    window: float = 0.24
    sidebar: float = 0.0
    panel: float = 0.0
    region: float = 0.34
    card: float = 0.34
    control: float = 0.22
    menu: float = 0.92
    overlay_panel: float = 0.96
    tooltip: float = 0.92

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"glass.{field.name} 必须在 0-1 之间 (当前 {value})")


@dataclass(frozen=True)
class GripSettings:
    """窗口缩放夹点几何（像素）。"""

    #: 四角夹点尺寸
    corner_size: NonNegativeInt = 15
    #: 四角夹点内边距
    corner_offset: NonNegativeInt = 5
    #: 右侧/下侧夹点相对窗口边缘的缩进
    corner_inset: NonNegativeInt = 20
    #: 四边夹点厚度
    edge_size: NonNegativeInt = 10


@dataclass(frozen=True)
class ShadowSettings:
    """窗口外阴影参数（像素 / 0-255）。"""

    blur_radius: NonNegativeInt = 20
    alpha: NonNegativeInt = 160
    offset_x: int = 0
    offset_y: int = 0


@dataclass(frozen=True)
class MenuOverlaySettings:
    """左菜单 Overlay 模式的遮罩参数（0-255 / 毫秒）。"""

    scrim_alpha_dark: NonNegativeInt = 80
    scrim_alpha_light: NonNegativeInt = 52
    duration: NonNegativeInt = 160


@dataclass(frozen=True)
class ScrollTopSettings:
    """滚动回顶按钮的几何与动画参数（像素 / 毫秒）。"""

    size: NonNegativeInt = 36
    margin: NonNegativeInt = 16
    threshold: NonNegativeInt = 32
    fade_duration: NonNegativeInt = 160
    scroll_duration: NonNegativeInt = 320


@dataclass(frozen=True)
class SplitButtonSettings:
    """分裂按钮下拉菜单的几何参数（像素）。"""

    menu_gap: NonNegativeInt = 2
    item_padding_x: NonNegativeInt = 12
    item_padding_y: NonNegativeInt = 8
    item_radius: NonNegativeInt = 4
    icon_gap: NonNegativeInt = 8
    icon_size: NonNegativeInt = 16
    min_width: NonNegativeInt = 200


@dataclass(frozen=True)
class InputSettings:
    """输入类组件的几何与交互参数（像素 / 数值）。"""

    radius: NonNegativeInt = 4
    icon_gap: NonNegativeInt = 6
    row_height: NonNegativeInt = 32
    popover_max_rows: NonNegativeInt = 8
    popover_inset: NonNegativeInt = 6
    affix_width: NonNegativeInt = 32
    float_label_band: NonNegativeInt = 14
    float_font_size: NonNegativeInt = 10
    select_chip_gap: NonNegativeInt = 4
    checkbox_box_size: NonNegativeInt = 20
    checkbox_label_gap: NonNegativeInt = 8
    slider_track_height: NonNegativeInt = 4
    slider_handle_radius: NonNegativeInt = 10
    slider_margin: NonNegativeInt = 12
    knob_ring_width: NonNegativeInt = 9
    knob_start_angle: float = 225.0
    knob_sweep: float = 270.0
    knob_pixels_per_step: NonNegativeInt = 3
    rating_star_size: NonNegativeInt = 24
    rating_star_gap: NonNegativeInt = 6
    date_cell: NonNegativeInt = 36
    date_header_height: NonNegativeInt = 34
    date_weekday_height: NonNegativeInt = 24
    color_picker_swatch: NonNegativeInt = 40
    color_picker_cell: NonNegativeInt = 24


@dataclass(frozen=True)
class MenuSettings:
    """菜单类组件的几何与动画参数（像素 / 毫秒）。"""

    list_row_height: NonNegativeInt = 36
    list_padding: NonNegativeInt = 4
    separator_height: NonNegativeInt = 9
    row_radius: NonNegativeInt = 4
    row_inset: NonNegativeInt = 4
    icon_size: NonNegativeInt = 16
    icon_gap: NonNegativeInt = 8
    indent: NonNegativeInt = 16
    text_padding: NonNegativeInt = 12
    arrow_space: NonNegativeInt = 24
    bar_height: NonNegativeInt = 40
    bar_padding: NonNegativeInt = 12
    bar_separator: NonNegativeInt = 9
    tab_height: NonNegativeInt = 40
    tab_padding: NonNegativeInt = 16
    tab_indicator_height: NonNegativeInt = 2
    mega_padding: NonNegativeInt = 6
    mega_spacing: NonNegativeInt = 4
    mega_column_width: NonNegativeInt = 180
    stepper_circle_size: NonNegativeInt = 28
    stepper_bar_height: NonNegativeInt = 52
    stepper_bar_width: NonNegativeInt = 210
    stepper_row_height: NonNegativeInt = 56
    app_row_height: NonNegativeInt = 40
    app_indent: NonNegativeInt = 16
    app_icon_size: NonNegativeInt = 16
    app_icon_gap: NonNegativeInt = 8
    app_text_padding: NonNegativeInt = 12
    app_row_radius: NonNegativeInt = 4


@dataclass(frozen=True)
class DataSettings:
    """数据视图 / 树 / 时间线的几何参数（像素）。"""

    item_height: NonNegativeInt = 36
    item_padding: NonNegativeInt = 12
    tree_indent: NonNegativeInt = 18
    tree_arrow_size: NonNegativeInt = 16
    tree_checkbox_size: NonNegativeInt = 16
    tree_icon_size: NonNegativeInt = 16
    tree_row_height: NonNegativeInt = 36
    timeline_dot_radius: NonNegativeInt = 6
    timeline_halo_radius: NonNegativeInt = 10
    timeline_axis_margin: NonNegativeInt = 24
    timeline_card_gap: NonNegativeInt = 22
    timeline_edge: NonNegativeInt = 12
    timeline_spacing: NonNegativeInt = 14
    timeline_horizontal_card_width: NonNegativeInt = 200
    timeline_axis_top: NonNegativeInt = 16
    timeline_dot_offset: NonNegativeInt = 18
    timeline_dot_gap: NonNegativeInt = 18


@dataclass(frozen=True)
class MediaSettings:
    """媒体组件的圆角、遮罩与缩略图几何（像素 / 0-255）。"""

    radius: NonNegativeInt = 8
    image_mask_alpha: NonNegativeInt = 210
    image_caption_height: NonNegativeInt = 28
    carousel_footer_height: NonNegativeInt = 30
    carousel_spacing: NonNegativeInt = 8
    carousel_dot_step: NonNegativeInt = 14
    galleria_thumb_width: NonNegativeInt = 74
    galleria_thumb_height: NonNegativeInt = 52
    galleria_thumb_row_height: NonNegativeInt = 58
    galleria_footer_height: NonNegativeInt = 30


@dataclass(frozen=True)
class DisplaySettings:
    """展示类组件的几何与刷新间隔（像素 / 毫秒）。"""

    progress_interval: NonNegativeInt = 33
    skeleton_interval: NonNegativeInt = 33
    tag_height: NonNegativeInt = 24
    tag_padding_x: NonNegativeInt = 8
    tag_icon_size: NonNegativeInt = 13
    tag_icon_gap: NonNegativeInt = 5
    chip_height: NonNegativeInt = 28
    chip_padding_x: NonNegativeInt = 10
    chip_icon_size: NonNegativeInt = 14
    chip_icon_gap: NonNegativeInt = 6


@dataclass(frozen=True)
class UploadSettings:
    """文件上传组件的几何与模拟进度参数。"""

    radius: NonNegativeInt = 8
    list_max_height: NonNegativeInt = 200
    upload_interval: NonNegativeInt = 60
    upload_step: NonNegativeInt = 5


@dataclass(frozen=True)
class ChartSettings:
    """图表组件的圆角（像素）。"""

    radius: NonNegativeInt = 8


@dataclass(frozen=True)
class SearchSettings:
    """全局搜索面板的行为参数。"""

    max_results: NonNegativeInt = 8


@dataclass(frozen=True)
class LoggerFileSettings:
    """日志文件轮转参数（console.yaml 引导期读取）。"""

    name: str = "sllkgui.log"
    max_bytes: NonNegativeInt = 1_048_576
    backup_count: NonNegativeInt = 5


@dataclass(frozen=True)
class AcrylicSettings:
    """亚克力材质参数（Windows 11 Fluent Design）。

    ``enabled`` 只表达使用意愿：平台不支持时样式表会自动回落到不透明
    主题底色（见 ``sllkgui.guicore.acrylic.acrylic_active``）。
    """

    #: 是否启用系统级亚克力背景
    enabled: bool = True
    #: 亚克力色调不透明度（0-100）；越大越接近实色，越小越透明
    opacity: NonNegativeInt = 60
    #: 窗口首次显示的淡入时长（毫秒，0 表示关闭）
    fade_in: NonNegativeInt = 160

    def __post_init__(self):
        if self.opacity > 100:
            raise ValueError(f"acrylic.opacity 必须在 0-100 之间 (当前 {self.opacity})")


@dataclass(frozen=True)
class AppSettingsModel:
    """系统设置模型：``settings`` 目录下所有 YAML 合并后的强类型视图。

    字段覆盖 window.yaml / config.yaml / console.yaml 三份文件的全部键；
    ``resource`` 下的文件是唯一数据源，本类是唯一 Schema。
    """

    # ---- window.yaml ----
    startup_size: tuple[int, int]
    minimum_size: tuple[int, int]
    icon_size: NonNegativeInt
    custom_title_bar: bool
    hide_grips: bool
    window_margin: NonNegativeInt
    window_space: NonNegativeInt
    window_border_size: NonNegativeInt
    window_border_radius: NonNegativeInt
    window_shadow: bool
    lef_menu_size: SizeRange
    left_menu_content_margins: NonNegativeInt
    left_column_size: SizeRange
    right_column_size: SizeRange
    top_column_size: SizeRange
    bottom_column_size: SizeRange
    right_menu_content_margins: NonNegativeInt
    right_title_bar_height: NonNegativeInt
    right_content_space: NonNegativeInt
    right_credits_height: NonNegativeInt
    custom_padding: NonNegativeInt
    custom_border: NonNegativeInt
    tooltip_border_radius: NonNegativeInt
    tooltip_font: NonNegativeInt
    time_animation: NonNegativeInt
    family: str
    title_size: NonNegativeInt
    subtitle_size: NonNegativeInt
    text_size: NonNegativeInt
    # ---- config.yaml ----
    language: str
    theme_name: str
    logo: str
    logo_home: str
    logo_title: str
    logo_loading: str
    # ---- console.yaml ----
    display: list[str]
    logger_level: str
    logger_color: bool
    # ---- console.yaml（日志文件轮转，引导期读取） ----
    logger_file: LoggerFileSettings = dataclass_field(default_factory=LoggerFileSettings)
    # ---- window.yaml（栏目切换动画） ----
    page_transition: PageTransitionSettings = dataclass_field(default_factory=PageTransitionSettings)
    feedback: FeedbackSettings = dataclass_field(default_factory=FeedbackSettings)
    overlay: OverlaySettings = dataclass_field(default_factory=OverlaySettings)
    panels: PanelSettings = dataclass_field(default_factory=PanelSettings)
    button: ButtonSettings = dataclass_field(default_factory=ButtonSettings)
    # ---- window.yaml（亚克力材质 / 玻璃层 / 窗口几何） ----
    acrylic: AcrylicSettings = dataclass_field(default_factory=AcrylicSettings)
    glass: GlassSettings = dataclass_field(default_factory=GlassSettings)
    grips: GripSettings = dataclass_field(default_factory=GripSettings)
    shadow: ShadowSettings = dataclass_field(default_factory=ShadowSettings)
    menu_overlay: MenuOverlaySettings = dataclass_field(default_factory=MenuOverlaySettings)
    scroll_top: ScrollTopSettings = dataclass_field(default_factory=ScrollTopSettings)
    #: 非亚克力模式下窗口外圈留给阴影的边距
    title_bar_margin: NonNegativeInt = 10
    #: 非亚克力模式下主界面外圈留白
    content_margin: NonNegativeInt = 10
    # ---- components.yaml ----
    split_button: SplitButtonSettings = dataclass_field(default_factory=SplitButtonSettings)
    input: InputSettings = dataclass_field(default_factory=InputSettings)
    menus: MenuSettings = dataclass_field(default_factory=MenuSettings)
    data: DataSettings = dataclass_field(default_factory=DataSettings)
    media: MediaSettings = dataclass_field(default_factory=MediaSettings)
    display_components: DisplaySettings = dataclass_field(default_factory=DisplaySettings)
    upload: UploadSettings = dataclass_field(default_factory=UploadSettings)
    chart: ChartSettings = dataclass_field(default_factory=ChartSettings)
    search: SearchSettings = dataclass_field(default_factory=SearchSettings)

    @classmethod
    def from_mapping(cls, data: Mapping, label: str = "AppSettings") -> AppSettingsModel:
        return from_mapping(cls, data, label=label)

    def __post_init__(self):
        if self.startup_size[0] < self.minimum_size[0] or self.startup_size[1] < self.minimum_size[1]:
            raise ValueError("startup_size 不能小于 minimum_size")


# ---------------------------------------------------------------------------
# 主题模型（每个主题文件一份）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThemeModel:
    """主题配色模型：必填颜色 + 可选颜色（历史兼容）。"""

    custom_dark_one: str
    custom_dark_two: str
    custom_dark_three: str
    custom_dark_four: str
    custom_bg_one: str
    custom_bg_two: str
    custom_bg_three: str
    custom_icon_color: str
    custom_icon_hover: str
    custom_icon_pressed: str
    custom_icon_active: str
    custom_context_color: str
    custom_context_hover: str
    custom_context_pressed: str
    custom_text_title: str
    custom_text_foreground: str
    custom_text_description: str
    custom_text_active: str
    custom_white: str
    custom_pink: str
    custom_green: str
    custom_red: str
    custom_yellow: str
    custom_bg_active_one: str | None = None
    custom_bg_active_two: str | None = None
    custom_bg_active_three: str | None = None
    custom_transparent: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping, label: str = "theme") -> ThemeModel:
        return from_mapping(cls, data, label=label)


# ---------------------------------------------------------------------------
# 兼容入口：校验函数（保持历史函数名与错误信息）
# ---------------------------------------------------------------------------


def validate_settings_data(settings_data: Any) -> AppSettingsModel:
    """校验合并后的系统设置，成功时返回强类型模型。"""
    return AppSettingsModel.from_mapping(settings_data, label="AppSettings")


def validate_theme_data(theme_data: Any, theme_name: str = "unknown") -> ThemeModel:
    """校验主题配色：所有出现的键都必须是非空字符串。"""
    label = f"主题 {theme_name}"
    if not isinstance(theme_data, Mapping):
        raise ValueError(f"{label} 必须是字典结构")

    for key, value in theme_data.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} 字段 {key} 必须是非空字符串")

    return ThemeModel.from_mapping(theme_data, label=label)


def _require_keys(data: Any, required: list[str], label: str) -> Attrs:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} 必须是字典")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"{label} 缺少关键字段: {', '.join(missing)}")
    return to_attrs(data)


def validate_language_data(language_data: Any, language_name: str = "unknown") -> Attrs:
    """校验语言包结构：custom_ui / PAGE / UI 三个分组及其关键键。

    与 :func:`validate_settings_data` / :func:`validate_theme_data` 保持一致，
    返回校验通过的 :class:`Attrs`（调用方可直接使用）。
    """
    label = f"语言 {language_name}"
    if not isinstance(language_data, Mapping):
        raise ValueError(f"{label} 必须是字典结构")

    _require_keys(language_data, ["custom_ui", "PAGE", "UI"], label)

    _require_keys(
        language_data["custom_ui"],
        ["sys_name", "sys_version", "sys_copyright", "sys_github"],
        f"{label}.custom_ui",
    )
    # PAGE 段仅要求存在（页面文本由 Apps/<app>/resource/lang 提供）
    if not isinstance(language_data["PAGE"], Mapping):
        raise ValueError(f"{label}.PAGE 必须是字典")
    _require_keys(language_data["UI"], ["ui_Settings", "ui_Show", "ui_Hide"], f"{label}.UI")
    return to_attrs(language_data)


__all__ = [
    "Attrs",
    "SizeRange",
    "AcrylicSettings",
    "AppSettingsModel",
    "ThemeModel",
    "NonNegativeInt",
    "coerce_value",
    "from_mapping",
    "validate_settings_data",
    "validate_theme_data",
    "validate_language_data",
]
