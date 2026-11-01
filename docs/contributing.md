# 贡献指南

## 环境

| 工具 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12+ | `requires-python = ">=3.12"` |
| PySide6 | 6.10+ | GUI 依赖 |
| uv | 最新 | 依赖管理（`pyproject.toml` 已配清华镜像） |

```powershell
uv sync --extra dev
uv run pytest          # 期望 270 passed, 5 skipped
uv run ruff check src tests
```

提交前这两条必须都是绿的。

---

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

`docs/PYCL2_BASE_SYNC.md` 是上一轮同步的实际记录，可作参照。
提 PR 时请自查这一条。

---

## 分层规则

| 层 | 包 | 可以做 | 不可以做 |
| --- | --- | --- | --- |
| 逻辑层 | `customgui.appcore` | 配置、主题、语言、令牌、插件协议、错误边界、工具 | 不得 import `guicore` / `guis` |
| 组件层 | `customgui.guicore` | 组件实现、窗口部件、QSS 生成 | 不得 import `guis` |
| 装配层 | `customgui.guis` | 主窗口组装、页面栈、插件加载、语言服务 | 只能使用 `appcore` 公开面（禁止 `appcore.sysx.*`） |
| 门面 | `customgui.window` | 把装配层的能力收成稳定 API | 不写业务逻辑 |

这些不是口头约定，`tests/test_architecture_boundaries.py` 用 AST 扫 import 根逐条守着。
新增层级依赖前先想清楚，改断言要单独说明理由。

---

## 代码约定

- **包名/模块名全小写**，单词间用下划线。历史的 `SYS` / `CustomUI` 这类命名已在 0.3.0 清除，
  不要再引入。Linux 文件系统大小写敏感，这条不是洁癖。
- **不要用 `Path(__file__).resolve().parents[N]` 定位资源**。源码运行、wheel 安装、
  PyInstaller 收集三种形态的目录深度不同，这是最隐蔽的「装完就崩」来源。
  一律走 `customgui.config.paths` 的 `find_resource()` / `resolve_path()` / `iter_files()`。
- **不要依赖当前工作目录**。运行时不得调用 `os.getcwd()`。
- **新公开能力先进门面**：宿主该用的东西放 `customgui.window` 或 `customgui.appcore`，
  别让消费方去 import 内部子模块。
- 相对导入：同包用 `.`，兄弟包用 `..`，**改层级后立刻 `python -c "import <包>"` 验证**。
  批量正则升降级是事故来源。

---

## 测试

- 全部在 `QT_QPA_PLATFORM=offscreen` 下跑（`tests/conftest.py` 已设）。
- src layout 下测试导入的是**已安装的** `customgui`，不要往 `sys.path` 塞源码目录——
  否则测的是源码树，而不是 wheel 里的东西，「装完能不能用」这类问题永远测不出来。
- 修 bug 请带一条能复现的测试；这个仓库历史上已经出现过两次「断言扫空目录、
  永远通过」的假绿测试，写扫描类断言时务必加「扫到了东西」的自检。

---

## 提交

- 一次提交做一件事。重构与功能分开，格式化与逻辑分开。
- 提交信息说明**为什么**，不只是**改了什么**。
- 破坏性变更必须同步更新 `CHANGELOG.md` 的「迁移指南」。
- 版本号只在 `src/customgui/_version.py` 一处改，git tag 与之保持一致（`v0.3.0` / `base-v0.3.0`）。

---

## 发版

```powershell
# 1. 改版本号（唯一一处）
#    src/customgui/_version.py  ->  __version__ = "0.3.0"

# 2. 构建与校验
uv run python -m build --wheel
uv run twine check dist/*.whl

# 3. 干净环境冒烟（务必做，别只看本机）
uv venv /tmp/smoke --python 3.12
uv pip install --python /tmp/smoke/bin/python dist/customgui-0.3.0-py3-none-any.whl
/tmp/smoke/bin/customgui doctor

# 4. 打 tag 并推送
git tag base-v0.3.0
git push origin main --tags
```

第 3 步是唯一能验证「开箱即用」的环节。`customgui doctor` 里任一 `✗` 都不要发。
