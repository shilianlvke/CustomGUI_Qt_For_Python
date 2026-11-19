"""设置声明模型：值类型、控件提示、分组与页面。

这是「统一设置框架」的**唯一契约**：基座与插件都用同一组 dataclass 描述
配置项，UI 层只负责按 ``kind`` / ``control`` 渲染，不关心配置来自哪里。

设计要点：

1. ``key`` 只在命名空间内唯一，完整键由 :attr:`SettingsPage.namespace` 拼出
   （``core.appearance.theme`` / ``plugin.plugin-hello.greeting``），因此插件
   与基座、插件与插件之间不可能重名；
2. ``kind`` 决定数据类型与校验，``control`` 只是渲染建议（例如 ``INT`` 既可
   渲染成滑块也可渲染成数字框），二者分离，避免把控件语义写进存储层；
3. 所有默认值必须是标量（bool / int / float / str），保证「恢复默认」与
   YAML 回写不会共享可变对象。

本模块不导入 Qt，``sllkgui.plugin`` 可直接转出给插件作者使用。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PAGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_NAMESPACE_RE = re.compile(r"^(?:core|plugin\.[a-z0-9][a-z0-9._-]{0,63})$")
_CORE_NAMESPACE = "core"
_PLUGIN_NAMESPACE_PREFIX = "plugin."


class SettingsError(ValueError):
    """设置声明 / 取值错误（消息直接面向开发者与设置界面）。"""


class SettingsConflictError(SettingsError):
    """完整键或页面 ID 在同一命名空间内重复注册。"""


class SettingsValidationError(SettingsError):
    """取值不满足声明的类型或范围。"""

    def __init__(self, key: str, message: str):
        super().__init__(message)
        self.key = key


class SettingKind(StrEnum):
    """配置值的数据类型（决定校验与 YAML 存储形态）。"""

    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    TEXT = "text"
    ENUM = "enum"
    PATH = "path"
    THEME = "theme"


class SettingControl(StrEnum):
    """渲染建议；同一种 ``kind`` 可以有多种表现。"""

    SWITCH = "switch"
    SELECT = "select"
    SEGMENTED = "segmented"
    SLIDER = "slider"
    NUMBER = "number"
    TEXT = "text"
    PATH = "path"
    THEME_GALLERY = "theme_gallery"


_DEFAULT_CONTROL = {
    SettingKind.BOOL: SettingControl.SWITCH,
    SettingKind.INT: SettingControl.NUMBER,
    SettingKind.FLOAT: SettingControl.NUMBER,
    SettingKind.TEXT: SettingControl.TEXT,
    SettingKind.ENUM: SettingControl.SELECT,
    SettingKind.PATH: SettingControl.PATH,
    SettingKind.THEME: SettingControl.THEME_GALLERY,
}


def normalize_namespace(namespace: str) -> str:
    """校验命名空间：只允许 ``core`` 或 ``plugin.<plugin_id>``。"""
    value = str(namespace or "").strip()
    if not _NAMESPACE_RE.match(value):
        raise SettingsError(f"非法设置命名空间: {value!r}（只允许 core 或 plugin.<plugin_id>）")
    return value


def plugin_namespace(plugin_id: str) -> str:
    """由插件 ID 生成命名空间（插件 ID 与 Gallery 清单保持一致）。"""
    text = str(plugin_id or "").strip()
    if not _PAGE_ID_RE.match(text):
        raise SettingsError(f"非法插件 ID: {text!r}")
    return normalize_namespace(f"{_PLUGIN_NAMESPACE_PREFIX}{text}")


def is_core_namespace(namespace: str) -> bool:
    return namespace == _CORE_NAMESPACE


@dataclass(frozen=True)
class SettingOption:
    """枚举项：``value`` 是存储值，``label`` / ``label_key`` 只影响显示。"""

    value: str
    label: str = ""
    label_key: str = ""

    def display_label(self) -> str:
        if self.label_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.label_key, self.label or self.value))
        return self.label or self.value


@dataclass(frozen=True)
class SettingsAction:
    """设置页动作行：标题 + 说明 + 一个执行按钮。

    动作不参与保存 / 恢复默认，也不进入存储；``command`` 在设置窗口里由
    用户点击触发。参数与异常隔离由渲染层负责。
    """

    key: str
    label: str = ""
    command: Callable[[], Any] | None = None
    hint: str = ""
    label_key: str = ""
    hint_key: str = ""
    #: 按钮文案；留空时回落到 ``label``
    button: str = ""
    button_key: str = ""

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.key):
            raise SettingsError(f"非法动作键: {self.key!r}（小写字母开头，仅含 a-z0-9_）")
        if self.command is not None and not callable(self.command):
            raise SettingsError(f"{self.key}: command 必须可调用")

    def display_label(self) -> str:
        if self.label_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.label_key, self.label or self.key))
        return self.label or self.key

    def display_hint(self) -> str:
        if self.hint_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.hint_key, self.hint))
        return self.hint

    def display_button(self) -> str:
        if self.button_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.button_key, self.button or self.display_label()))
        return self.button or self.display_label()


@dataclass(frozen=True)
class SettingsInfo:
    """设置页只读信息行：标签 + 每次渲染时由插件运行时求值的文本。

    值来自插件当前状态（统计、连接摘要等），因此不进入设置存储，也不参与
    「恢复本页默认」；求值失败时显示占位符，不影响整页渲染。
    """

    key: str
    label: str = ""
    value_provider: Callable[[], Any] | None = None
    hint: str = ""
    label_key: str = ""
    hint_key: str = ""
    mono: bool = True

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.key):
            raise SettingsError(f"非法信息键: {self.key!r}（小写字母开头，仅含 a-z0-9_）")
        if self.value_provider is not None and not callable(self.value_provider):
            raise SettingsError(f"{self.key}: value_provider 必须可调用")

    def display_label(self) -> str:
        if self.label_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.label_key, self.label or self.key))
        return self.label or self.key

    def display_hint(self) -> str:
        if self.hint_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.hint_key, self.hint))
        return self.hint

    def value(self) -> str:
        if self.value_provider is None:
            return ""
        try:
            raw = self.value_provider()
        except Exception as exc:  # noqa: BLE001 - 单个信息行失败不影响整页
            from ..sysx.modules.logger_module import Logger

            Logger.warning(f"设置信息读取失败: {self.key}: {exc}")
            return "—"
        return "" if raw is None else str(raw)


@dataclass(frozen=True)
class SettingSpec:
    """单个配置项声明。

    使用类方法构造（:meth:`switch` / :meth:`select` / :meth:`number` /
    :meth:`slider` / :meth:`text` / :meth:`path` / :meth:`theme`），可以少写
    大量重复字段，也让插件作者的调用意图更清楚。
    """

    key: str
    kind: SettingKind
    default: Any
    label: str = ""
    hint: str = ""
    label_key: str = ""
    hint_key: str = ""
    control: SettingControl | None = None
    options: tuple[SettingOption, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float = 1
    decimals: int = 0
    suffix: str = ""
    placeholder: str = ""
    #: 改动后立即预览（主题 / 材质 / 背景），放弃修改时由宿主还原
    live_preview: bool = False
    #: 需要重启或重建界面才完全生效（语言、布局模式）
    requires_restart: bool = False
    #: 基座配置在 user.yaml 中的历史键名；插件留空表示与 key 相同
    storage_key: str = ""

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.key):
            raise SettingsError(f"非法设置键: {self.key!r}（小写字母开头，仅含 a-z0-9_）")
        if not isinstance(self.kind, SettingKind):
            object.__setattr__(self, "kind", SettingKind(str(self.kind)))
        if self.control is not None and not isinstance(self.control, SettingControl):
            object.__setattr__(self, "control", SettingControl(str(self.control)))
        if isinstance(self.default, (list, dict, set, tuple)):
            raise SettingsError(f"{self.key}: 默认值必须是标量，避免可变对象被共享")
        if self.kind is SettingKind.ENUM and not self.options:
            raise SettingsError(f"{self.key}: 枚举项必须提供 options")
        if self.kind in (SettingKind.INT, SettingKind.FLOAT):
            if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
                raise SettingsError(f"{self.key}: minimum 不能大于 maximum")
        # 默认值本身也要过一遍校验，避免声明阶段埋下非法值
        normalize_value(self, self.default)

    # ------------------------------------------------------------------
    # 构造快捷方式
    # ------------------------------------------------------------------
    @classmethod
    def switch(
        cls,
        key: str,
        default: bool,
        label: str,
        *,
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        live_preview: bool = False,
        storage_key: str = "",
    ) -> SettingSpec:
        return cls(
            key=key,
            kind=SettingKind.BOOL,
            default=bool(default),
            label=label,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=SettingControl.SWITCH,
            live_preview=live_preview,
            storage_key=storage_key,
        )

    @classmethod
    def select(
        cls,
        key: str,
        default: str,
        label: str,
        options: Sequence[SettingOption | tuple[str, str] | str],
        *,
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        control: SettingControl = SettingControl.SELECT,
        live_preview: bool = False,
        storage_key: str = "",
    ) -> SettingSpec:
        return cls(
            key=key,
            kind=SettingKind.ENUM,
            default=default,
            label=label,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=control,
            options=_normalize_options(options),
            live_preview=live_preview,
            storage_key=storage_key,
        )

    @classmethod
    def number(
        cls,
        key: str,
        default: int | float,
        label: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
        step: float = 1,
        decimals: int = 0,
        suffix: str = "",
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        control: SettingControl = SettingControl.NUMBER,
        live_preview: bool = False,
        storage_key: str = "",
    ) -> SettingSpec:
        kind = SettingKind.FLOAT if decimals > 0 or isinstance(default, float) else SettingKind.INT
        return cls(
            key=key,
            kind=kind,
            default=default,
            label=label,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=control,
            minimum=minimum,
            maximum=maximum,
            step=step,
            decimals=decimals,
            suffix=suffix,
            live_preview=live_preview,
            storage_key=storage_key,
        )

    @classmethod
    def slider(
        cls,
        key: str,
        default: int,
        label: str,
        *,
        minimum: int = 0,
        maximum: int = 100,
        step: int = 1,
        suffix: str = "%",
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        live_preview: bool = False,
        storage_key: str = "",
    ) -> SettingSpec:
        return cls.number(
            key,
            default,
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            suffix=suffix,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=SettingControl.SLIDER,
            live_preview=live_preview,
            storage_key=storage_key,
        )

    @classmethod
    def text(
        cls,
        key: str,
        default: str,
        label: str,
        *,
        hint: str = "",
        placeholder: str = "",
        label_key: str = "",
        hint_key: str = "",
        live_preview: bool = False,
        storage_key: str = "",
    ) -> SettingSpec:
        return cls(
            key=key,
            kind=SettingKind.TEXT,
            default=default,
            label=label,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=SettingControl.TEXT,
            placeholder=placeholder,
            live_preview=live_preview,
            storage_key=storage_key,
        )

    @classmethod
    def path(
        cls,
        key: str,
        default: str,
        label: str,
        *,
        hint: str = "",
        placeholder: str = "",
        label_key: str = "",
        hint_key: str = "",
        live_preview: bool = False,
        storage_key: str = "",
    ) -> SettingSpec:
        return cls(
            key=key,
            kind=SettingKind.PATH,
            default=default,
            label=label,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=SettingControl.PATH,
            placeholder=placeholder,
            live_preview=live_preview,
            storage_key=storage_key,
        )

    @classmethod
    def theme(
        cls,
        key: str,
        default: str,
        label: str,
        *,
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        storage_key: str = "",
    ) -> SettingSpec:
        return cls(
            key=key,
            kind=SettingKind.THEME,
            default=default,
            label=label,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            control=SettingControl.THEME_GALLERY,
            live_preview=True,
            storage_key=storage_key,
        )

    # ------------------------------------------------------------------
    # 展示
    # ------------------------------------------------------------------
    @classmethod
    def action(
        cls,
        key: str,
        label: str,
        command: Callable[[], Any] | None = None,
        *,
        button: str = "",
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        button_key: str = "",
    ) -> SettingsAction:
        """声明一个动作行（按钮不参与保存语义）。"""
        return SettingsAction(
            key=key,
            label=label,
            command=command,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            button=button,
            button_key=button_key,
        )

    @classmethod
    def info(
        cls,
        key: str,
        label: str,
        value_provider: Callable[[], Any] | None = None,
        *,
        hint: str = "",
        label_key: str = "",
        hint_key: str = "",
        mono: bool = True,
    ) -> SettingsInfo:
        """声明一个只读信息行（值在渲染时求值）。"""
        return SettingsInfo(
            key=key,
            label=label,
            value_provider=value_provider,
            hint=hint,
            label_key=label_key,
            hint_key=hint_key,
            mono=mono,
        )

    def resolved_control(self) -> SettingControl:
        return self.control or _DEFAULT_CONTROL[self.kind]

    def display_label(self) -> str:
        if self.label_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.label_key, self.label or self.key))
        return self.label or self.key

    def display_hint(self) -> str:
        if self.hint_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.hint_key, self.hint))
        return self.hint

    def option_values(self) -> tuple[str, ...]:
        return tuple(option.value for option in self.options)

    def option_label(self, value: str) -> str:
        for option in self.options:
            if option.value == value:
                return option.display_label()
        return str(value)


@dataclass(frozen=True)
class SettingsSection:
    """设置分组：渲染为一张卡片（标题 + 说明 + 若干行）。"""

    title: str
    #: 值项列表；运行时归一成 tuple，声明处接受 list 或 tuple
    items: Sequence[SettingSpec] = ()
    section_id: str = ""
    hint: str = ""
    title_key: str = ""
    hint_key: str = ""
    #: 只读信息行（统计、连接摘要等），显示在值行之前
    info: Sequence[SettingsInfo] = ()
    #: 动作行（测试 / 导入 / 同步等），显示在值行之后
    actions: Sequence[SettingsAction] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "info", tuple(self.info))
        object.__setattr__(self, "actions", tuple(self.actions))

    def display_title(self) -> str:
        if self.title_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.title_key, self.title))
        return self.title

    def display_hint(self) -> str:
        if self.hint_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.hint_key, self.hint))
        return self.hint


@dataclass(frozen=True)
class SettingsPage:
    """一个设置页：左侧导航的一项，右侧一组分组卡片。

    插件页的 ``page_id`` 留空时由 ``GallerySettings.define()`` 填成插件 ID，
    因此一个插件默认只有一页；需要多页时显式给 ``page_id``（如 ``desktop``）。
    """

    page_id: str
    title: str
    #: 分组列表。运行时 ``__post_init__`` 会归一成 tuple（内部一律按 tuple 处理），
    #: 因此声明处接受 list 或 tuple——文档示例用 list，改成 tuple 也能过。
    sections: Sequence[SettingsSection] = ()
    hint: str = ""
    icon: str = "icon_setting"
    title_key: str = ""
    hint_key: str = ""
    order: int = 100
    namespace: str = _CORE_NAMESPACE
    origin: str = "base"

    def __post_init__(self) -> None:
        if self.page_id and not _PAGE_ID_RE.match(self.page_id):
            raise SettingsError(f"非法设置页 ID: {self.page_id!r}")
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "namespace", normalize_namespace(self.namespace))
        # 同一页内键重复属于声明错误，越早失败越好；值项、信息行、动作行
        # 共用一个键空间，避免「同名动作覆盖配置」这类难以排查的写法。
        seen: set[str] = set()
        for section in self.sections:
            # 三类行的键空间共用，但类型不同；显式标注避免元组展开后
            # 类型信息丢失（mypy 会把展开结果收敛成 object）
            rows: tuple[SettingsInfo | SettingsAction | SettingSpec, ...] = (
                *section.info,
                *section.items,
                *section.actions,
            )
            for item in rows:
                if item.key in seen:
                    raise SettingsConflictError(f"{self.namespace}.{self.page_id}: 设置键重复 {item.key!r}")
                seen.add(item.key)

    def with_namespace(self, namespace: str, *, origin: str = "") -> SettingsPage:
        return replace(
            self,
            namespace=normalize_namespace(namespace),
            origin=origin or self.origin,
        )

    def display_title(self) -> str:
        if self.title_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.title_key, self.title))
        return self.title

    def display_hint(self) -> str:
        if self.hint_key:
            from ..sysx.modules.language_module import Language

            return str(Language.resolve_key(self.hint_key, self.hint))
        return self.hint

    def specs(self) -> tuple[SettingSpec, ...]:
        return tuple(item for section in self.sections for item in section.items)

    def infos(self) -> tuple[SettingsInfo, ...]:
        return tuple(item for section in self.sections for item in section.info)

    def actions(self) -> tuple[SettingsAction, ...]:
        return tuple(item for section in self.sections for item in section.actions)

    def spec(self, key: str) -> SettingSpec | None:
        for item in self.specs():
            if item.key == key:
                return item
        return None

    def full_key(self, key: str) -> str:
        """完整键：基座带页面 ID（``core.appearance.theme``），插件带命名空间。

        插件默认一页，完整键即 ``plugin.<id>.<key>``；同一插件若要拆多页，
        键仍需在该命名空间内唯一（注册表会拦截重复）。
        """
        if is_core_namespace(self.namespace):
            return f"{self.namespace}.{self.page_id}.{key}"
        return f"{self.namespace}.{key}"

    def storage_key(self, spec: SettingSpec) -> str:
        """存储键：基座沿用 user.yaml 的历史键名，插件直接用声明键。"""
        return spec.storage_key or spec.key


def _normalize_options(options: Sequence[SettingOption | tuple[str, str] | str]) -> tuple[SettingOption, ...]:
    result: list[SettingOption] = []
    for item in options:
        if isinstance(item, SettingOption):
            result.append(item)
        elif isinstance(item, str):
            result.append(SettingOption(value=item))
        elif isinstance(item, tuple) and len(item) == 2:
            result.append(SettingOption(value=str(item[0]), label=str(item[1])))
        else:  # pragma: no cover - 防御式分支
            raise SettingsError(f"非法枚举项: {item!r}")
    values = [option.value for option in result]
    if len(values) != len(set(values)):
        raise SettingsError("枚举项 value 不能重复")
    return tuple(result)


def normalize_value(spec: SettingSpec, value: Any) -> Any:
    """按声明校验并归一化取值；失败抛 :class:`SettingsValidationError`。"""
    key = spec.key
    if spec.kind is SettingKind.BOOL:
        if not isinstance(value, bool):
            raise SettingsValidationError(key, "必须是开 / 关取值")
        return value

    if spec.kind is SettingKind.INT:
        if isinstance(value, bool):
            raise SettingsValidationError(key, "必须是整数")
        if isinstance(value, float):
            if not value.is_integer():
                raise SettingsValidationError(key, "必须是整数")
            value = int(value)
        if not isinstance(value, int):
            raise SettingsValidationError(key, "必须是整数")
        return _check_range(spec, value)

    if spec.kind is SettingKind.FLOAT:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsValidationError(key, "必须是数值")
        return _check_range(spec, float(value))

    if spec.kind is SettingKind.ENUM:
        if not isinstance(value, str):
            raise SettingsValidationError(key, "必须是选项值")
        if value not in spec.option_values():
            raise SettingsValidationError(key, f"不支持的选项 {value!r}")
        return value

    if spec.kind is SettingKind.THEME:
        if not isinstance(value, str) or not value.strip():
            raise SettingsValidationError(key, "主题名不能为空")
        return value.strip()

    if spec.kind in (SettingKind.TEXT, SettingKind.PATH):
        if not isinstance(value, str):
            raise SettingsValidationError(key, "必须是文本")
        return value.strip()

    raise SettingsValidationError(key, f"未知取值类型 {spec.kind!r}")  # pragma: no cover


def _check_range(spec: SettingSpec, value: int | float) -> int | float:
    if spec.minimum is not None and value < spec.minimum:
        raise SettingsValidationError(spec.key, f"不能小于 {_fmt(spec.minimum)}")
    if spec.maximum is not None and value > spec.maximum:
        raise SettingsValidationError(spec.key, f"不能大于 {_fmt(spec.maximum)}")
    return value


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


#: 允许 ``from sllkgui.plugin import Setting`` 直接使用短名
Setting = SettingSpec
Section = SettingsSection


__all__ = [
    "Setting",
    "SettingControl",
    "SettingKind",
    "SettingOption",
    "SettingSpec",
    "SettingsAction",
    "SettingsConflictError",
    "SettingsError",
    "SettingsInfo",
    "SettingsPage",
    "SettingsSection",
    "SettingsValidationError",
    "Section",
    "is_core_namespace",
    "normalize_namespace",
    "normalize_value",
    "plugin_namespace",
]
