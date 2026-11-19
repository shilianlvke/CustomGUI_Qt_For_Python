# 插件协议

一个 Git 仓库 = 一个插件，插件通过 **Surface** 向 Gallery 贡献页面。插件代码运行在
Gallery 进程内，清单里的权限用于安装前知情同意，不是沙箱。

## 1. 仓库结构

```text
sllkgui-notes/
├── sllkgui-plugin.yml      # 必需：运行时清单
├── plugin.py               # 必需：导出 PLUGIN 实例
├── pages/                  # 可选：页面实现
├── resource/
│   ├── icon/*.svg
│   └── lang/{zh_cn,zh_tw,en_us,ja_jp}.yml
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## 2. 清单 `sllkgui-plugin.yml`

```yaml
schema: 1
api: 1
id: com.example.notes
name: Notes
version: 1.2.0
description: 通用便签
license: MIT
entry: plugin.py
requires:
  sllkgui: ">=3.0.0,<4.0.0"
  python: ">=3.12"
python_dependencies:
  - psutil>=6
  - pyyaml>=6.0.3
surfaces:
  - id: notes
    title: {zh_cn: 便签, zh_tw: 便籤, en_us: Notes, ja_jp: ノート}
    icon: resource/icon/notes.svg
    impl: pages/notes.py
    default: true
    order: 10
permissions:
  - filesystem.write
```

- `id`：`^[a-z0-9][a-z0-9._-]{0,63}$`，全局唯一。
- `version`：SemVer。
- `surfaces`：至少一个；`default: true` 最多一个；`order` 越小越靠前。
- `impl`（3.0 起可选但建议声明）：该 Surface 的页面实现文件路径，相对插件根目录。
  基座在加载期校验它是否存在，缺失时跳过整个插件并记
  `PLUGIN_SURFACE_IMPL_MISSING`，而不是等到用户点击时才崩。
- `permissions`：`network`、`filesystem.read`、`filesystem.write`、`subprocess`、
  `clipboard`、`notifications`、`tray`、`shortcuts`、`autostart`、`system.info`。
- `python_dependencies`（可选）：第三方 Python 包声明（PEP 508 格式，如
  `psutil>=6`）。基座在导入插件**之前**检查；缺失时弹窗让用户选择自动安装
  （`uv pip install` 到当前解释器）或手动安装，安装失败则隔离该插件并记录
  `PYTHON_DEPENDENCY_MISSING`。镜像源见 `sllkgui run --index-url` /
  `SLLKGUI_PIP_INDEX_URL` / `sllkgui.configure(pip_index_url=...)`。
  能用标准库、纯 Python 小库或 `vendor/` 内联解决的，优先不声明。

  > **冻结形态例外**：宿主以 PyInstaller 等方式打包分发时，解释器不是可执行的
  > Python，`uv pip install` 无从谈起。此时基座直接报 `FROZEN_ENV_UNSUPPORTED`
  > 并跳过该插件，而不是给出一条注定失败的手动命令。冻结形态下的可行做法：
  > 把依赖内置到 `vendor/` 随仓库分发、由宿主在启动前自行安装、或改用源码分发
  > 形态（启动器 bootstrap 出真实 venv）。

## 3. 入口 `plugin.py`

```python
from sllkgui.plugin import GalleryContext, Plugin


def build_notes(ctx: GalleryContext):
    from .pages.list import NotesPage

    with ctx.timing("notes.surface.build"):
        page = NotesPage(ctx)
    ctx.event("surface.ready", {"surface": "notes"})
    return page


class NotesPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading notes")
        with ctx.timing("notes.load"):
            self.data_file = ctx.data_dir / "notes.yaml"
        ctx.event("notes.loaded")

    def surfaces(self):
        return {"notes": build_notes}

    def on_locale_changed(self, locale: str) -> None:
        self.ctx.log(f"locale -> {locale}")

    def on_unload(self) -> None:
        self.ctx.log("unloading notes")
        self.ctx.event("notes.unloaded")


