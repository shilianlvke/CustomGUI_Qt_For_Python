# SllkGUI · PySide6 桌面 UI 基座

基于 **PySide6** 的桌面 UI 基座，同时是一个可直接运行的桌面应用外壳：窗口骨架、主题与多语言、组件库，以及插件运行时。

当前版本：**4.0.1**（tag `base-v4.0.1`）。插件协议 API 为 **2**，详见 [插件协议](docs/PLUGIN.md)。

---

## 面向用户：Windows 启动器

`Launcher/` 目录提供双击即用的启动器，无需预先安装 Python。

| 文件 | 用途 |
| --- | --- |
| `SllkGuiLauncher.exe` | 双击启动。图形界面，自动完成环境初始化并运行基座 |
| `SllkGuiLauncher.bat` | 与 exe 同源的脚本入口（其内嵌 PowerShell 主体被打包进 exe） |
| `build_exe.py` | **仅供维护者**：把 `.bat` 的脚本主体重新打包进 `.exe`，普通用户无需关心 |

启动器首次运行会自动完成 6 步初始化：uv → Python 3.12 → Git → 拉取基座源码 → 创建虚拟环境 → 同步依赖。之后可在界面里：

- 切换**运行模式**（正式模式加载已安装插件 / 预览模式只加载内置组件预览）；
- 切换**镜像源**（国内镜像 / 官方源）；
- 选择并**更新到指定版本**（tag 或分支），查看实时日志。

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
