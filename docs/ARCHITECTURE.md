# 架构总览

```text
┌─────────────────────────────────────────────┐
│                GalleryWindow                │
│  标题栏 / 左菜单 / 页面栈 / 四向抽屉        │
└──────────────────┬──────────────────────────┘
                   │ GalleryRegistry（路由）
┌──────────────────┴──────────────────────────┐
│                 GalleryLoader               │
│  导入 / 生命周期 / Surface 校验 / 失败隔离  │
└───────┬───────────────────────┬─────────────┘
        │                       │
  showcase/*                plugins/*
（gallery 模式）            （run 模式）
        │                       │
        └──────────┬────────────┘
                   │
        guis/pages/*（原生插件管理，两种模式常驻）
┌──────────────────┴──────────────────────────┐
│  appcore（配置/主题/语言/日志/遥测）        │
│  guicore（组件/令牌/窗口部件）              │
└─────────────────────────────────────────────┘
```

## 分层

| 层 | 职责 | 依赖 |
| --- | --- | --- |
| `sllkgui.appcore` | 配置、主题、语言、日志、遥测、错误边界 | 不依赖 Qt（仅依赖 pyyaml；有守卫测试锁定不 import PySide6） |
| `sllkgui.guicore` | 组件库、设计令牌、窗口部件、快捷键表 | appcore + PySide6 |
| `sllkgui.gallery` | 插件协议、源、存储、安装、加载、外壳 | appcore + guicore + guis（**仅组合根 `gallery/window.py` 可 import guis**） |
| `sllkgui.showcase` | 内置组件预览插件 | appcore + guicore + guis（经插件 API；内置预览中有 1 处直接引用 guis 的 `MainFunctions`（overlays/page.py:77），属允许的依赖边但非典型插件写法） |
| `sllkgui.guis.pages` | 基座原生页面（插件管理） | appcore + guicore + 窗口持有的 gallery registry（鸭子类型读取，**不 import gallery 模块**） |
| `sllkgui.plugin` | 插件作者公开门面 | gallery.api |

**包间依赖矩阵以 `tests/test_architecture_boundaries.py` 的 `ALLOWED_EDGES` / `EDGE_ALLOWLIST` 为唯一真相**，
上表与之对齐；新增跨包 import 时先改守卫、再同步本表。

## 关键约定

- 一个 Git 仓库 = 一个插件；插件可贡献多个 Surface。
- 路由键 `plugin_id/surface_id`；菜单按钮与页面 objectName 由路由派生。
- `gallery` 与 `run` 共用窗口外壳，只替换插件来源；插件管理是原生页面，
  不参与插件发现与加载。
- 设置只有一套界面：独立设置窗口合并软件信息、外观、界面与插件页，取代旧的右侧抽屉。
- 旧 App 协议（`AppPlugin` / `AppPage` / `apps/` / `plugins.yml`）已删除，不保留兼容层。
- 插件代码在宿主进程内执行；权限声明用于知情同意，不是沙箱。
- 插件重载是**按插件选择性刷新**：`GalleryRuntime.reload_plugins()` 只卸载/加载目标及其反向依赖者，
  未受影响插件与页面实例保留；`GalleryWindow.reload_plugin_in_place()` 只失效目标页面并同步左菜单。
  全量重载仍保留为 `force_full=True` 回退路径。
- 选择性重载先做清单/依赖/Surface 实现预检，再卸载旧实例；更新失败尝试用 history 目录回滚。
  原生扩展（`.pyd` / `.so` / `.dll`）不参与热替换，返回 `PLUGIN_RESTART_REQUIRED`。
- 可见反馈只有一条通道：插件走 `ctx.toast`，原生页走 `guicore.toast_bus()`，
  去重/通道/溢出/卸载清理由总线裁决（见 `docs/TOAST.md`）；`CToast` 只负责渲染。
- 输入类能力（托盘、快捷键）由基座持有唯一实例，插件只注册条目：托盘走
  `ctx.tray`（声明槽与次序，形态与预算由基座裁决），快捷键走 `ctx.shortcuts`，
  两者都在卸载时由加载器统一清理。
- 插件目录**不进入** `sys.path`：插件内部一律用相对导入（`from . import x`），
  否则插件里的同名模块会遮蔽标准库、劫持全进程。
- 类型承诺是分层的：`sllkgui.plugin` / `sllkgui.window` / 插件协议 / 设置 schema
  这层由 mypy 门禁保证类型完整；`guicore` 组件库内部只保证运行期行为正确，
  不保证注解完备。门禁范围见 `pyproject.toml` 的 `[tool.mypy]`。

### 术语澄清

"Gallery" 在不同语境含义不同，不要混用：

- `GalleryWindow`：插件 Surface 的宿主外壳（标题栏、左菜单、页面栈、抽屉），
  `gallery` 模式与 `run` 模式共用同一个类，并非只指预览模式。
- `gallery`（CLI 子命令）：仅加载内置预览；`sllkgui.gallery` 包：插件运行时
  （协议、源、存储、安装、加载、外壳）；存储目录名 `gallery`：数据目录约定。
  三者同名但职责不同。
- `guis`：窗口装配层（shell，主窗口组装、页面栈、语言服务）；`guicore`：组件库
  （组件、令牌、窗口部件）。二者职责不同，不要混称。

## 相关文档

| 文档 | 内容 |
| --- | --- |
| [PLUGIN.md](./PLUGIN.md) | 插件协议：清单、Surface、生命周期、相对导入约定 |
| [PLUGIN_STANDARD.md](./PLUGIN_STANDARD.md) | 插件开发规范与 lint 规则 |
| [SOURCE.md](./SOURCE.md) | 源仓库协议 |
| [GALLERY.md](./GALLERY.md) | 命令与存储 |
| [API.md](./API.md) | 公开 API 速查 |
| [SETTINGS.md](./SETTINGS.md) | 设置 schema 与持久化 |
| [COMPONENTS.md](./COMPONENTS.md) | 组件分类与设计令牌 |
| [POPUP_MENU.md](./POPUP_MENU.md) | 自绘弹出菜单：接口、交互与 QMenu 迁移 |
| [TRAY.md](./TRAY.md) | 托盘所有权与插件动作 |
| [SHORTCUTS.md](./SHORTCUTS.md) | 快捷键作用域、优先级与插件协议 |
