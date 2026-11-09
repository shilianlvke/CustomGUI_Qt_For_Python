# 应用插件协议

SllkGUI 把「一个页面/一组页面」封装成目录：**放进 `apps/` 即被发现，删除目录即下线**。
本文件是清单字段、两套协议与装载行为的唯一说明。

## 0. 信任边界

加载器会对 `apps/<app>/app.py`（或 `gui/main.py`）执行 `exec_module`，插件代码与宿主
运行在同一进程、拥有相同权限。**这不是沙箱**：

- 只加载可信来源的插件；不要把不受信任的第三方目录放进 `apps/`，也不要让
  `SLLKGUI_APPS_DIR` 指向可被他人写入的位置。
- `sllkgui doctor` 默认只发现应用、不执行入口代码；只有加 `--load` 才会加载并执行插件。
- 插件在宿主进程内直接执行（见上文 `exec_module`），没有代码隔离；单个插件加载失败会被记录并跳过，不影响其他应用装载。
- 便携分发时建议在启动日志中打印实际生效的 `apps` 目录（`configure()` 会输出）。

## 1. 目录结构

```text
apps/<app_name>/
├── config.yml                     # 必需：清单
├── app.py                         # 可选：v2 插件入口（优先于 gui/main.py）
├── gui/
│   ├── main.py                    # v1/v2 入口，页面实现
│   └── style.py                   # 可选：应用私有样式
├── lib/                           # 可选：应用内共用代码
├── resource/
│   ├── icon/app_icon.svg          # 菜单图标
│   ├── lang/{zh_cn,zh_tw,en_us,ja_jp}.yml
│   ├── images/  voice/            # 其他资源
└── brand/
    └── sllkgui/                  # 可选：品牌覆盖层（themes / languages / settings / images）
```

`app_name`、`resource/`、`brand/` 都由加载器识别，无需在代码里拼路径。

## 2. 清单字段（`config.yml`）

| 字段 | 必需 | 说明 |
| --- | --- | --- |
| `app_name` | ✅ | **必须等于目录名**，否则抛 `APP_NAME_MISMATCH`（不一致会让应用内导入静默失效） |
| `app_id` | | 菜单插件 ID，缺省 `app.menu.<target>.<name>` |
| `button_id` | | 左侧菜单按钮对象名，缺省 `app_<name>` |
| `page_object` | | 页面控件对象名，缺省 `<name>Page` |
| `app_icon` | | 图标资源键，配合 `resource/icon/` |
| `app_text` | | 菜单文本语言键，缺省 `language.app.<name>.app_text` |
| `app_tooltip` | | 提示语言键 |
| `app_target` | | 菜单容器，缺省 `LeftMenu` |
| `show_top` | | 按钮是否放在菜单上部（`false` 放底部） |
| `is_active` | | 是否参与初始高亮 |
| `is_default` | | 是否作为默认页（首个 `true` 生效） |
| `protocol` | | `1`（缺省）或 `2`；其他值抛 `APP_PROTOCOL_UNSUPPORTED` |
| `plugin` | | v2 入口里有多个 `AppPlugin` 子类时，用符号名消歧 |
| `core` | | 逻辑层目录名；声明后必须存在，否则抛 `APP_CORE_MISSING` |

最小清单：

```yaml
app_name: "hello"
button_id: "btn_hello"
page_object: "helloPage"
app_text: "language.app.hello.app_text"
app_target: "LeftMenu"
is_default: true
```

## 3. 协议 v2（推荐）

清单写 `protocol: 2`，入口（`app.py` 优先，其次 `gui/main.py`）导出 `AppPlugin` 子类：

```python
from PySide6.QtWidgets import QLabel, QWidget

from sllkgui.appcore import AppPage, AppPlugin


def build_home(ctx, window) -> QWidget:
    page = QWidget()
    label = QLabel(ctx.lang_text("app_text"))
    label.setParent(page)
    return page


class HelloApp(AppPlugin):
    def on_load(self, ctx) -> None:          # 可选：页面构建前调用一次
        self.ready = True

    def pages(self) -> list[AppPage]:
        return [
            AppPage(
                button_id="btn_hello",
                page_object="helloPage",
                build=build_home,
                title_key="language.app.hello.app_text",
                default=True,
            )
        ]
```

入口识别顺序：

1. 模块级 `PLUGIN = HelloApp()`（实例）；
2. 模块级 `PLUGIN = HelloApp`（类，加载器实例化）；
3. 模块内**唯一**的 `AppPlugin` 子类；
4. 多个子类又没写 `PLUGIN` → `APP_PLUGIN_AMBIGUOUS`。

`AppPage` 字段：

| 字段 | 说明 |
| --- | --- |
| `button_id` / `page_object` | 菜单按钮与页面对象名 |
| `build(ctx, window)` | 返回页面 `QWidget`；基座负责 `setObjectName` 与 `addWidget` |
| `title` | `str`、语言键或 `fn(language) -> str` |
| `title_key` | 语言键，缺省 `language.app.<name>.<button_id>` |
| `icon` / `tooltip` | 图标资源键 / 提示文本 |
| `default` / `show_top` / `is_active` | 与清单同义，用于多页面应用逐页声明 |

生命周期钩子：`on_load(ctx)`、`on_language_changed(language)`、`on_unload()`。多数应用不需要覆写
`on_language_changed`，页面标题由基座按 `title_key` 自动刷新。

## 4. 协议 v1（兼容）

清单不写 `protocol`（或写 `1`），入口固定为 `gui/main.py`，按优先级识别三种写法：

