# 插件协议（SllkGUI 2.0）

一个 Git 仓库 = 一个插件，插件通过 **Surface** 向 Gallery 贡献页面。插件代码运行在
Gallery 进程内，清单里的权限用于安装前知情同意，不是沙箱。

## 1. 仓库结构

```text
sllkgui-notes/
├── sllkgui-plugin.yml      # 必需：运行时清单
├── plugin.py               # 必需：导出 PLUGIN 实例
├── pages/                  # 可选：页面实现
├── resource/
│   ├── icon/*.svg
│   └── lang/{zh_cn,zh_tw,en_us,ja_jp}.yml
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## 2. 清单 `sllkgui-plugin.yml`

```yaml
schema: 1
api: 1
id: com.example.notes
name: Notes
version: 1.2.0
description: 通用便签
license: MIT
entry: plugin.py
requires:
  sllkgui: ">=2.0.0,<3.0.0"
  python: ">=3.12"
python_dependencies:
  - psutil>=6
  - pyyaml>=6.0.3
surfaces:
  - id: notes
    title: {zh_cn: 便签, zh_tw: 便籤, en_us: Notes, ja_jp: ノート}
    icon: resource/icon/notes.svg
    default: true
    order: 10
permissions:
  - filesystem.write
```

- `id`：`^[a-z0-9][a-z0-9._-]{0,63}$`，全局唯一。
- `version`：SemVer。
- `surfaces`：至少一个；`default: true` 最多一个；`order` 越小越靠前。
- `permissions`：`network`、`filesystem.read`、`filesystem.write`、`subprocess`、
  `clipboard`、`notifications`、`tray`、`autostart`、`system.info`。
- `python_dependencies`（可选）：第三方 Python 包声明（PEP 508 格式，如
  `psutil>=6`）。基座在导入插件**之前**检查；缺失时弹窗让用户选择自动安装
  （`uv pip install` 到当前解释器）或手动安装，安装失败则隔离该插件并记录
  `PYTHON_DEPENDENCY_MISSING`。镜像源见 `sllkgui run --index-url` /
  `SLLKGUI_PIP_INDEX_URL` / `sllkgui.configure(pip_index_url=...)`。
  能用标准库、纯 Python 小库或 `vendor/` 内联解决的，优先不声明。

## 3. 入口 `plugin.py`

```python
from sllkgui.plugin import GalleryContext, Plugin


def build_notes(ctx: GalleryContext):
    from .pages.list import NotesPage

    with ctx.timing("notes.surface.build"):
        page = NotesPage(ctx)
    ctx.event("surface.ready", {"surface": "notes"})
    return page


class NotesPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading notes")
        with ctx.timing("notes.load"):
            self.data_file = ctx.data_dir / "notes.yaml"
        ctx.event("notes.loaded")

    def surfaces(self):
        return {"notes": build_notes}

    def on_locale_changed(self, locale: str) -> None:
        self.ctx.log(f"locale -> {locale}")

    def on_unload(self) -> None:
        self.ctx.log("unloading notes")
        self.ctx.event("notes.unloaded")


PLUGIN = NotesPlugin()
```

规则：

- 必须导出模块级 `PLUGIN` **实例**；不接受 `PAGE`、`register_plugins` 等旧形式。
- `surfaces()` 返回 `{surface_id: factory}`，factory 签名 `(GalleryContext) -> QWidget`。
- 清单 `surfaces[].id` 与 factory 键一一对应；缺失会报 `PLUGIN_SURFACE_FACTORY_MISSING`。
- 生命周期：`on_load` → `surfaces()` →（语言切换）`on_locale_changed` → `on_unload`。

## 4. `GalleryContext`

| 成员 | 说明 |
| --- | --- |
| `plugin_id` / `plugin_version` | 插件元数据 |
| `data_dir` / `cache_dir` | 可写目录，自动创建 |
| `locale` / `theme` | 当前语言 / 主题名 |
| `permissions` | 清单声明的权限 |
| `resource(*parts)` | `resource/` 内只读路径 |
| `open_surface(id)` | 跳转到本插件 Surface |
| `text(key, default=None, **kwargs)` | 多语言文案，缺失回退 `en_us` |
| `log(message, level="info")` | 基座日志，自动加插件前缀 |
| `logger` | 标准库 `logging.Logger`，已桥接基座 |
| `event(name, payload=None, level="info")` | 基座遥测 |
| `timing(name, payload=None)` | 上下文计时，自动记录 `duration_ms` |
| `report_error(code, message, detail=None)` | 日志 + 遥测 + 非阻塞错误提示 |
| `parent_window()` | Gallery 主窗口（对话框父级） |
| `tray` | 基座托盘（需 `tray` 权限，见 `docs/TRAY.md`） |

## 5. 多语言

`resource/lang/<locale>.yml` 支持嵌套字典；四个语言文件必须齐全且键集合一致。
`ctx.text("home.title")` 读取当前语言；切换语言后 Loader 会调用
`on_locale_changed`，页面可自行刷新文案。

## 6. 本地开发

```powershell
# 直接加载本地插件目录，不写 registry
uv run sllkgui run --plugin-dir ..\my-plugin

# 规范检查
uv run sllkgui plugin lint ..\my-plugin

# 运行仓库内最小示例
uv run sllkgui run --plugin-dir examples\plugin-hello
```

## 7. 发布

1. 打 SemVer tag（如 `v1.2.0`）。
2. 在官方源提交 `plugins/<id>/entry.yaml`（见 `docs/SOURCE.md`）。
3. 用户执行 `sllkgui source refresh` 后即可搜索安装。
