# 统一设置系统

> 原型：[docs/prototype/settings-window.html](prototype/settings-window.html)

设置系统把「基座配置」与「插件配置」收进同一个独立窗口、同一套声明模型与
同一套保存语义。基座按全局能力分类，插件按插件分组；配置键带命名空间，
不会互相覆盖。

## 1. 结构

```text
sllkgui/
├─ appcore/settings/          # Qt-free：声明、注册表、存储、会话、变更总线
│  ├─ schema.py               # SettingSpec / SettingsSection / SettingsPage
│  ├─ registry.py             # 命名空间隔离 + 重复键拦截
│  ├─ store.py                # core → user.yaml；plugin.<id> → plugins/<id>.yaml
│  ├─ session.py              # 草稿 / 脏值 / 保存 / 放弃 / 恢复默认
│  ├─ events.py               # 保存后向插件广播变更
│  └─ base.py                 # 基座三张页：外观 / 界面 / 启动与窗口
├─ guicore/window/settings_window/
│  ├─ window.py               # 独立窗口、导航、保存栏、关闭确认
│  └─ pages.py                # 声明 → 控件；快捷键 / 关于 / 空状态
└─ guicore/custom_ui/         # 可复用组件（见第 6 节）
```

## 2. 打开方式

- 标题栏「设置」按钮；
- 快捷键 `primary+,`（macOS 为 `⌘,`，其余 `Ctrl+,`）；
- 宿主代码：`window.controller.open_settings_window()`。

窗口是非模态的，打开期间主窗口仍可交互；主题 / 材质 / 背景改动会实时预览，
点「保存」才落盘，点「放弃」（或关闭时确认放弃）会还原。

保存成功后窗口保持打开，并停留在当前设置页；语言切换会原地重建页面文案，
不会关闭窗口或跳回第一页。只有用户主动点关闭（或按 Esc）时才允许关闭。

窗口宽高固定为主界面宽高的 80%，居中打开，并跟随主窗口尺寸变化重新适配；
窗口本身就是唯一表面，不再套内层卡片，因此没有额外的边框、背景、阴影或
外边距；标题栏右上角只保留关闭按钮。

页面头部使用固定高度与固定说明区，切换页面或产生脏值时不会伸缩、位移；
脏值数量只在底部操作栏展示。每一行设置的「恢复默认」按钮始终占位显示，
当前值已是默认值时置灰不可点，鼠标悬停不会让按钮显隐或引发布局跳动。
界面文案只描述功能与结果，不展示存储路径、注册表、重建过程等实现细节。

3.0 起基座只保留独立设置窗口这一套界面：右侧设置抽屉与左栏设置面板已删除，
标题栏按钮、``Ctrl+,``、托盘「设置…」与展厅入口全部指向 `CSettingsWindow`。

## 3. 命名空间与键

| 来源 | 完整键 | 存储位置 |
| --- | --- | --- |
| 基座 | `core.<page_id>.<key>`，如 `core.appearance.theme` | `<data_root>/settings/user.yaml` |
| 插件 | `plugin.<plugin_id>.<key>`，如 `plugin.com.example.hello.columns` | `<data_root>/settings/plugins/<plugin_id>.yaml` |

- 注册表以完整键去重，重复注册抛 `SettingsConflictError`（插件重载用
  `replace=True` 幂等覆盖）；
- 基座沿用历史 `user.yaml` 的扁平键（`theme_name` 等），通过
  `SettingSpec.storage_key` 映射，**升级不需要迁移旧文件**；
- 插件一插件一文件，卸载只撤注册、不删文件，重新安装后配置仍在；
- 所有写入采用「临时文件 + fsync + 原子替换」，失败只记日志并返回 `False`。

## 4. 基座页面

| 页面 | 内容 | 存储键 |
| --- | --- | --- |
| 外观 | 主题卡片、窗口透明度、亚克力质感、背景图 / 适应模式 / 模糊强度 | `theme_name` `acrylic_transparency` `glass_strength` `background_image` `background_fit` `background_blur` |
| 界面 | 语言、左菜单模式、抽屉模式 | `language` `menu_mode` `drawer_mode` |
| 启动与窗口 | 记住窗口尺寸 + 当前 / 最小 / 启动尺寸只读信息 | `remember_window_size` |
| 快捷键 | 基座与插件绑定按 owner 分组展示、冲突计数 | 只读（快捷键表） |
| 关于 | 版本、运行环境、目录、配置存储位置 | 只读 |

`remember_window_size=false` 时，关闭窗口不再写入 `startup_size`，下次启动
回落到 `settings/window.yaml` 的 `startup_size`。

## 5. 插件接入

在 `on_load` 中声明一次（重复调用会整体替换本插件的页面）：

