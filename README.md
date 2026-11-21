# SllkGUI · PySide6 桌面 UI 基座

基于 **PySide6** 的桌面 UI 基座，同时是一个可直接运行的桌面应用外壳：窗口骨架、主题与多语言、组件库，以及插件运行时。

当前版本：**4.0.2**（tag `base-v4.0.2`）。插件协议 API 为 **2**，详见 [插件协议](docs/PLUGIN.md)。

---

## 面向用户：Windows 启动器

`Launcher/` 目录提供双击即用的启动器，无需预先安装 Python。

| 文件 | 用途 |
| --- | --- |
| `SllkGuiLauncher.exe` | 双击启动。图形界面，自动完成环境初始化并运行基座 |
| `src/` | C# / .NET Framework 4.8 启动器源码 |
| `ui/index.html` | 内嵌 SPA 管理界面 |
| `build.ps1` / `verify.ps1` | **仅供维护者**：编译、资源嵌入、签名与验证 |
| `README.md` / `UPGRADE.md` | 使用说明与本次升级说明 |

启动器首次运行会自动完成 7 步初始化：uv → CPython → Git → 拉取基座源码 → 创建虚拟环境 → 同步依赖 → 启动校验。之后可在界面里：

- 切换**运行模式**（正式模式加载已安装插件 / 预览模式只加载内置组件预览）；
- 切换**镜像源**（默认国内镜像，可回退官方源）；
- 选择并**更新到指定版本**（tag 或分支），查看固定滚动区域的实时日志；
- 修复/重建环境、回滚上一环境、清理旧环境、导出诊断。

默认 `standard` 配置约 176 MB（Git + PySide6 Essentials，不含 QtCharts）；需要完整 PySide6 时可在设置中切换 `full`（约 333 MB）。
运行时目录默认在启动器旁 `runtime/`；若该目录不可写，回退到 `%LOCALAPPDATA%\SllkGuiLauncher`。

## 面向开发者：从源码运行

需要 Python ≥ 3.12 与 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run sllkgui gallery   # 组件预览：只加载内置预览插件
uv run sllkgui run       # 正式模式：加载已安装插件
uv run sllkgui --help    # 查看全部命令
```

CLI 还提供插件源与插件管理（`source` / `plugin` 子命令）、插件校验、脚手架与诊断（`sllkgui doctor`）。

## 插件一句话说明

一个 Git 仓库 = 一个插件，通过 **Surface** 向 Gallery 贡献页面；插件在宿主进程内运行，权限声明用于知情同意而非沙箱。完整契约见 [插件协议](docs/PLUGIN.md) 与 [公开 API](docs/API.md)。

## 文档

- [文档索引](docs/README.md) · [架构](docs/ARCHITECTURE.md) · [组件速查](docs/COMPONENTS.md)
- [插件协议](docs/PLUGIN.md) · [设置系统](docs/SETTINGS.md) · [托盘](docs/TRAY.md) · [快捷键](docs/SHORTCUTS.md)
- [更新日志](CHANGELOG.md) · [许可证](LICENSE)

本项目使用 [MIT](LICENSE) 许可证，欢迎通过 issue / PR 贡献。
