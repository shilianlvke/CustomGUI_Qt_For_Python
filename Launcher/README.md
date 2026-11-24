# SllkGui Launcher 5.0

单文件 Windows 启动器：双击后按需安装 uv、CPython、Git 与 PySide6 依赖，然后启动 SllkGui 基座。
启动器本身是 **C# / .NET Framework 4.8** 的 WinExe，约 **263 KiB（269,312 B）**（含 icon.ico 与嵌入资源），不依赖 PowerShell 脚本、不需要管理员权限。

## 设计目标

- 用户只需要一个 exe；首次运行按需下载，后续启动直接复用已安装环境。
- 版本更新不修改当前环境：每次更新构建一个独立的新环境，成功后原子切换；失败保留原环境。
- 不再使用固定资源槽和二进制补丁；UI 与 manifest 作为 .NET 资源嵌入，随源码一起编译。
- 本地管理界面只绑定回环，API 需要每次运行随机生成的 token；页面使用 nonce CSP。

## 架构

```
SllkGuiLauncher.exe (C# / .NET 4.8 / WinExe)
├─ LauncherApp        状态聚合、HTTP 路由、配置/更新/回滚/清理
├─ Bootstrap          7 步安装管线：uv → CPython → Git → source → venv → deps → verify
├─ Toolchain          uv / git 进程封装、版本探测、环境变量隔离
├─ AppRunner          启动/健康检查/停止基座，PID 记录与日志尾部
├─ HttpServer         TcpListener HTTP/1.1：token、Host/Origin、CSP、body 上限
├─ EnvManager         envs/<id>、current.json、previous.json、回滚
└─ ui/index.html      内嵌 SPA（GZip 压缩为 .NET 资源，运行时注入 token/nonce）
```

关键路径：

1. 双击 exe → 启动本地 HTTP（127.0.0.1，默认 17823 起）→ 打开系统浏览器。
2. 首次运行点击“开始初始化” → 按配置下载/安装 → 写入 `current.json`。
3. 之后启动器始终可打开管理界面；“打开基座”启动 PySide6 应用，`--launch` 可跳过界面直接启动。
4. 更新/修复 → 在 `envs/<new-id>` 构建新环境 → 成功后切换 `current.json`；旧环境保留为 `previous.json`，可回滚。
5. 清理只删除非 current/previous 的旧环境与 cache 根目录下载包，保留 uv 缓存。

## 目录

```
src/                 C# 源码
ui/index.html        SPA（被 build.ps1 压缩后嵌入 exe）
manifest.json        组件版本、SHA-256、repo、profile 估算
app.manifest         asInvoker / longPathAware / Win10+ 兼容
icon.ico             exe 图标 / favicon（128×128）
mihoutao.svg         UI 品牌图标（内嵌资源）
build.ps1            编译 + 资源嵌入 + 可选签名
verify.ps1           构建 + selftest + print-plan + 版本/签名检查
```

## 构建

要求：Windows 10 1809+ / Windows 11，.NET Framework 4.8（系统自带），无需 Visual Studio。

```powershell
.\build.ps1
```

输出 `SllkGuiLauncher.exe`，带 FileVersion/ProductVersion/CompanyName 和内嵌图标。
签名（可选，需要 pfx）：

```powershell
.\build.ps1 -Sign -CertPath .\codesign.pfx -CertPassword '***'
# 或设置 SLLK_SIGN_CERT / SLLK_SIGN_PASSWORD
```

未提供证书时构建仍成功，但会打印 `未签名构建` 提示；发布前应签名并提交 SmartScreen。

## 验证

```powershell
.\verify.ps1
```

包含：

- 重新构建并检查 exe 大小、FileVersion、ProductName。
- `--selftest`：旧配置被丢弃、旧 runtime 不被接管、HTTP 200/403/404/413、Host/Origin、CSP、小 POST body 同包、token。
- `--print-plan`：打印固定版本、SHA-256、profile 下载估算。
- Authenticode 状态（可用 `-RequireSignature` 强制要求）。

当前验证结果：**VERIFY PASS**（见 `verify.ps1` 输出）。

## 运行参数

```text
（无参数）        启动本地界面
--launch          直接启动基座，不打开界面
--no-browser      不自动打开浏览器
--port <n>        界面起始端口（默认 17823）
--runtime <dir>   指定运行时目录（测试/多实例）
--print-plan      打印安装计划，不下载
--selftest        运行内建自检
```

## 安装配置（profile）

| profile | Git | PySide6 Addons | 首次下载 | 适用 |
| --- | --- | --- | --- | --- |
| `standard`（默认） | 是 | 否（Essentials） | 约 176 MB | 常规使用；可切换 tag/main；QtCharts 组件降级 |
| `full` | 是 | 是 | 约 333 MB | 需要 QtCharts / 完整 PySide6 |

