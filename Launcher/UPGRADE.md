# SllkGui Launcher 升级说明（4.x → 5.0）

本次升级把启动器从“PowerShell 脚本 + 固定资源槽补丁”改为“C# .NET Framework 4.8 原生外壳 + 内嵌 SPA”。
核心业务目标保持不变：一个 exe、零安装、按需准备运行时、可切换基座版本、可回滚。

## 主要改动

| 领域 | 旧实现 | 5.0 |
| --- | --- | --- |
| 外壳 | 49 KB .NET 壳，内嵌 raw Deflate PowerShell，写 `%LOCALAPPDATA%\...\launcher.ps1` | 约 263 KiB C# WinExe，UI/manifest/icon 作为 .NET 资源，无脚本落地 |
| 打包 | `build_exe.py` 按 0x44C–0x6F8B 固定偏移打补丁，槽位 97.9% 满 | `build.ps1` 用 csc 从源码编译，动态资源；无固定偏移 |
| UI | 内嵌在 PowerShell here-string | `ui/index.html` 独立维护，build 时 GZip 嵌入 |
| HTTP | PowerShell 手写串行 accept，5 秒阻塞 | `TcpListener` + 每连接 Task；header/body 同包处理；Host/Origin/CSP |
| 安装管线 | PowerShell runspace，6 步 | C# Bootstrap，7 步（uv → CPython → Git → source → venv → deps → verify） |
| 依赖 | `uv sync` 默认安装 dev 组 + 157 MB Addons | `--no-dev`；`standard` 跳过 `pyside6-addons`，`full` 才安装 |
| 版本更新 | 在 `runtime\base` 原地 fetch/reset/clean，需 force 丢弃改动 | 每次构建 `envs/<id>` 新环境，成功后切换；当前环境永不被修改 |
| 回滚 | checkout 旧 SHA + 重新 sync | `previous.json` 指向完整旧环境，原子切回 |
| 单实例 | 按 `$Root` 取 MD5；runtime 回退时可能不一致 | 只按解析后的 runtime 路径取互斥量，不再兼容旧 root-key |
| 兼容性 | 依赖 Windows PowerShell 5.1 / GPO | 不依赖 PowerShell；.NET Framework 4.8 系统组件 |
| 体积 | 首次 332 MB，其中 Addons 157 MB + MinGit 38 MB | `standard` 约 176 MB（保留 MinGit/Git，跳过 Addons）；`full` 约 333 MB |
| 安全 | 无签名、无哈希、隐藏 PowerShell + Bypass | 无脚本；uv/MinGit 固定 SHA-256；源码校验 commit SHA；token + Host/Origin + nonce CSP |
| 发布信息 | 0.0.0.0，无签名、无版本描述 | 5.0.0.0，FileVersion/ProductName/CompanyName/图标；`build.ps1 -Sign` 可签名 |

## 破坏性变更

1. **入口变化**：`SllkGuiLauncher.bat` 已移除；只使用 `SllkGuiLauncher.exe`，不再提供脚本入口。
2. **构建方式变化**：`build_exe.py` 已移除；发布使用 `build.ps1` 从源码编译。
3. **运行时不写 PowerShell**：不再生成 `launcher.ps1`，也不再调用 `-ExecutionPolicy Bypass`。依赖此行为的脚本/快捷方式需要调整。
4. **配置不兼容**：只接受 `schemaVersion=2`。旧 `config.json`（无版本号或版本不是 2）会被直接丢弃并重建默认值，不迁移旧键。
5. **运行时不兼容**：新环境在 `runtime\envs\<id>\base`，当前/上一环境由 `current.json` / `previous.json` 指向；旧 `runtime\base` / `base-ref.json` 不再扫描，不会被接管。
6. **更新语义**：`/api/update`、`/api/sync` 不再原地修改当前源码；`force` 参数被忽略，本地改动不会被丢弃。需要干净环境时使用“修复 / 重建环境”或回滚。
7. **profile 变化**：不再提供“无 Git 的源码 zip 极速模式”。Gitee tag archive 对非 curl UA 返回反爬 HTML，且 zip 字节哈希不稳定；5.0 统一使用 Git clone + commit SHA 校验。可选配置为 `standard`（Essentials）与 `full`（Addons）。
8. **API 行为**：`/api/cleanup` 只删除非 current/previous 环境与 cache 根下载包；`/api/rollback`、`/api/repair`、`/api/stop`、`/api/diagnostics` 为新增；`/api/state` 增加 `env/health/download/cleanup/launcher/capabilities` 字段。
9. **单实例**：只按解析后的 runtime 路径取互斥量；不再兼容旧 root-key，也不再读写 `port.txt`。
10. **界面资源**：exe/favicon 使用 `icon.ico`，品牌图标使用 `mihoutao.svg`；实时日志为固定滚动区，不再自动跟随。

## 不兼容影响

- 旧配置、旧 `runtime\base`、旧 `.bat`、旧 `port.txt` 均不再识别；升级后需要重新初始化。
- 需要保留旧数据时，请在升级前自行备份；启动器不提供迁移。
- `runtime\data` 仍是当前的共享数据目录；新环境创建后可以继续使用其中的用户设置与插件。

## 需要同步处理的事项

1. **基座仓库（推荐）**：把 `pyproject.toml` 的 `pyside6` 元包改为 `pyside6-essentials`，QtCharts 继续走 `chart.py` 的缺失降级。这样 `uv sync`/PyPI 安装天然不拉 157 MB Addons；启动器的 `--no-install-package` 作为双保险。
2. **代码签名**：准备 Authenticode 证书，使用 `build.ps1 -Sign -CertPath ...`；发布页提供 SHA-256；提交 SmartScreen 信誉。当前产物为 `NotSigned`。
3. **CI**：把 `verify.ps1` 加入发布流水线；在干净 Windows VM 上跑一次首次安装并保存日志。
4. **镜像**：默认 `mirror=cn`；MinGit 依次尝试 npmmirror → gh-proxy → GitHub，uv/Python 走 gh-proxy，PyPI 走清华，失败再回退官方源；回退下载仍校验 SHA-256。
5. **ARM64**：uv 使用 aarch64 资产；MinGit 仍为 x64（随系统模拟）。如需原生 Git，需要替换 MinGit 资产并补充哈希。
6. **本地改动策略**：产品语义已改为“更新不碰当前环境”，因此 UI 中“强制同步/丢弃改动”的文案已移除；如有外部脚本依赖 `force=true`，需要同步调整。
7. **旧版清理**：确认发布物不再包含 `.bat`、`build_exe.py`、旧 `runtime` 或 `port.txt`。

## 验收结果

- `.\verify.ps1`：**VERIFY PASS**。
- 内建 selftest：19 项通过（旧配置被丢弃、旧 runtime 不接管、HTTP token/Host/Origin/CSP、413、404、小 POST body 同包等）。
- 实机标准安装：7/7 步完成，`env-...` 可用，PySide6 6.10.2 校验通过。
- 实机启动基座：`/api/launch` 返回 PID，状态 `running`，健康 `ok`；`/api/stop` 正常关闭。
- 修复 / 回滚 / 清理：新环境构建、previous 切换、cache 根下载包清理均验证通过。
- 单实例：第二实例退出码 0，复用第一实例端口；`/api/exit` 正常退出启动器。
- 已覆盖：在 PATH 无 Git 的干净 runtime 中完成 uv → CPython → MinGit 2.56.1 → git clone → venv → sync → verify，7/7 通过。
- 未覆盖：ARM64、干净 VM 的完整首次耗时、代码签名。
