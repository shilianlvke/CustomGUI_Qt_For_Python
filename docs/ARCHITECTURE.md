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
  showcase/*            core_plugins/* + plugins/*
（gallery 模式）          （run 模式）
        │                       │
┌───────┴───────────────────────┴─────────────┐
│  appcore（配置/主题/语言/日志/遥测）        │
│  guicore（组件/令牌/窗口部件）              │
└─────────────────────────────────────────────┘
```

## 分层

| 层 | 职责 | 依赖 |
| --- | --- | --- |
| `sllkgui.appcore` | 配置、主题、语言、日志、遥测、错误边界 | 标准库 |
| `sllkgui.guicore` | 组件库、设计令牌、窗口部件 | PySide6 |
| `sllkgui.gallery` | 插件协议、源、存储、安装、加载、外壳 | appcore + guicore |
| `sllkgui.showcase` | 内置组件预览插件 | plugin API + guicore |
| `sllkgui.core_plugins` | 核心插件（插件管理） | plugin API + guicore |
| `sllkgui.plugin` | 插件作者公开门面 | gallery.api |

## 关键约定

- 一个 Git 仓库 = 一个插件；插件可贡献多个 Surface。
- 路由键 `plugin_id/surface_id`；菜单按钮与页面 objectName 由路由派生。
- `gallery` 与 `run` 共用窗口外壳，只替换插件来源。
- 旧 App 协议（`AppPlugin` / `AppPage` / `apps/` / `plugins.yml`）已删除，不保留兼容层。
- 插件代码在宿主进程内执行；权限声明用于知情同意，不是沙箱。

## 相关文档

- [PLUGIN.md](./PLUGIN.md)：插件协议
- [PLUGIN_STANDARD.md](./PLUGIN_STANDARD.md)：开发规范
- [SOURCE.md](./SOURCE.md)：源仓库协议
- [GALLERY.md](./GALLERY.md)：命令与存储
