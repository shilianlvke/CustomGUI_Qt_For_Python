# 基座托盘方案

> 状态：已实现（`base-v2.1.0`）
>
> 目标：全应用只有一个托盘图标，由基座统一持有；插件只注册动作与通知，
> 不再各自创建 `QSystemTrayIcon`。

## 1. 所有权与边界

| 项 | 归属 | 说明 |
| --- | --- | --- |
| 托盘图标 / 菜单 / 生命周期 | 基座 `gallery/tray.py` | 全进程唯一，随 Gallery 窗口创建与销毁 |
| 菜单动作 | 插件 | 通过 `ctx.tray.add_action()` 注册，按 `order` 排序 |
| 系统通知 | 插件 | `ctx.tray.show_message()`，需要 `notifications` 权限 |
| 「显示主窗口」「退出」 | 基座 | 固定存在，始终位于插件动作之后 |

插件不得创建 `QSystemTrayIcon`、不得拦截应用退出；这样避免多插件抢图标、
托盘对象泄漏，以及「关窗后谁负责退出」的歧义。

## 2. 公开 API

```python
class GalleryTray(ABC):
    def available(self) -> bool: ...
    def set_icon(self, path: str | Path | None = None) -> bool: ...
    def set_tooltip(self, text: str) -> None: ...
    def add_action(self, action_id: str, text: str, callback, *, order: int = 100) -> None: ...
    def set_action_text(self, action_id: str, text: str) -> None: ...
    def remove_action(self, action_id: str) -> None: ...
    def show_message(self, title: str, message: str, *, level="info", timeout_ms=4000) -> bool: ...
    def clear(self) -> None: ...
```

- `ctx.tray` 需要清单声明 `permissions: [tray]`；未声明时抛
  `PLUGIN_PERMISSION_DENIED`。
- `show_message` 额外需要 `notifications` 权限。
- `action_id` 由基座加 `plugin_id:` 前缀隔离；插件间重名互不影响。
- 图标路径应使用 `ctx.resource(...)`，基座不校验插件目录之外的路径（插件本身
  已有文件权限）。
- 语言切换时基座刷新菜单外壳；插件在 `on_locale_changed` 里调用
  `set_action_text` 更新自己的动作文案。

## 3. 生命周期

```text
plugin.on_load
  └─ ctx.tray.set_icon / add_action      # 首次调用惰性创建托盘图标
plugin.on_locale_changed
  └─ ctx.tray.set_action_text
plugin.on_unload
  └─ 加载器调用 ctx.clear_tray()          # 移除该插件全部动作，恢复默认图标
GalleryWindow.closeEvent
  ├─ 托盘可见且非强制退出 → hide() + ignore()，运行时与桌面小部件继续
  └─ 托盘不可见 / 托盘「退出」 → shutdown() + 关闭窗口
```

- 系统托盘不可用（无桌面环境 / offscreen）时，`available()` 返回 `False`，
  所有方法安全降级为空操作并只告警一次。
- `GalleryRuntime.reload()` 会先卸载插件再重新加载，托盘动作随之重建。

## 4. 插件使用示例

```python
def on_load(self, ctx: GalleryContext) -> None:
    self.ctx = ctx
    tray = ctx.tray
    tray.set_icon(ctx.resource("icon", "pyrm.svg"))
    tray.set_tooltip("py-rm")
    tray.add_action("toggle", self._text("tray.hide_skins"), self._toggle_widgets, order=10)

def on_locale_changed(self, locale: str) -> None:
    self.ctx.tray.set_action_text("toggle", self._text("tray.hide_skins"))

def on_unload(self) -> None:
    if self.ctx is not None:
        self.ctx.tray.clear()
```

## 5. 兼容与限制

- 只支持 SllkGUI 2.1+；旧基座没有 `ctx.tray`，插件需在清单
  `requires.sllkgui` 中声明下限。
- 托盘菜单是扁平列表，不支持二级子菜单与自定义菜单控件；复杂配置应放在
  Surface 页面里。
- 通知使用系统原生 `QSystemTrayIcon.showMessage`，不提供通知中心历史。

## 6. 后续规划

| 项 | 说明 |
| --- | --- |
| 动作分组 | 按插件分组显示子菜单（`add_menu(plugin_id)`），需要统一的本地化标题 |
| 图标状态 | 支持 `set_badge(count)` / 动态图标（需跨平台评估） |
| 托盘权限细化 | 区分「注册动作」与「替换图标」，安装确认页展示更精确 |
| 无托盘降级 | 无系统托盘时把插件动作镜像到主窗口菜单 |