`standard` 通过 `uv sync --no-install-package pyside6-addons` 跳过 157 MB 的 Addons；
基座 `chart.py` 已对 QtCharts 缺失做占位降级。若后续基座把依赖改为 `pyside6-essentials`，这一跳过仍可保留。

首次运行仍需要 Git（约 38 MB MinGit），因为源码通过 Git clone 并校验 commit SHA；
Gitee 的 tag archive 对非 curl UA 返回 HTML 反爬页，且 zip 字节哈希会随重新打包变化，因此不再作为安装路径。

## 默认下载源

`mirror` 默认 `cn`；国内源优先，失败时自动回退：

| 内容 | 首选 | 回退 |
| --- | --- | --- |
| PyPI 依赖 | 清华 `pypi.tuna.tsinghua.edu.cn` | `pypi.org` |
| uv | `gh-proxy.com` | `github.com` |
| CPython | `gh-proxy.com` | 官方 python-build-standalone |
| MinGit | `registry.npmmirror.com` | `gh-proxy.com` → `github.com` |
| 基座源码 | Gitee | 无（Gitee 是唯一源码源） |

所有回退下载仍会校验固定 SHA-256；`mirror=global` 仅用于海外网络或排查国内源故障。

## 日志与图标

- 实时日志是固定高度滚动区域：桌面用 flex 填充剩余空间，窄屏/矮屏固定 260–300px；追加日志不会把页面撑高。
- 日志更新不再自动滚动或抢占焦点；需要查看最新内容时点击右上角“最新”按钮。
- exe 图标与 `/favicon.ico` 使用根目录 `icon.ico`；界面左上角品牌图标使用 `mihoutao.svg`，均作为内嵌资源提供。

## 运行时布局

```
%USERPROFILE%\.SllkGui/             （即 C:\Users\<用户>\.SllkGui，运行时根目录）
├─ config.json                 schemaVersion 2
├─ current.json                当前环境记录
├─ previous.json               上一环境（回滚用）
├─ envs/<id>/base              Git 源码
├─ envs/<id>/base/.venv        uv venv
├─ envs/<id>/meta.json         环境元数据
├─ tools/uv/uv.exe             固定版本 uv
├─ tools/python/...            uv managed CPython
├─ tools/git/...               MinGit（仅 PATH 无 Git 时）
├─ data/                       基座共享数据（--data-dir；跨环境保留）
├─ logs/                       launcher.log + app.out/err.log
├─ cache/                      下载包；cache/uv 为 uv 缓存
└─ port.json                   界面端口 + PID
```

`data/` 跨环境共享，升级/回滚不会动用户设置和插件。

## 配置 schema v2

```json
{
  "schemaVersion": 2,
  "mirror": "cn",
  "repo": "https://gitee.com/shilianlvke/SllkGui.git",
  "branch": "main",
  "python": "3.12.16",
  "mode": "run",
  "profile": "standard",
  "autoLaunch": false,
  "closeWithPage": true,
  "safeMode": false,
  "noPluginDeps": false
}
```

本版本只接受 `schemaVersion=2`；旧配置会被直接丢弃并重建默认值，不做迁移。
`repo` 仅允许 `https://gitee.com/...` 或 `https://github.com/...`；`branch`、`python` 均有格式校验。

## HTTP API

所有 `/api/*` 需要 `X-Token`（页面内注入）。仅绑定 `127.0.0.1`，校验 Host/Origin，响应带 CSP、X-Frame-Options、nosniff。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 内嵌 SPA（注入 token/nonce） |
| GET | `/api/state` | 环境、步骤、版本、健康、下载、cleanup 状态 |
| GET | `/api/log?cursor=` | 启动器日志增量 |
| GET | `/api/versions?refresh=1` | main + base-* tag（Git 模式） |
| GET/POST | `/api/config` | 读取/保存 mirror、mode、profile、autoLaunch、closeWithPage |
| POST | `/api/mode` | 切换 run/gallery（运行中禁止） |
| POST | `/api/setup` | 开始初始化；body `{profile, mirror}` |
| POST | `/api/setup/stop` | 取消初始化 |
| POST | `/api/launch` | 启动基座并做 6 秒健康检查 |
| POST | `/api/stop` | 关闭基座进程树 |
| POST | `/api/update` | 构建新环境并切换；body `{ref}` |
| POST | `/api/sync` | 兼容旧 UI，等价于更新到 main（非破坏式） |
| POST | `/api/repair` | 按当前配置重建环境 |
| POST | `/api/rollback` | 切回 previous 环境 |
| POST | `/api/cleanup` | 删除非 current/previous 环境与 cache 根下载包 |
| GET | `/api/dirty` | 当前源码 git status（Git 模式） |
| GET | `/api/health` | 健康检查 |
| GET | `/api/diagnostics` | 诊断 JSON（配置、环境、日志、版本） |
| GET | `/api/applog` | 基座日志尾部 |
| POST | `/api/exit` | 退出启动器（不动基座） |
| POST | `/api/bye` | 页面关闭通知（closeWithPage） |

