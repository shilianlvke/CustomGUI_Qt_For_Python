# 贡献指南

## 环境

| 工具 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12 | `requires-python = ">=3.12"`，`.python-version` 固定 3.12 |
| PySide6 | 6.10+ | GUI 依赖 |
| uv | 最新 | 依赖管理（`pyproject.toml` 已配清华镜像） |

```powershell
uv sync --extra dev
uv run ruff check src tests apps examples scripts
uv run mypy
uv run pytest --cov=sllkgui --cov-report=term-missing --cov-fail-under=70
```

三条命令都必须干净：`ruff check` 零告警，`mypy` 零错误，`pytest` 零失败、覆盖率不低于
70%、skip 只允许平台相关的用例。测试数量随代码变化，以实际输出为准，不要写进文档。

本地命令只便于自查，CI 的判定标准以 `.workflow/*.yml` 里的实际命令为准：向 `main` 提 PR
（以及推送 `main`）会触发 `.workflow/QualityGate.yml`；打 `base-v*` tag 触发
`.workflow/ReleasePipeline.yml`，发布侧复跑同一套门禁后才打包。两处命令若有调整，以文件为准同步本地。

窗口类测试统一走 `QT_QPA_PLATFORM=offscreen`（`tests/conftest.py` 已设置），
本地与无头容器都不需要真实显示。`ruff` 的规则集在 `pyproject.toml` 的
`[tool.ruff.lint]`（`E/F/W/I/UP/B`，忽略 `E501`、`TID252`），新增规则要同步更新该处，
不要只在命令行加 `--select`。

## 硬规则：许可证边界

基座是**木兰宽松许可证 v2**（MulanPSL-2.0，宽松、可商用、可闭源分发）。

下游有个真实项目 **py-cl2**，它是 **GPL-3.0**。

> **宽松许可的库可以被 GPL 项目依赖——这个方向安全。**
> **反过来不安全。**

所以：

- ❌ **禁止**把 py-cl2（或任何 GPL 项目）的业务代码搬进本仓库——主题色板、品牌文案、
  业务页面、图标、LauncherCore 之类。一旦搬进来，整个仓库就成为 GPL 衍生物，
  从此失去「宽松许可、可商用」这个核心卖点。
- ✅ **允许**回流通用能力：懒加载、信号路由修复、主题强调色机制、错误边界……
  判据是「这段代码离开 py-cl2 的业务语境后还有意义吗」。

提 PR 时请自查这一条。

## 分层规则

| 层 | 包 | 可以做 | 不可以做 |
| --- | --- | --- | --- |
| 逻辑层 | `sllkgui.appcore` | 配置、主题、语言、令牌、插件协议、错误边界、工具 | 不得 import `guicore` / `guis` |
| 组件层 | `sllkgui.guicore` | 组件实现、窗口部件、QSS 生成 | 不得 import `guis` |
| 装配层 | `sllkgui.guis` | 主窗口组装、页面栈、插件加载、语言服务 | 只能使用 `appcore` 公开面（禁止 `appcore.sysx.*`） |
| 门面 | `sllkgui.window` | 把装配层的能力收成稳定 API | 不写业务逻辑 |

这些不是口头约定，`tests/test_architecture_boundaries.py` 用 AST 扫 import 根逐条守着。
新增层级依赖前先想清楚，改断言要单独说明理由。

## 代码约定

- **包名/模块名全小写**，单词间用下划线。历史的 `SYS` / `CustomUI` 命名已清除，不要再引入
  （现存 `appcore/tool/Net.py` 属于待改的历史命名）。Linux 文件系统大小写敏感，这条不是洁癖。
- **不要用 `Path(__file__).resolve().parents[N]` 定位资源**。源码运行、wheel 安装、
  PyInstaller 收集三种形态的目录深度不同，这是最隐蔽的「装完就崩」来源。
  一律走 `sllkgui.appcore.sysx.config.paths` 的 `find_resource()` / `resolve_path()` / `iter_files()`。
