"""基座托盘服务：全进程唯一 ``QSystemTrayIcon``，随基座启动常驻。

协议要点（详见 ``docs/TRAY.md``）：

- 一个应用只有一个托盘图标，由基座持有并常驻；插件不得自建托盘；
- 图标与悬停提示固定使用基座品牌，插件没有任何修改入口；
- 插件只声明「槽 + 次序 + 文案」，菜单形态（内联 / 子菜单 / 兜底桶）
  由 :func:`plan_menu` 按槽预算裁决；
- 菜单由 :class:`~sllkgui.guicore.custom_ui.menu.CPopupMenu` 自绘（不继承
  ``QMenu``），因此可以按主题着色、画出子菜单箭头并整条链路统一关闭；
- 预算保证插件再多也不溢出屏幕：顶层最多 18 行 ≈ 610px，768p 可完整展开；
- 插件动作以 ``plugin_id:action_id`` 命名隔离，卸载/重载时由基座清理；
- 系统托盘不可用时全部降级为空操作，只告警一次。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from sllkgui.appcore import AppSettings, Language, Logger, PathFactory, record_event

from .api import GalleryTray, Permission, TrayEntry, TrayGroup
from .errors import (
    PLUGIN_PERMISSION_DENIED,
    PLUGIN_TRAY_ACTION_INVALID,
    PLUGIN_TRAY_GROUP_FORBIDDEN,
    PLUGIN_TRAY_GROUP_INVALID,
    PLUGIN_TRAY_QUOTA_EXCEEDED,
    GalleryError,
)

#: 动作短 id：字母/数字开头，允许点、下划线、连字符
_ACTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")

#: 主菜单预算。插件只增不减，预算保证「插件再多，顶层行数也有上界」：
#: quick 5 + tools 7（含兜底桶）+ status 3 + 基座 3 = 18 行。
MAX_QUICK_ROWS = 5
MAX_TOOLS_ROWS = 7
MAX_STATUS_ROWS = 3
#: 单插件动作上限；超出直接拒绝，而不是让某个插件撑爆菜单
MAX_PLUGIN_ACTIONS = 12
#: 允许内联的插件块最大动作数（再多就必须收进子菜单）
MAX_INLINE_ACTIONS = 3
MAX_TEXT_CHARS = 40
MAX_ORDER = 999

#: 兜底桶节点的类型标记；文案在渲染期解析，便于四语言切换
BUCKET_KIND = "more"


def _tray_text(key: str, default: str) -> str:
    try:
        return Language.resolve(key, default) or default
    except Exception:  # noqa: BLE001 - 语言表未就绪时用默认文案
        return default


@dataclass
class TrayAction:
    """一条已注册的插件动作（``action_id`` 已带 ``plugin_id:`` 前缀）。"""

    action_id: str
    text: str
    callback: Callable[[], None]
    order: int = 100
    plugin_id: str = ""
    plugin_name: str = ""
    group: str = TrayGroup.TOOLS
    submenu: bool | None = None
    enabled: bool = True


@dataclass(frozen=True)
class TrayPlanItem:
    """菜单计划节点；``kind`` 取 ``action`` / ``submenu`` / ``more`` / ``separator``。"""

    kind: str
    text: str = ""
    action_id: str = ""
    enabled: bool = True
    children: tuple[TrayPlanItem, ...] = ()

    @property
    def is_separator(self) -> bool:
        return self.kind == "separator"


@dataclass(frozen=True)
class TrayPlan:
    """渲染计划 + 压缩统计（供日志、``entries()`` 与测试断言）。"""

    items: tuple[TrayPlanItem, ...] = ()
    quick_rows: int = 0
    demoted: int = 0
    tools_blocks: int = 0
    submenu_blocks: int = 0
    inline_blocks: int = 0
    overflow_blocks: int = 0
    bucketed: int = 0
    status_rows: int = 0
    truncated_status: int = 0


@dataclass
class _Block:
    """同一插件在同一槽内的动作集合。"""

    plugin_id: str
    name: str
    actions: list[TrayAction] = field(default_factory=list)

    @property
    def min_order(self) -> int:
        return min((item.order for item in self.actions), default=MAX_ORDER)


_SEPARATOR = TrayPlanItem(kind="separator")


def _action_key(action: TrayAction) -> tuple[int, str, str]:
    """槽内动作排序：次序 → 文案 → 完整 id（逐层兜底，永远确定）。"""
    return (action.order, action.text.casefold(), action.action_id)


def _block_key(block: _Block) -> tuple[int, str, str]:
    """插件块排序：块内最靠前的次序 → 插件名 → 插件 id。"""
    return (block.min_order, block.name.casefold(), block.plugin_id)


def _group_blocks(actions: Iterable[TrayAction]) -> list[_Block]:
    blocks: dict[str, _Block] = {}
    for action in actions:
        block = blocks.get(action.plugin_id)
        if block is None:
            block = _Block(action.plugin_id, action.plugin_name or action.plugin_id)
            blocks[action.plugin_id] = block
        block.actions.append(action)
    ordered = sorted(blocks.values(), key=_block_key)
    for block in ordered:
        block.actions.sort(key=_action_key)
    return ordered


def _action_item(action: TrayAction, *, disabled: bool = False, text: str = "") -> TrayPlanItem:
    enabled = bool(action.enabled) and not disabled and action.group != TrayGroup.STATUS
    return TrayPlanItem(
        kind="action",
        text=text or action.text,
        action_id=action.action_id,
        enabled=enabled,
    )


def _uses_submenu(block: _Block, total_blocks: int) -> bool:
    """块形态裁决：显式偏好 > 块数规则 > 内联动作数护栏。

    - 任意动作声明 ``submenu=True`` → 子菜单；
    - 槽内多块时默认统一子菜单，只有全部声明 ``False`` 才允许内联；
    - 内联块最多 :data:`MAX_INLINE_ACTIONS` 条，防止单个插件把槽撑爆；
    - 独占槽且无偏好 → 内联（单插件时零层级）。
    """
    prefs = {action.submenu for action in block.actions}
    too_many = len(block.actions) > MAX_INLINE_ACTIONS
    if True in prefs:
        return True
    if total_blocks < 2:
        return False
    if prefs == {False} and not too_many:
        return False
    return True


def _block_rows(block: _Block, total_blocks: int) -> int:
    return 1 if _uses_submenu(block, total_blocks) else len(block.actions)


def plan_menu(actions: Iterable[TrayAction]) -> TrayPlan:
    """把注册表编译成确定性的菜单计划（纯函数，不碰 Qt）。

    规则与次序见 ``docs/TRAY.md`` §4：

    1. 槽次序固定 quick → tools → status，空槽不产生分隔线；
    2. quick 逐条内联，超出 :data:`MAX_QUICK_ROWS` 的动作降级到 tools；
    3. tools 按插件分块，行数受 :data:`MAX_TOOLS_ROWS` 约束，放不下的块
       收进兜底桶（桶内平铺 + 插件名前缀，层级不超过 2）；
    4. status 恒为禁用态，超出 :data:`MAX_STATUS_ROWS` 截断并计数；
    5. 末尾留一条分隔线给基座固定项。
    """
    pools: dict[str, list[TrayAction]] = {group.value: [] for group in TrayGroup}
    for action in actions:
        pools.setdefault(str(action.group), []).append(action)

    quick = sorted(pools[TrayGroup.QUICK], key=_action_key)
    quick_rows = quick[:MAX_QUICK_ROWS]
    demoted = quick[MAX_QUICK_ROWS:]

    blocks = _group_blocks([*pools[TrayGroup.TOOLS], *demoted])
    total = len(blocks)
    kept: list[_Block] = []
    overflow: list[_Block] = []
    budget = MAX_TOOLS_ROWS
    for index, block in enumerate(blocks):
        rows = _block_rows(block, total)
        reserve = 1 if index < total - 1 else 0  # 后面还有块时，给兜底桶留一行
        if rows <= budget - reserve:
            kept.append(block)
            budget -= rows
        else:
            overflow = blocks[index:]
            break

    status = sorted(pools[TrayGroup.STATUS], key=_action_key)
    status_rows = status[:MAX_STATUS_ROWS]

    sections: list[list[TrayPlanItem]] = []
    if quick_rows:
        sections.append([_action_item(action) for action in quick_rows])

    tools_items: list[TrayPlanItem] = []
    inline_blocks = 0
    for block in kept:
        if _uses_submenu(block, total):
            tools_items.append(
                TrayPlanItem(
                    kind="submenu",
                    text=block.name,
                    children=tuple(_action_item(action) for action in block.actions),
                )
            )
        else:
            inline_blocks += 1
            tools_items.extend(_action_item(action) for action in block.actions)
    bucketed = 0
    if overflow:
        bucket_children: list[TrayPlanItem] = []
        for block in overflow:
            for action in block.actions:
                bucket_children.append(_action_item(action, text=f"{block.name} · {action.text}"))
        bucketed = len(bucket_children)
        tools_items.append(TrayPlanItem(kind=BUCKET_KIND, children=tuple(bucket_children)))
    if tools_items:
        sections.append(tools_items)

    if status_rows:
        sections.append([_action_item(action, disabled=True) for action in status_rows])

    items: list[TrayPlanItem] = []
    for index, section in enumerate(sections):
        if index:
            items.append(_SEPARATOR)
        items.extend(section)
    if items:
        items.append(_SEPARATOR)

    return TrayPlan(
        items=tuple(items),
        quick_rows=len(quick_rows),
        demoted=len(demoted),
        tools_blocks=total,
        submenu_blocks=len(kept) - inline_blocks,
        inline_blocks=inline_blocks,
        overflow_blocks=len(overflow),
        bucketed=bucketed,
        status_rows=len(status_rows),
        truncated_status=len(status) - len(status_rows),
    )


class TrayService:
    """基座级托盘：常驻图标、动作注册、菜单重建与通知。"""

    def __init__(self) -> None:
        self._actions: dict[str, TrayAction] = {}
        self._icon: Any = None
        self._menu: Any = None
        self._show_window: Callable[[], None] | None = None
        self._quit_app: Callable[[], None] | None = None
        self._open_settings_cb: Callable[[], None] | None = None
        self._warned_unavailable = False

    # ------------------------------------------------------------------
    # 窗口回调
    # ------------------------------------------------------------------
    def attach_window(
        self,
        show_window: Callable[[], None],
        quit_app: Callable[[], None],
        open_settings: Callable[[], None] | None = None,
    ) -> None:
        self._show_window = show_window
        self._quit_app = quit_app
        self._open_settings_cb = open_settings
        self._rebuild_menu()

    # ------------------------------------------------------------------
    # 可用性 / 生命周期
    # ------------------------------------------------------------------
    def available(self) -> bool:
        try:
            from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        except ImportError:  # pragma: no cover - 无 Qt 环境
            return False
        return QApplication.instance() is not None and bool(QSystemTrayIcon.isSystemTrayAvailable())

    def is_active(self) -> bool:
        return self._icon is not None and bool(self._icon.isVisible())

    def ensure_visible(self) -> bool:
        """确保基座托盘常驻；系统不支持时返回 ``False`` 并只告警一次。"""
        if not self.available():
            if not self._warned_unavailable:
                self._warned_unavailable = True
                Logger.warning("系统托盘不可用：托盘动作与通知已禁用")
            return False
        from PySide6.QtWidgets import QSystemTrayIcon

        if self._icon is None:
            # 图标固定取基座品牌，插件没有任何替换入口
            self._icon = QSystemTrayIcon(self._base_icon())
            self._icon.setToolTip(self._tooltip_text())
            # 不用 setContextMenu：右键由 activated(Context) 拉起自绘菜单
            self._icon.activated.connect(self._on_activated)
            self._ensure_menu()
            record_event("tray.shown", category="gallery", payload={"actions": len(self._actions)})
        if not self._icon.isVisible():
            self._icon.show()
        return True

    def _base_icon(self):
        """基座托盘图标：优先应用图标，缺失时回落到内置品牌图标。"""
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        icon = app.windowIcon() if app is not None else QIcon()
        if icon.isNull():
            for path in (
                PathFactory.set_ico(AppSettings.logo),
                PathFactory.set_svg_image(AppSettings.logo_title),
            ):
                icon = QIcon(path)
                if not icon.isNull():
                    break
            if app is not None and not icon.isNull():
                app.setWindowIcon(icon)
        return icon

    @staticmethod
    def _tooltip_text() -> str:
        return _tray_text("custom_ui.sys_name", "SllkGUI")

    def _on_activated(self, reason: Any) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.show_menu()

    def show_window(self) -> None:
        if self._show_window is not None:
            self._show_window()

    def open_settings(self) -> None:
        record_event("tray.settings", category="gallery")
        if self._open_settings_cb is not None:
            self._open_settings_cb()

    def quit_app(self) -> None:
        record_event("tray.quit", category="gallery")
        if self._quit_app is not None:
            self._quit_app()

    def dispose(self) -> None:
        if self._menu is not None:
            try:
                self._menu.dismiss()
                self._menu.deleteLater()
            except Exception as exc:  # noqa: BLE001 - 退出路径不因菜单报错中断
                Logger.debug(f"托盘菜单释放失败: {exc}")
            self._menu = None
        if self._icon is not None:
            self._icon.hide()
            self._icon.deleteLater()
            self._icon = None
        self._menu = None
        self._actions.clear()
        self._warned_unavailable = False

    # ------------------------------------------------------------------
    # 动作
    # ------------------------------------------------------------------
    def add_action(
        self,
        action_id: str,
        text: str,
        callback: Callable[[], None],
        *,
        order: int = 100,
        plugin_id: str = "",
        plugin_name: str = "",
        group: str = TrayGroup.TOOLS,
        submenu: bool | None = None,
        enabled: bool = True,
    ) -> None:
        self._actions[action_id] = TrayAction(
            action_id=action_id,
            text=text,
            callback=callback,
            order=order,
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            group=group,
            submenu=submenu,
            enabled=enabled,
        )
        self._rebuild_menu()
        self.ensure_visible()

    def set_action_text(self, action_id: str, text: str) -> None:
        action = self._actions.get(action_id)
        if action is None or action.text == text:
            return
        action.text = text
        self._rebuild_menu()

    def set_action_enabled(self, action_id: str, enabled: bool) -> None:
        action = self._actions.get(action_id)
        if action is None or action.enabled == bool(enabled):
            return
        action.enabled = bool(enabled)
        self._rebuild_menu()

    def remove_action(self, action_id: str, *, plugin_id: str = "") -> None:
        action = self._actions.get(action_id)
        if action is None:
            return
        if plugin_id and action.plugin_id != plugin_id:
            return
        self._actions.pop(action_id, None)
        self._rebuild_menu()

    def remove_plugin(self, plugin_id: str) -> None:
        for action_id in [key for key, action in self._actions.items() if action.plugin_id == plugin_id]:
            self._actions.pop(action_id, None)
        self._rebuild_menu()

    def action_count(self, plugin_id: str = "", *, group: str | None = None) -> int:
        items = list(self._actions.values())
        if plugin_id:
            items = [item for item in items if item.plugin_id == plugin_id]
        if group is not None:
            items = [item for item in items if str(item.group) == str(group)]
        return len(items)

    def plan(self) -> TrayPlan:
        """当前渲染计划（只读，供诊断与测试）。"""
        return plan_menu(self._actions.values())

    def entries(self, plugin_id: str = "") -> tuple[TrayEntry, ...]:
        """按计划还原每条动作的实际落位：内联 / 子菜单 / 兜底桶。"""
        bucket_label = _tray_text("UI.ui_TrayMorePlugins", "更多插件")
        result: list[TrayEntry] = []
        for item in self.plan().items:
            if item.kind == "action":
                entry = self._make_entry(item, "inline", (item.text,))
                if entry is not None:
                    result.append(entry)
            elif item.kind == "submenu":
                for child in item.children:
                    entry = self._make_entry(child, "submenu", (item.text, child.text))
                    if entry is not None:
                        result.append(entry)
            elif item.kind == BUCKET_KIND:
                for child in item.children:
                    entry = self._make_entry(child, "bucket", (bucket_label, child.text))
                    if entry is not None:
                        result.append(entry)
        if plugin_id:
            result = [entry for entry in result if entry.plugin_id == plugin_id]
        return tuple(result)

    def _make_entry(self, item: TrayPlanItem, rendered_as: str, path: tuple[str, ...]) -> TrayEntry | None:
        action = self._actions.get(item.action_id)
        if action is None:
            return None
        return TrayEntry(
            action_id=action.action_id,
            text=action.text,
            group=str(action.group),
            order=action.order,
            enabled=item.enabled,
            plugin_id=action.plugin_id,
            rendered_as=rendered_as,
            path=path,
        )

    # ------------------------------------------------------------------
    # 提示 / 通知
    # ------------------------------------------------------------------
    def show_message(self, title: str, message: str, *, level: str = "info", timeout_ms: int = 4000) -> bool:
        if not self.ensure_visible():
            return False
        from PySide6.QtWidgets import QSystemTrayIcon

        icons = {
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error": QSystemTrayIcon.MessageIcon.Critical,
            "critical": QSystemTrayIcon.MessageIcon.Critical,
            "info": QSystemTrayIcon.MessageIcon.Information,
        }
        self._icon.showMessage(
            title, message, icons.get(str(level).lower(), QSystemTrayIcon.MessageIcon.Information), timeout_ms
        )
        return True

    def refresh_texts(self) -> None:
        """语言切换后刷新菜单外壳与悬停提示（插件动作文案由插件自己刷新）。"""
        self._rebuild_menu()
        if self._icon is not None:
            self._icon.setToolTip(self._tooltip_text())

    # ------------------------------------------------------------------
    # 菜单
    # ------------------------------------------------------------------
    def _invoke(self, action: TrayAction) -> None:
        """执行插件动作并隔离异常，避免单个回调打断 Qt 事件循环。"""
        try:
            action.callback()
        except Exception as exc:  # noqa: BLE001 - 插件回调错误不得影响基座
            Logger.exception(f"托盘动作失败 {action.plugin_id}:{action.action_id}: {exc}")

    def _ensure_menu(self) -> Any:
        """惰性创建自绘菜单（``tray`` 模块导入期不加载 Qt 与组件库）。"""
        if self._menu is None:
            from sllkgui.guicore.custom_ui.menu import CPopupMenu

            self._menu = CPopupMenu(self.menu_items())
            self._menu.triggered.connect(self._on_menu_triggered)
        return self._menu

    def show_menu(self, anchor: Any = None) -> bool:
        """在托盘图标处展开菜单（右键触发，或宿主主动调用）。"""
        if not self.ensure_visible():
            return False
        from PySide6.QtGui import QCursor

        menu = self._ensure_menu()
        self._rebuild_menu()
        menu.popup(anchor if anchor is not None else QCursor.pos(), above=True, align="right")
        record_event("tray.menu_opened", category="gallery", payload={"actions": len(self._actions)})
        return True

    def menu(self) -> Any:
        """当前菜单实例（诊断与测试用；按需创建）。"""
        return self._ensure_menu()

    def menu_items(self) -> list[Any]:
        """把当前注册表编译成菜单项树（不依赖 Qt 控件，但需要 ``MenuItem``）。"""
        return self._items_from_plan(plan_menu(self._actions.values()))

    def _items_from_plan(self, plan: TrayPlan) -> list[Any]:
        from sllkgui.guicore.custom_ui.menu import MenuItem

        items: list[Any] = [self._to_menu_item(node, MenuItem) for node in plan.items]
        items.extend(self._base_items(MenuItem))
        return items

    def _to_menu_item(self, node: TrayPlanItem, item_cls: Any) -> Any:
        if node.kind == "separator":
            return item_cls(separator=True)
        if node.kind in ("submenu", BUCKET_KIND):
            label = _tray_text("UI.ui_TrayMorePlugins", "更多插件") if node.kind == BUCKET_KIND else node.text
            return item_cls(
                label=label,
                items=[self._to_menu_item(child, item_cls) for child in node.children],
            )
        # 插件动作只挂 key：触发由 ``triggered`` 统一派发，避免 command 再执行一次
        return item_cls(
            label=node.text,
            key=node.action_id,
            disabled=not node.enabled,
        )

    def _base_items(self, item_cls: Any) -> list[Any]:
        """基座固定项：永远在最后，插件无法插入到这条分隔线之后。"""
        items = [
            item_cls(
                label=_tray_text("UI.ui_TrayShowWindow", "显示主窗口"),
                command=self.show_window,
            )
        ]
        if self._open_settings_cb is not None:
            items.append(item_cls(label=_tray_text("UI.ui_TraySettings", "设置…"), command=self.open_settings))
        items.append(item_cls(label=_tray_text("UI.ui_TrayQuit", "退出"), command=self.quit_app))
        return items

    def _on_menu_triggered(self, item: Any) -> None:
        """菜单点击：插件动作按 key 派发，基座项由 ``MenuItem.command`` 自行处理。"""
        action_id = getattr(item, "key", None)
        if not action_id:
            return
        action = self._actions.get(action_id)
        if action is not None:
            self._invoke(action)

    def _rebuild_menu(self) -> None:
        if self._menu is None:
            return
        plan = plan_menu(self._actions.values())
        self._menu.set_items(self._items_from_plan(plan))
        if plan.demoted or plan.overflow_blocks or plan.truncated_status:
            Logger.debug(
                "托盘菜单已压缩: "
                f"降级 {plan.demoted} / 兜底 {plan.overflow_blocks} 块 "
                f"（{plan.bucketed} 条）/ 截断状态 {plan.truncated_status}"
            )


class TrayHandle(GalleryTray):
    """单个插件的托盘句柄：权限校验 + 字段校验 + 命名空间 + 卸载清理。

    图标与悬停提示由基座固定持有，句柄只暴露动作与通知；注册字段的非法值在
    这里拒绝，而不是等到渲染期才发现。
    """

    def __init__(
        self,
        service: TrayService,
        plugin_id: str,
        permissions: tuple[Permission, ...],
        plugin_name: str = "",
    ) -> None:
        self._service = service
        self._plugin_id = plugin_id
        self._permissions = permissions
        self._plugin_name = (plugin_name or plugin_id).strip() or plugin_id
        self._action_ids: set[str] = set()

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    def _require(self, permission: Permission, action: str) -> None:
        if permission not in self._permissions:
            raise GalleryError(
                PLUGIN_PERMISSION_DENIED,
                f"插件未声明 {permission.value} 权限，无法{action}",
                "在 sllkgui-plugin.yml 的 permissions 中添加对应权限",
            )

    @staticmethod
    def _check_text(text: str) -> str:
        label = str(text or "").strip()
        if not label:
            raise GalleryError(PLUGIN_TRAY_ACTION_INVALID, "托盘动作文案不能为空")
        if len(label) > MAX_TEXT_CHARS:
            raise GalleryError(
                PLUGIN_TRAY_ACTION_INVALID,
                f"托盘动作文案超过 {MAX_TEXT_CHARS} 字：{label[:12]}…",
                "把细节放进 Surface 页面，菜单里只留短标签",
            )
        return label

    @staticmethod
    def _check_order(order: Any) -> int:
        if isinstance(order, bool) or not isinstance(order, int) or not 0 <= order <= MAX_ORDER:
            raise GalleryError(
                PLUGIN_TRAY_ACTION_INVALID,
                f"托盘动作 order 必须是 0–{MAX_ORDER} 的整数: {order!r}",
            )
        return order

    @staticmethod
    def _check_group(group: Any) -> str:
        value = str(getattr(group, "value", group) or "").strip().lower()
        if value == "base":
            raise GalleryError(
                PLUGIN_TRAY_GROUP_FORBIDDEN,
                "插件不能写入基座区",
                "基座固定项（显示主窗口 / 设置 / 退出）由基座独占，插件只能用 quick / tools / status",
            )
        allowed = {item.value for item in TrayGroup}
        if value not in allowed:
            raise GalleryError(
                PLUGIN_TRAY_GROUP_INVALID,
                f"未知托盘槽: {value!r}",
                f"可用槽：{' / '.join(sorted(allowed))}",
            )
        return value

    @staticmethod
    def _check_submenu(submenu: bool | None) -> bool | None:
        if submenu is not None and not isinstance(submenu, bool):
            raise GalleryError(PLUGIN_TRAY_ACTION_INVALID, f"submenu 只能是 True / False / None: {submenu!r}")
        return submenu

    # ------------------------------------------------------------------
    # 动作
    # ------------------------------------------------------------------
    def available(self) -> bool:
        return self._service.available()

    def add_action(
        self,
        action_id: str,
        text: str,
        callback: Callable[[], None],
        *,
        order: int = 100,
        group: str | TrayGroup = TrayGroup.TOOLS,
        submenu: bool | None = None,
        enabled: bool = True,
    ) -> None:
        self._require(Permission.TRAY, "注册托盘动作")
        short_id = str(action_id or "").strip()
        if not _ACTION_ID_RE.match(short_id):
            raise GalleryError(
                PLUGIN_TRAY_ACTION_INVALID,
                f"非法托盘动作 id: {short_id!r}",
                "允许字母、数字、点、下划线、连字符，长度 1–40，且不以符号开头",
            )
        label = self._check_text(text)
        order = self._check_order(order)
        group_id = self._check_group(group)
        submenu = self._check_submenu(submenu)
        full = f"{self._plugin_id}:{short_id}"
        if full not in self._action_ids and len(self._action_ids) >= MAX_PLUGIN_ACTIONS:
            raise GalleryError(
                PLUGIN_TRAY_QUOTA_EXCEEDED,
                f"单个插件最多注册 {MAX_PLUGIN_ACTIONS} 条托盘动作",
                "把低频动作放进 Surface 页面，菜单只保留高频入口",
            )
        self._service.add_action(
            full,
            label,
            callback,
            order=order,
            plugin_id=self._plugin_id,
            plugin_name=self._plugin_name,
            group=group_id,
            submenu=submenu,
            enabled=bool(enabled),
        )
        self._action_ids.add(full)

    def set_action_text(self, action_id: str, text: str) -> None:
        self._service.set_action_text(f"{self._plugin_id}:{action_id}", self._check_text(text))

    def set_action_enabled(self, action_id: str, enabled: bool) -> None:
        self._service.set_action_enabled(f"{self._plugin_id}:{action_id}", bool(enabled))

    def remove_action(self, action_id: str) -> None:
        full = f"{self._plugin_id}:{action_id}"
        self._action_ids.discard(full)
        self._service.remove_action(full, plugin_id=self._plugin_id)

    def entries(self) -> tuple[TrayEntry, ...]:
        return tuple(
            TrayEntry(
                action_id=entry.action_id.split(":", 1)[-1],
                text=entry.text,
                group=entry.group,
                order=entry.order,
                enabled=entry.enabled,
                plugin_id=entry.plugin_id,
                rendered_as=entry.rendered_as,
                path=entry.path,
            )
            for entry in self._service.entries(self._plugin_id)
        )

    def show_message(self, title: str, message: str, *, level: str = "info", timeout_ms: int = 4000) -> bool:
        self._require(Permission.NOTIFICATIONS, "发送托盘通知")
        return self._service.show_message(title, message, level=level, timeout_ms=timeout_ms)

    def clear(self) -> None:
        for action_id in list(self._action_ids):
            self._service.remove_action(action_id, plugin_id=self._plugin_id)
        self._action_ids.clear()
        self._service.remove_plugin(self._plugin_id)


__all__ = [
    "BUCKET_KIND",
    "MAX_INLINE_ACTIONS",
    "MAX_PLUGIN_ACTIONS",
    "MAX_QUICK_ROWS",
    "MAX_STATUS_ROWS",
    "MAX_TOOLS_ROWS",
    "TrayAction",
    "TrayHandle",
    "TrayPlan",
    "TrayPlanItem",
    "TrayService",
    "plan_menu",
]