```python
from sllkgui.plugin import (
    GalleryContext, Plugin, Setting, SettingsPage, SettingsSection,
)


class NotesPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.settings.define(
            SettingsPage(
                page_id="",                       # 留空 = 插件 ID（一个插件一页）
                title="便签",
                hint="插件级配置，保存在 settings/plugins/<plugin_id>.yaml。",
                sections=(
                    SettingsSection(
                        "行为",
                        (
                            Setting.switch("auto_save", True, "自动保存"),
                            Setting.select(
                                "sort", "updated", "排序方式",
                                [("updated", "按更新时间"), ("title", "按标题")],
                            ),
                            Setting.number("width", 320, "卡片宽度",
                                           minimum=240, maximum=480, suffix="px"),
                            Setting.slider("fade", 160, "淡入时长",
                                           minimum=0, maximum=600, suffix="ms"),
                        ),
                        section_id="behavior",
                    ),
                ),
            )
        )

    def _read(self):
        return self.ctx.settings.get("width", 320)
```

`GallerySettings` 能力：

| 方法 | 说明 |
| --- | --- |
| `define(page)` | 声明唯一设置页；键自动加 `plugin.<id>.` 前缀 |
| `get(key, default=None)` | 读取并校验；未声明返回 default |
| `set(key, value)` | 校验并立即写入；失败返回 `False` |
| `reset(key)` | 恢复声明默认值 |
| `values()` | 当前配置快照 |
| `on_changed(cb)` | 订阅变更，返回取消订阅函数 |
| `refresh()` | 请求设置窗口重建本插件页（动作 / 信息行变化时调用） |

### 动作行与信息行

工具类操作可以直接放进设置页，不必再单独做插件内页面：

```python
SettingsSection(
    "数据与备份",
    (),
    info=(
        Setting.info("stats", "数据统计", lambda: f"{database.count()} 首"),
    ),
    actions=(
        Setting.action(
            "export",
            "导出备份",
            lambda: export_backup(dialog_parent()),
            button="导出",
            hint="把配置、歌曲与歌单打包为 JSON。",
        ),
    ),
)
```

- 信息行的值由 `value_provider` 在页面构建与 `sync_from_session()` 时求值，
  只读、不落盘、不参与「恢复本页默认」；求值异常显示 `—`；
- 动作行的按钮只执行 `command`，不改变草稿；异常由设置页隔离并记日志；
- 动作或后台状态变化后调用 `ctx.settings.refresh()`：设置窗口按命名空间重建
  插件页，保留当前页、滚动位置与未保存草稿；窗口未打开时为空操作；
- 动作使用的是**已保存**配置，未保存草稿不会作用到 WebDAV / 导入导出等操作。

- 设置窗口里的编辑走统一的「保存 / 放弃」语义，保存后经变更总线通知插件；
- 插件卸载时加载器调用 `ctx.clear_settings()`，只撤页面与订阅，配置文件保留；
- 插件没有声明设置页时，设置窗口仍会列出该插件，并展示「未声明」空状态。

## 6. 组件库新增

| 组件 | 用途 |
| --- | --- |
| `CSideNav` / `CSideNavGroup` / `CSideNavItem` | 分组侧边导航，支持图标、徽标、禁用态与关键词过滤 |
| `CSettingGroup` | 设置分组卡片（标题 + 说明 + 发丝线分隔） |
| `CSettingRow` | 设置行：标题 / 说明 / 控件 / 已修改点 / 恢复默认 / 行内错误 |
| `CActionRow` | 动作行：标题 / 说明 / 右侧执行按钮 |
| `CInfoRow` | 只读信息行（关于页、当前窗口信息、插件统计） |
| `CEditActionBar` | 脏值操作栏：计数、错误、保存中、已保存 + 恢复默认 / 放弃 / 保存 |
| `CThemeCard` | 主题预览卡片（名称、副标题、四个调色块、选中角标） |
| `CThumbnail` | 圆角缩略图按钮（解码期缩放、选中描边） |

这些组件均从 `sllkgui.guicore` 导出，主题切换后调用 `update_style()` 即可重绘。

## 7. 保存语义

1. 编辑只写入 `SettingsSession` 草稿，行上出现「已修改」点；
2. 底部操作栏显示未保存数量，可「恢复本页默认 / 放弃 / 保存」；
3. 保存按命名空间分组写入，全部成功才清空脏值；失败保留脏值并提示；
4. 关闭窗口时若有未保存改动，弹出「放弃并关闭 / 取消」确认；
5. 主题、透明度、质感、背景与背景模糊在编辑时实时预览；放弃或关闭时按基线还原。

## 8. 测试

```powershell
uv run pytest tests/test_settings_framework.py tests/test_settings_window.py tests/test_plugin_settings.py
```

覆盖：命名空间冲突、会话保存 / 放弃 / 恢复默认、插件文件隔离、变更通知、
窗口导航 / 脏值 / 搜索、插件页面保存与卸载清理、动作行 / 信息行与插件页刷新。
