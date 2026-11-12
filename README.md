# SllkGUI · PySide6

基于 **PySide6** 的桌面 UI 基座：窗口骨架、设计令牌、组件库、主题与语言、Gallery 插件运行时。

<p align="center">
  <a href="https://gitee.com/shilianlvke/SllkGui">Gitee</a> ·
  <a href="docs/README.md">文档</a> ·
  <a href="docs/ARCHITECTURE.md">架构</a> ·
  <a href="docs/PLUGIN.md">插件协议</a> ·
  <a href="docs/SOURCE.md">源仓库</a> ·
  <a href="CHANGELOG.md">更新日志</a>
</p>

> **版本 2.0.2**（tag `base-v2.0.2`）
>
> 2.0 是破坏性重构：旧的 App 协议 v1/v2、`apps/`、`config.yml`、`plugins.yml`
> 全部删除，不提供兼容层。插件改为「一个 Git 仓库 = 一个插件，多个 Surface」，
> 通过官方源或自建源发现、安装与更新。

## 两个命令

| 命令 | 用途 | 插件来源 |
| --- | --- | --- |
| `sllkgui gallery` | 组件预览、设计走查、离线演示 | 仅内置 `showcase/core_preview`，不加载外部插件 |
| `sllkgui run` | 日常使用、运行插件应用 | 核心插件 + 已安装插件 + `--plugin-dir` |

```powershell
uv run sllkgui gallery
uv run sllkgui run
uv run sllkgui run --safe-mode          # 只加载核心插件
uv run sllkgui run --plugin-dir ..\my-plugin
```

## 安装

```powershell
uv add "sllkgui @ git+https://gitee.com/shilianlvke/SllkGui.git@base-v2.0.2"
```

从源码运行：

```powershell
git clone https://gitee.com/shilianlvke/SllkGui.git
cd SllkGui
uv sync --extra dev
uv run sllkgui gallery
```

运行时依赖：Python 3.12+、PySide6 6.10+、PyYAML、packaging。

## 插件

```powershell
uv run sllkgui source add https://gitee.com/shilianlvke/sllkgui-source.git --yes
uv run sllkgui source refresh official
uv run sllkgui plugin search
uv run sllkgui plugin install com.shilianlvke.pyrm --yes
uv run sllkgui plugin list --json
uv run sllkgui plugin lint ..\my-plugin
```

插件仓库最小结构：

```text
my-plugin/
├── sllkgui-plugin.yml
├── plugin.py                 # 导出 PLUGIN 实例
├── resource/icon/*.svg
└── resource/lang/{zh_cn,zh_tw,en_us,ja_jp}.yml
```

```python
from sllkgui.plugin import GalleryContext, Plugin


def build_home(ctx: GalleryContext):
    from PySide6.QtWidgets import QLabel
    return QLabel(ctx.text("home.title", "Hello"))


class MyPlugin(Plugin):
    def on_load(self, ctx: GalleryContext) -> None:
        self.ctx = ctx
        ctx.log("loading")
        ctx.event("plugin.ready")

    def surfaces(self):
        return {"home": build_home}

    def on_unload(self) -> None:
        self.ctx.log("unloading")


PLUGIN = MyPlugin()
```

完整协议见 [docs/PLUGIN.md](docs/PLUGIN.md)，强制规范见
[docs/PLUGIN_STANDARD.md](docs/PLUGIN_STANDARD.md)。

## 命令总览

```text
sllkgui gallery [--surface ROUTE] [--data-dir DIR]
sllkgui run [--surface ROUTE] [--data-dir DIR] [--gallery-dir DIR]
            [--plugin-dir DIR]... [--safe-mode] [--allow-local]
sllkgui source list|add|remove|refresh|info
sllkgui plugin search|info|install|list|update|rollback|remove
                enable|disable|verify|lint|doctor
sllkgui doctor [--json]
sllkgui scaffold <dir> [--id ID] [--name NAME] [--source]
```

## 目录

```text
src/sllkgui/
├── appcore/          配置、主题、语言、日志、遥测
├── guicore/          组件库、设计令牌、窗口部件
├── gallery/          插件协议、源、存储、安装、加载、Gallery 外壳
├── showcase/         内置组件预览（gallery 模式）
├── core_plugins/     核心插件（run 模式）
├── plugin.py         插件作者公开 API
├── window.py         窗口/Gallery 门面
└── cli.py            gallery / run / plugin / source / doctor / scaffold
examples/
├── plugin-hello/     最小合规插件
└── source-template/  最小源仓库
```

## 数据目录

默认 `<data_root>/gallery/`：

```text
registry.json / sources.json
sources/     源仓库浅克隆
plugins/     已安装插件
history/     回滚版本
data/        插件 ctx.data_dir
cache/       插件缓存
staging/     安装临时目录
trash/       卸载回收站
```

`gallery` 模式不读取这些目录，也不联网。

## 开发与门禁

```powershell
uv sync --extra dev
uv run ruff check .
uv run mypy
uv run pytest --cov=sllkgui --cov-fail-under=70
```

## 相关项目

| 项目 | 说明 |
| --- | --- |
| [py-rm](https://gitee.com/shilianlvke/py-rm) | 基于 SllkGUI 2.0 Gallery 的桌面小部件运行时插件 |
| [sllkgui-source](https://gitee.com/shilianlvke/sllkgui-source) | 官方插件源（只存元信息） |

欢迎通过 issue/PR 提交插件与改进。
