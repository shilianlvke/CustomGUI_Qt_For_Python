# Gallery 架构与命令

SllkGUI 2.0 把「组件预览」与「插件运行」拆成两个严格分离的命令。

## 1. 模式

| 命令 | 插件来源 | 外部插件 | 网络 | 用途 |
| --- | --- | --- | --- | --- |
| `sllkgui gallery` | `<package>/showcase/*` + 原生插件管理 | 否 | 否 | 组件验收、设计走查 |
| `sllkgui run` | 已安装插件 + `--plugin-dir` + 原生插件管理 | 是 | 否（不自动刷新源） | 日常使用 |

`gallery` 不读取 `registry.json`、`sources.json`、`plugins/`，也不发起网络请求；
即使本机安装了插件，也不会出现在预览里。

## 2. 存储布局

```text
<data_root>/gallery/
├── registry.json
├── sources.json
├── sources/<source_id>/       # 源仓库浅克隆
├── plugins/<plugin_id>/       # 当前安装版本
├── history/<plugin_id>/       # 上一版本（回滚）
├── data/<plugin_id>/          # ctx.data_dir
├── cache/<plugin_id>/
├── staging/                   # 安装临时目录
└── trash/                     # 卸载回收站
```

`gallery_dir` 可整体覆盖；默认 `<data_root>/gallery`。

## 3. 加载流程

```text
gallery:  discover(showcase) -> load -> registry -> window
run:      read registry -> installed -> plugin-dir -> registry -> window
          （两种模式都会注册原生插件管理页）
```

- 单个插件失败只记录错误，不影响其它插件。
- 插件管理是基座原生页面（不走插件协议），两种模式都常驻左菜单底部。
- `--safe-mode` 不加载任何外部插件，仍可进入原生插件管理。
- `--surface plugin_id/surface_id` 直接打开指定页面。
- `run --allow-local` 允许 `file://` 源（仅开发/测试）。

## 4. 命令

```text
sllkgui gallery [--surface ROUTE] [--data-dir DIR]
sllkgui run [--surface ROUTE] [--data-dir DIR] [--gallery-dir DIR]
            [--plugin-dir DIR]... [--safe-mode] [--allow-local]
            [--index-url URL] [--no-install-deps]

sllkgui source list [--json]
sllkgui source add <url> [--id ID] [--trust user|official] [--allow-local] [--refresh] [--yes]
sllkgui source remove <id> [--yes]
sllkgui source refresh [<id>|--all]
sllkgui source info <id> [--json]

sllkgui plugin search [query] [--source ID] [--json]
sllkgui plugin info <plugin_id>
sllkgui plugin install <id> [--version V] [--source ID] [--yes] [--allow-local]
sllkgui plugin install --url <git-url> [--ref REF] [--yes] [--allow-local]
sllkgui plugin list [--json]
sllkgui plugin update <id>|--all [--dry-run]
sllkgui plugin rollback <id>
sllkgui plugin remove <id> [--force] [--purge] [--yes]
sllkgui plugin enable|disable <id>
sllkgui plugin verify [<id>] [--json]
sllkgui plugin lint <path> [--json]
sllkgui plugin doctor [--json]

sllkgui doctor [--json]
sllkgui scaffold <dir> [--id ID] [--name NAME] [--source]
```

### 依赖与工具链

- `run` 启动时检测 **uv** 与 **Git**：缺失时弹窗让用户选择自动安装（pip 装 uv、
  winget 装 Git）或手动安装，也可跳过（仅影响「从源安装/刷新插件」）。
- 插件清单声明 `python_dependencies` 时，加载前检查当前解释器；缺失则提示
  自动安装（`uv pip install --python <当前解释器>`）或给出手动命令。安装失败
  的插件被隔离，记录 `PYTHON_DEPENDENCY_MISSING` / `PYTHON_DEPENDENCY_INSTALL_FAILED`。
- 镜像源优先级：`run --index-url` > `SLLKGUI_PIP_INDEX_URL` >
  `sllkgui.configure(pip_index_url=...)` > 默认 PyPI。`--no-install-deps`
  只检查不安装，适合离线/受控环境。
- `doctor` / `plugin doctor` 输出 `tools: {uv, git, pip}` 与生效镜像，便于排查。
- uv 自动安装使用官方脚本（`irm https://astral.sh/uv/install.ps1 | iex`），
  不通过 pip；Git 在 Windows 上优先用 winget。

### 托盘

- 插件通过 `ctx.tray` 使用基座唯一托盘，禁止自建 `QSystemTrayIcon`；
  需要声明 `tray` 权限，通知另需 `notifications`。
- 托盘可见时关闭主窗口只隐藏，插件与桌面小部件继续运行；托盘菜单的
  「退出」才会执行 `shutdown()`。
- 完整方案见 [TRAY.md](TRAY.md)。

## 5. 安全

- Git 仅允许 `https://` / `ssh://` / `git@host:path`；`file://` 需 `--allow-local`。
- 注入 `GIT_TERMINAL_PROMPT=0`、禁用 `ext::`、`core.hooksPath` 指向空目录、不递归子模块。
- 安装校验 `commit` 与 `manifest_sha256`；`plugin verify` 复跑校验。
- 权限是声明式知情同意，插件仍以当前用户权限运行。

## 6. 目录内核心模块

| 模块 | 职责 |
| --- | --- |
| `gallery/manifest.py` | 清单解析与校验 |
| `gallery/state.py` | registry/sources 原子读写 |
| `gallery/store.py` | 插件/历史/数据/暂存/回收站 |
| `gallery/git_backend.py` | 安全 Git 操作 |
| `gallery/resolver.py` | SemVer 依赖解析 |
| `gallery/source.py` | 源刷新与索引 |
| `gallery/manager.py` | 安装/更新/回滚/卸载/校验 |
| `gallery/loader.py` | 导入、生命周期、失败隔离 |
| `gallery/dependencies.py` | 第三方 Python 依赖检测、uv/Git 工具检查与安装 |
| `gallery/tray.py` | 基座唯一托盘、插件动作与通知（见 `docs/TRAY.md`） |
| `gallery/registry.py` | Surface 路由与默认页 |
| `gallery/context.py` | 插件上下文 |
| `gallery/lint.py` | 开发规范检查 |
| `gallery/window.py` | Gallery 外壳窗口 |