## 安全边界

- 不写 `%LOCALAPPDATA%\...\launcher.ps1`，不调用 `powershell -ExecutionPolicy Bypass`；无脚本落地。
- uv（0.13.9）与 MinGit（2.56.1）固定版本 + SHA-256；CPython 由 uv 校验下载。
- 源码使用 `git clone --depth 1`，并校验 `git rev-parse HEAD` 与 `ls-remote` 的 commit SHA 一致。
- 本地 API：token（32 hex）、Host/Origin 校验、CSP `script-src 'nonce-...'`、`frame-ancestors 'none'`、1 MB body 上限。
- `config.json` 的 repo 限制在 Gitee/GitHub HTTPS；branch/python 做格式校验。
- 未做代码签名前，SmartScreen/AV 仍可能提示；这是发布流程剩余项，不是代码缺陷。

## 兼容性

- Windows 10 1809+ / Windows 11；.NET Framework 4.8（系统自带）。
- AnyCPU：x64 原生；ARM64 使用 `uv-aarch64-pc-windows-msvc`，MinGit 为 x64（随系统模拟运行）。
- 不再依赖 Windows PowerShell 5.1，因此不受 ExecutionPolicy / Constrained Language Mode 影响。
- PySide6 6.10 / Qt 6 的 Windows 下限以 Qt 官方支持列表为准。

## 不兼容旧版

本版本主动放弃旧版兼容，升级后需要重新初始化：

- 旧 `config.json`（无 `schemaVersion` 或版本不是 2）会被直接丢弃并重建默认配置，不迁移旧值。
- `runtime\base`、`base-ref.json` 不再扫描；旧环境不会被接管。
- `port.txt` 与旧 root-key 互斥量不再兼容；只使用 `runtime\port.json` 与 runtime-key 互斥量。
- 旧 `SllkGuiLauncher.bat` / `build_exe.py` 已移除，只使用 `SllkGuiLauncher.exe`。
- 如需保留旧数据，请在升级前自行备份；启动器本身不提供迁移。

## 已知限制 / 后续项

- 未签名：需要 Authenticode 证书 + SmartScreen 信誉。
- MinGit 下载路径已在 PATH 无 Git 的干净 runtime 中验证（2.56.1，SHA-256 校验通过）；ARM64 仍建议在 VM 复测。
- ARM64 未实机验证；MinGit 走 x64 模拟。
- `standard` 跳过 Addons 是启动器侧行为；建议基座仓库把依赖改为 `pyside6-essentials`，让 `uv sync`/PyPI 安装天然一致。
- cleanup 为同步执行；旧环境很大时可能耗时，但只删除非 current/previous 环境，且保留 uv 缓存。

---

## 验证入口

Launcher 自身与「Launcher + 基座」联调目前都**未纳入基座 CI**（基座 CI 只覆盖非 Windows 降级路径），以下两个入口均为本地人工验证。

### Launcher 自身本地验证（`Launcher/verify.ps1`）

在 `Launcher/` 目录执行：

```powershell
.\verify.ps1
```

脚本包含：重新构建并核对 exe 大小 / FileVersion / ProductName；`--selftest`（旧配置丢弃、旧 runtime 不接管、HTTP 200/403/404/413、Host/Origin、CSP、小 POST body 同包、token）；`--print-plan`（固定版本、SHA-256、profile 下载估算）；以及 Authenticode 签名状态检查（可用 `-RequireSignature` 强制要求，无证书时为未签名构建）。此验证为本地入口，**未进入基座 CI**。

### 与基座联调的手动验证步骤

1. 用 manifest 指向的 tag 构建环境：`Launcher/manifest.json` 的 `base.tag` 当前为 `base-v4.4.0`（`defaultBranch` 为 `main`）。在 Launcher 管理界面执行初始化 / 更新，使 `current.json` 指向该 tag 构建出的 `envs/<id>`；或在仓库根目录用 `uv run sllkgui run --data-dir data/` 复现同一基座行为。
2. 启动后确认基座进程与命令：`sllkgui.exe --data-dir data/` 正常启动、健康检查通过（`POST /api/launch` 6 秒健康检查），`data/` 跨环境保留用户设置和插件。
3. 日志实时输出：管理界面“实时日志”区域随基座启动持续追加 `logs/app.out.log`、`logs/app.err.log` 与 `launcher.log`，点击“最新”可到达尾部；追加日志不把页面撑高。
4. 更新 / 回滚 / 清理路径可用：`POST /api/update` 在 `envs/<new-id>` 构建新环境并切 `current.json`；失败可 `POST /api/rollback` 切回 `previous.json`；`POST /api/cleanup` 删除非 current/previous 旧环境与 cache 根下载包且保留 uv 缓存。逐项在界面执行并确认状态与 `/api/state` 一致。

上述联调同样**未进入基座 CI**，需在真实 Windows 上人工执行并留存结果。