| 优先级 | 写法 | 入栈由谁负责 | 能拿到 `AppContext` |
| --- | --- | --- | --- |
| 1 | `def register_plugins(registry, app)` | 应用自己 `addWidget` | 能 |
| 2 | `PAGE = MyPage` / `PAGE = MyPage()`（含 `load_page(window)`） | 页面自己 | 不能 |

> **`PAGE` 的 `self` 是陷阱**：加载器按 `PAGE.load_page(window)` 调用，`PAGE` 写成**类**时
> `self` 拿到的是主窗口，写成**实例**时 `self` 是页面对象、`window` 才是窗口——同一份代码
> 不能依赖 `self` 的含义。内置的 10 个预览应用统一继承 `sllkgui.guicore.CPreviewPage`，
> 它的钩子全部是 `classmethod`，两种写法都成立，新页面建议直接以它为起点。
| 3 | `def build_page(app) -> QWidget` | 基座 | 能 |

```python
# 协议 3：最简
from PySide6.QtWidgets import QLabel, QWidget


def build_page(app):
    page = QWidget()
    page.setObjectName(app.config.get("page_object") or "helloPage")
    label = QLabel(app.lang_text("app_text", "你好"))
    label.setParent(page)
    return page
```

v1 的既有应用无需改动；新应用建议直接用 v2——v1 的三套写法在「谁入栈」「self 是谁」上语义不一致，
是最常见的出错点。

## 5. `AppContext`

页面代码拿到的 `ctx`（v2 的 `build(ctx, window)` 第一参数，v1 的 `app`）：

| 成员 | 说明 |
| --- | --- |
| `config` | 清单字段（`Attrs`，属性/字典双访问） |
| `app_dir` / `core_dir` / `icon_path` | 应用根、逻辑层目录、默认图标（缺失为 `None`） |
| `language` | 当前语言，**每次读取都取最新值** |
| `lang_text(key, default=None)` | 读本应用语言命名空间 `app.<name>.<key>` |
| `resource(*parts)` | `<app>/resource/...` 绝对路径 |
| `icon(name)` / `image(name)` / `voice(name)` / `lang_file(lang)` | 应用内资源定位 |
| `brand(*parts)` | `<app>/brand/...`，纳入基座资源解析链 |
| `import_module("pages.home")` | 在应用命名空间内导入，无需拼 `_sllkgui_apps.<name>.` |

## 6. 语言文件

`resource/lang/<code>.yml` 是**扁平键值**，键名与代码里 `lang_text()` 的第二段对应：

```yaml
# resource/lang/zh_cn.yml
app_text: "你好"
app_tooltip: "示例应用"
greeting: "欢迎使用"
```

```python
ctx.lang_text("greeting")   # -> "欢迎使用"
```

切换语言时，`Language.apply()` 会重新装载所有应用的 `resource/lang/<code>.yml`，
并整体重建页面栈，页面内文本随之更新。四套语言（`zh_cn` / `zh_tw` / `en_us` / `ja_jp`）
的键必须逐键对齐，`test_language_coverage.py` 会检查。

## 7. 品牌覆盖层

`<app>/brand/sllkgui/` 与包内 `_resources/sllkgui/` 同构，自动进入资源解析链，且优先级高于基座：

```text
brand/sllkgui/
├── themes/brand.yaml          # 覆盖或新增主题
├── languages/zh_cn.yaml       # 覆盖基座文案
└── images/svg_icons/...       # 覆盖图标
```

配置类文件（settings / themes / languages）**深合并**：只写要改的键即可，其余键由基座提供。
图标、图片、字体同名时整份替换。

## 8. 装载时序与懒加载

1. `discover_app_dirs()` 扫描含 `config.yml` 的子目录，按名称排序。
2. 每个应用：读清单 → 校验 `app_name` / `core` / `protocol` → 解析图标 → 注入语言命名空间
   → 注册菜单插件 → 按协议注册页面插件。
3. 首个 `is_default: true` 的页面立即构建；其余页面在首次导航时由 `ensure_registered_page()` 构建。
4. 语言切换时清空页面栈，只重建默认页与当前页。

## 9. 常见错误

| 错误码 | 原因 | 处理 |
| --- | --- | --- |
| `APP_NAME_MISMATCH` | 清单 `app_name` 与目录名不一致 | 改成一致，或直接改名目录 |
| `APP_PROTOCOL_UNSUPPORTED` | `protocol` 不是 `1` / `2` | 修正清单 |
| `APP_PLUGIN_MISSING` | `protocol: 2` 但入口没有 `AppPlugin` 子类 | 定义子类或写 `PLUGIN = ...` |
| `APP_PLUGIN_AMBIGUOUS` | 入口有多个子类且未指定 | 写 `PLUGIN = MyApp()` |
| `APP_CORE_MISSING` | 清单 `core` 指向的目录不存在 | 修正目录名或删掉该字段 |
| `APP_PAGE_EMPTY` | `build()` 返回 `None` | 返回一个 `QWidget` |
| `YAML_FILE_NOT_FOUND` | 清单/语言文件路径解析失败 | 确认 `app_name` 与目录一致；`--apps-dir` 用绝对路径 |

页面没出现时按顺序排查：`sllkgui doctor` 是否 `发现应用` > 0 → 加 `--load` 后 `成功加载` 是否等于发现数
（doctor 默认不执行入口代码，不加 `--load` 不会有「成功加载」这一行）→ 清单 `page_object` 与页面
`setObjectName` 是否一致 → `build()` 是否返回控件。
