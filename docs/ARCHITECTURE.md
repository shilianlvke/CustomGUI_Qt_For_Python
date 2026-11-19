# 架构总览（2.0）

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
| `sllkgui.appcore` | 配置、主题、语言、日志、遥测、错误边界 | 仅标准库（不 import PySide6，有守卫测试锁定） |
| `sllkgui.guicore` | 组件库、设计令牌、窗口部件、快捷键表 | PySide6 |
| `sllkgui.gallery` | 插件协议、源、存储、安装、加载、外壳 | appcore + guicore |
| `sllkgui.showcase` | 内置组件预览插件 | plugin API + guicore |
| `sllkgui.guis.pages` | 基座原生页面（插件管理） | guicore + gallery 查询 |
| `sllkgui.plugin` | 插件作者公开门面 | gallery.api |

## 关键约定

- 一个 Git 仓库 = 一个插件；插件可贡献多个 Surface。
- 路由键 `plugin_id/surface_id`；菜单按钮与页面 objectName 由路由派生。
- `gallery` 与 `run` 共用窗口外壳，只替换插件来源；插件管理是原生页面，
  不参与插件发现与加载。
- 设置只有一套界面：独立设置窗口合并软件信息、外观、界面与插件页，取代旧的右侧抽屉。
- 旧 App 协议（`AppPlugin` / `AppPage` / `apps/` / `plugins.yml`）已删除，不保留兼容层。
- 插件代码在宿主进程内执行；权限声明用于知情同意，不是沙箱。
- 输入类能力（托盘、快捷键）由基座持有唯一实例，插件只注册条目：托盘走
  `ctx.tray`（声明槽与次序，形态与预算由基座裁决），快捷键走 `ctx.shortcuts`，
  两者都在卸载时由加载器统一清理。
- 插件目录**不进入** `sys.path`：插件内部一律用相对导入（`from . import x`），
  否则插件里的同名模块会遮蔽标准库、劫持全进程。
- 类型承诺是分层的：`sllkgui.plugin` / `sllkgui.window` / 插件协议 / 设置 schema
  这层由 mypy 门禁保证类型完整；`guicore` 组件库内部只保证运行期行为正确，
  不保证注解完备。门禁范围见 `pyproject.toml` 的 `[tool.mypy]`。

## 相关文档

- [PLUGIN.md](./PLUGIN.md)：插件协议
- [PLUGIN_STANDARD.md](./PLUGIN_STANDARD.md)：开发规范
- [SOURCE.md](./SOURCE.md)：源仓库协议
- [GALLERY.md](./GALLERY.md)：命令与存储
- [TRAY.md](./TRAY.md)：托盘所有权与插件动作
- [SHORTCUTS.md](./SHORTCUTS.md)：快捷键作用域、优先级与插件协议