- **不要依赖当前工作目录**。运行时不得调用 `os.getcwd()`。
- **新公开能力先进门面**：宿主该用的东西放 `sllkgui.window` 或 `sllkgui.appcore`，
  别让消费方去 import 内部子模块。
- **组件不缓存主题色**：自绘组件在 `paintEvent` 中读令牌，`__init__` 里存色值会导致主题热切换混色。
- 相对导入：同包用 `.`，兄弟包用 `..`，**改层级后立刻 `python -c "import <包>"` 验证**。
  批量正则升降级是事故来源。

## 测试

- 全部在 `QT_QPA_PLATFORM=offscreen` 下跑（`tests/conftest.py` 已设）。
- src layout 下测试导入的是**已安装的** `sllkgui`，不要往 `sys.path` 塞源码目录——
  否则测的是源码树，而不是 wheel 里的东西，「装完能不能用」这类问题永远测不出来。
- 修 bug 请带一条能复现的测试；扫描类断言必须加「扫到了东西」的自检，
  本仓库历史上出现过「扫空目录、永远通过」的假绿测试。
- 已知遗留：`tests/test_example_paradigm.py` 整文件 skip 且指向已删除的 `Apps_legacy`，
  修改示例协议时顺手清理或重写它。

## 文档

- `docs/` 是唯一文档来源，**手工维护**；不再使用 `scripts/generate_docs.py` 生成 API 列表
  （AST 列表看不到 `__init__` 的再导出，且行号一改就过期）。
- 协议与清单字段只写在 `docs/PLUGIN.md`，组件签名只写在 `docs/COMPONENTS.md`，
  README 只做摘要并链接，避免同一事实多处维护。
- 不写过程记录与待办清单：变更归 `CHANGELOG.md`，现状归 `docs/ARCHITECTURE.md`。
- 文档中的命令、路径、版本号、组件数量必须与代码一致；改代码时一起改。

## 提交

- 一次提交做一件事。重构与功能分开，格式化与逻辑分开。
- 提交信息说明**为什么**，不只是**改了什么**；沿用 `type(scope): 中文描述` 风格。
- 破坏性变更必须同步更新 `CHANGELOG.md` 的「破坏性变更」。
- 版本号只在 `src/sllkgui/_version.py` 一处改，git tag 命名统一为 `base-vX.Y.Z`（如 `base-v1.0.1`）并与之保持一致。

## 发版

改动基座代码后必须补一次补丁发布（`base-vX.Y.Z`），下游 py-rm 固定依赖 tag 而不是分支。

一键发布（bump patch → 质量门禁 → 提交 → tag → 推送）：

```powershell
uv run python scripts/release_base.py --dry-run             # 预览
uv run python scripts/release_base.py --message "fix: ..."   # 正式发布
```

手工发布：

```powershell
# 1. 改版本号（唯一一处）
#    src/sllkgui/_version.py  ->  __version__ = "1.0.0"

# 2. 构建与校验
uv run python -m build --wheel
uv run twine check dist/*.whl

# 3. 干净环境冒烟（务必做，别只看本机）
uv venv /tmp/smoke --python 3.12
uv pip install --python /tmp/smoke/bin/python dist/sllkgui-1.0.0-py3-none-any.whl
/tmp/smoke/bin/sllkgui doctor
# doctor 默认不执行插件代码；需要验证加载时改跑：/tmp/smoke/bin/sllkgui doctor --load

# 4. 打 tag 并推送
git tag base-v1.0.1
git push origin main --tags
```

第 3 步是唯一能验证「开箱即用」的环节。`sllkgui doctor` 里任一 `✗` 都不要发；它默认不执行插件代码，需要验证加载时加 `--load`。
1.x 暂不发 PyPI，只走 wheel + tag。

`base-v*` 触发发布流水线；历史 `v*` tag 不再触发，保留但不使用。