PLUGIN = NotesPlugin()
```

规则：

- 必须导出模块级 `PLUGIN` **实例**；不接受 `PAGE`、`register_plugins` 等旧形式。
- `surfaces()` 返回 `{surface_id: factory}`，factory 签名 `(GalleryContext) -> QWidget`。
- 清单 `surfaces[].id` 与 factory 键一一对应；缺失会报 `PLUGIN_SURFACE_FACTORY_MISSING`。
- 生命周期：`on_load` → `surfaces()` →（语言切换）`on_locale_changed` → `on_unload`。

### 3.1 插件内一律用相对导入

3.0 起基座**不会**把插件目录加入 `sys.path`。原因很直接：把插件根插到
`sys.path[0]` 等于让它排到标准库之前，插件里一个 `json.py` 就能在全进程劫持
`import json`，影响基座自身与其它插件。

因此插件内部**必须**使用相对导入：

```python
# 正确：相对导入，入口模块被当作包加载（submodule_search_locations）
from .pages.list import NotesPage
from . import helpers

# 错误：绝对导入——插件目录不在 sys.path 里，会抛 ModuleNotFoundError
import helpers
```

基座会在错误信息里直接给出改法（`插件内请用相对导入：把 import helpers 改为
from . import helpers`）。若确实需要加载插件目录下的文件，用 `importlib`
配合插件根路径自行处理，不要动 `sys.path`。

## 4. `GalleryContext`

| 成员 | 说明 |
| --- | --- |
| `plugin_id` / `plugin_version` | 插件元数据 |
| `data_dir` / `cache_dir` | 可写目录，自动创建 |
| `locale` / `theme` | 当前语言 / 主题名 |
| `permissions` | 清单声明的权限 |
| `resource(*parts)` | `resource/` 内只读路径 |
| `open_surface(id)` | 跳转到本插件 Surface |
| `text(key, default=None, **kwargs)` | 多语言文案，缺失回退 `en_us` |
| `log(message, level="info")` | 基座日志，自动加插件前缀 |
| `logger` | 标准库 `logging.Logger`，已桥接基座 |
| `event(name, payload=None, level="info")` | 基座遥测 |
| `timing(name, payload=None)` | 上下文计时，自动记录 `duration_ms` |
| `report_error(code, message, detail=None)` | 日志 + 遥测 + 非阻塞错误提示 |
| `parent_window()` | Gallery 主窗口（对话框父级） |
| `tray` | 基座常驻托盘的分组动作：槽 + 次序 + 文案（形态由基座裁决，见 `docs/TRAY.md`） |
| `shortcuts` | 基座快捷键表：注册/更新/注销、启停与冲突查询（见 `docs/SHORTCUTS.md`） |
| `settings` | 统一设置：声明页面、读写本插件配置（见 `docs/SETTINGS.md`） |

## 5. 托盘动作

插件只声明**语义**，菜单形态由基座按槽预算裁决（详见 `docs/TRAY.md`）：

```python
ctx.tray.add_action(
    "start", "开始专注", self.toggle_focus,   # id 在插件内唯一，重名覆盖
    group="tools",                            # quick | tools | status
    order=10,                                 # 槽内次序，越小越靠前
)
ctx.tray.add_action("running", "专注中 · 剩 12:34", lambda: None, group="status")

for entry in ctx.tray.entries():              # 实际落位：inline / submenu / bucket
    ctx.log(f"{entry.action_id} -> {entry.rendered_as} {entry.path}")
```

- `quick`：内联直达，每插件至多 1 条、文案写成「动词 + 对象」；
- `tools`：默认槽，独占时内联，槽内出现第二个插件时自动收进同名子菜单；
- `status`：只读状态，恒为禁用态，不做点击回调；
- 图标、悬停提示、基座固定项与菜单外壳没有插件 API，属于结构性禁止。

## 6. 设置

插件在 `on_load` 中声明一次设置页，基座设置窗口会自动出现「插件设置」条目：

```python
from sllkgui.plugin import (
    GalleryContext, Plugin, Setting, SettingsPage, SettingsSection,
)


class NotesPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.settings.define(
            SettingsPage(
                page_id="",                       # 留空 = 插件 ID
                title="便签",
                sections=(
                    SettingsSection(
                        "行为",
                        (
                            Setting.switch("auto_save", True, "自动保存"),
                            Setting.number("width", 320, "卡片宽度",
                                           minimum=240, maximum=480, suffix="px"),
                        ),
                        section_id="behavior",
                    ),
                ),
            )
        )

    def _width(self) -> int:
        return self.ctx.settings.get("width", 320)
```

- 完整键自动加 `plugin.<plugin_id>.` 前缀，与基座、其它插件互不冲突；
- 配置写在 `<data_root>/settings/plugins/<plugin_id>.yaml`，卸载不删除；
- `get` / `set` 立即生效；设置窗口里的编辑走统一「保存 / 放弃」，保存后通过
  `on_changed` 通知插件；
- 没有声明设置页的插件仍会出现在设置窗口，显示「未声明」空状态；
- 卸载时加载器调用 `ctx.clear_settings()`，只撤页面与订阅。

工具类操作可以直接声明为动作行，统计类信息声明为信息行：

```python
SettingsSection(
    "数据",
    (),
    info=(Setting.info("stats", "数据统计", lambda: f"{db.count()} 首"),),
    actions=(Setting.action("export", "导出备份", self._export, button="导出"),),
)
```

动作或后台状态变化后调用 `ctx.settings.refresh()`，设置窗口会重建本插件页
并保留未保存草稿；窗口未打开时为空操作。详见 `docs/SETTINGS.md`。

可用控件：`Setting.switch` / `select` / `number` / `slider` / `text` / `path` /
`theme`，以及非值的 `Setting.action` / `Setting.info`。

## 7. 快捷键

快捷键与内置功能共用基座同一张注册表，按「作用域 → 优先级 → 冲突策略」裁决：

```python
class NotesPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        self.handle = ctx.shortcuts.register(
            "new-note",              # 插件内唯一，基座自动加 plugin_id 前缀
            "primary+alt+n",         # macOS 自动变 ⌘⌥N，Windows 为 Ctrl+Alt+N
            self._new_note,
            scope="global",          # global 全应用；local 仅本插件页面
            description="新建便签",   # 供设置页/诊断展示
            conflict="error",        # error 拒绝 / shadow 共存 / replace 覆盖
        )

    def _new_note(self) -> None:
        self.ctx.open_surface("notes")

    def on_locale_changed(self, locale: str) -> None:
        self.handle.update(description=self.ctx.text("shortcuts.new_note", "新建便签"))

    def on_unload(self) -> None:
        self.handle.unregister()     # 可选：加载器也会统一清理
```

要点：

- 序列用 `primary` 而不是写死 `ctrl` / `cmd`，跨平台语义一致。
- 内置项（`primary+k` 搜索、`primary+,` 设置）已锁定且优先级最高，插件撞上会
  直接收到 `PLUGIN_SHORTCUT_CONFLICT`，请换序列。
- 局部快捷键必须传 `host`（Surface 页面根控件），宿主销毁时自动注销。
- 文本输入框聚焦时，不含 Ctrl/Alt/Meta 的绑定不会触发，不会抢走正常输入。

## 8. 多语言

`resource/lang/<locale>.yml` 支持嵌套字典；四个语言文件必须齐全且键集合一致。
`ctx.text("home.title")` 读取当前语言；切换语言后 Loader 会调用
`on_locale_changed`，页面可自行刷新文案。

## 9. 本地开发

```powershell
# 直接加载本地插件目录，不写 registry
uv run sllkgui run --plugin-dir ..\my-plugin

# 规范检查
uv run sllkgui plugin lint ..\my-plugin

# 运行仓库内最小示例
uv run sllkgui run --plugin-dir examples\plugin-hello
```

## 10. 发布

1. 打 SemVer tag（如 `v1.2.0`）。
2. 在官方源提交 `plugins/<id>/entry.yaml`（见 `docs/SOURCE.md`）。
3. 用户执行 `sllkgui source refresh` 后即可搜索安装。
