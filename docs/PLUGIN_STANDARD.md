# 插件开发规范（强制）

本规范适用于所有提交到官方源的插件。`sllkgui plugin lint` 与源仓库 CI 会逐项检查；
不合规的插件不能合并。

## 1. 日志

- 唯一入口：`ctx.log()` / `ctx.logger`。
- 禁止：`print()`、`logging.basicConfig()`、`FileHandler`、自建日志文件。
- 必须记录：`on_load` / `on_unload`、Surface 创建失败、后台任务开始/结束/失败、
  外部 IO/网络失败、数据迁移或损坏、权限拒绝。
- 禁止记录密码、token、用户正文、完整本地路径；高频错误限频或聚合。

## 2. 遥测

- 唯一入口：`ctx.event()` / `ctx.timing()`。
- 事件名使用 `<domain>.<action>`（如 `notes.created`），禁止 `test` / `event1`。
- 必须记录用户可见动作、后台任务状态、数据迁移、权限拒绝、外部服务失败。
- payload 仅允许 JSON 标量/列表/浅层字典；单事件 ≤ 2 KiB；禁止隐私数据。
- 基座自动记录 `plugin.loaded` / `plugin.unloaded` / `plugin.error`，插件不要重复。

## 3. 错误处理

- 插件边界捕获异常并 `ctx.report_error(code, message, detail)`；禁止静默 `except: pass`。
- 禁止 `sys.exit`、覆盖 `sys.excepthook`、阻塞 Gallery 主循环。
- 错误码使用插件命名空间：`NOTES_IO_FAILED`、`NOTES_PARSE_FAILED`。

## 4. 生命周期与线程

- `on_load` 阻塞不超过 50ms；重活放到 Surface `showEvent` 或后台任务。
- `QTimer` / `QThread` / `QObject` 必须在 `on_unload` 中停止并 `deleteLater()`。
- `on_unload` 必须幂等；卸载后不得回调已销毁控件。

## 5. 数据与资源

- 只写 `ctx.data_dir` / `ctx.cache_dir`；禁止写安装目录、`resource/` 或系统目录。
- 写入必须原子化（临时文件 + `replace`），并带 schema 版本与迁移。
- 资源通过 `ctx.resource()` 访问；图标使用 SVG。
- 卸载默认保留 `data_dir`；`--purge` 才删除，README 必须说明。

## 6. UI、主题与语言

- 使用 `sllkgui.guicore` 组件与设计令牌；禁止硬编码颜色/字号/圆角。
- Surface 返回 `QWidget`；禁止创建 `QApplication` / `QMainWindow`。
- 所有用户可见文本走四语言资源；支持 DPI、键盘焦点与明暗主题。
- 禁止修改全局样式表、字体、语言；禁止 monkey-patch 基座模块。

## 7. 安全与权限

- 清单 `permissions` 必须覆盖实际能力使用。
- 禁止 `eval` / `exec` 远程内容、运行时下载代码、修改 `sys.path`、未声明子进程。
- 文件路径限制在 `data_dir` / `resource` 内。
- 网络请求必须设置超时与错误处理，禁止在 UI 线程同步网络。

## 8. 依赖与打包

- 只使用清单声明的依赖；跨插件不得直接 import 另一个插件的内部模块。
- 纯 Python 依赖放 `vendor/`；禁止运行时 `pip install`。
- 提供 `README.md`、`CHANGELOG.md`、`LICENSE`；不提交 `.venv`、`build/`、`dist/`。

## 9. 测试与文档

- 至少包含 smoke test：加载插件、构建每个 Surface、关键动作、错误路径。
- 测试必须离线可跑；外部服务使用 mock。
- README 必须包含功能、权限、数据位置、日志/遥测事件表、卸载说明、兼容范围。

## 10. 合规检查

```powershell
sllkgui plugin lint <插件目录> --json
sllkgui plugin verify <已安装插件 id>
```

- `entry.yaml` 的 `compliance: 1` 表示已通过本规范。
- 运行期若插件从未发出自定义事件，管理页会标记 `telemetry: missing` 警告。
