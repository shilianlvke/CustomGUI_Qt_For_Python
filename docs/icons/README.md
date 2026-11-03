# 图标资源

本目录只有两件事：**通用图标库**（不进包）和**内置图标说明**。

## 1. 内置图标（随包分发）

位置：`src/customgui/_resources/customui/images/svg_icons/`，共 49 个，随 wheel 分发，
是基座样式与组件默认值唯一引用的图标集。

```python
from customgui.appcore import PathFactory

path = PathFactory.set_svg_icon("icon_arrow_right")   # 自动补 .svg，返回绝对路径
path = PathFactory.set_ico("icon")                    # images/ico/icon.ico
```

`set_svg_icon()` / `set_svg_image()` / `set_png_image()` / `set_jpg_image()` 都只在资源根里查找，
因此应用品牌层的 `brand/customui/images/svg_icons/` 可以同名覆盖基座图标。

## 2. 通用图标库（不随包分发）

位置：`docs/icons/library/`，2481 个通用 SVG（约 11 MB）。

- **不参与运行时解析**，也不会被 `import customgui` 加载；
- 放在仓库里只为方便检索与复制，代价是仓库体积（见 README「已知限制」）；
- 需要某个图标时，复制到自己的应用里，而不是引用本目录。

```text
apps/myapp/
└── resource/
    └── icon/
        └── my_icon.svg
```

```python
# 在页面里
icon_path = ctx.icon("my_icon.svg")            # -> <app>/resource/icon/my_icon.svg
# 或者清单里声明 app_icon，由基座解析菜单图标
```

## 3. 把图标提升为内置

如果某个图标被 `Styles` 或组件默认值引用，它就应该进包：

1. 把文件放到 `src/customgui/_resources/customui/images/svg_icons/`；
2. 代码里用 `PathFactory.set_svg_icon("<name>")` 引用（不带 `.svg`）；
3. 同步更新 `docs/COMPONENTS.md` 中相关的默认值说明（如有）。

图标建议：24×24 viewBox、`currentColor` 或单色填充，方便按主题着色。
多色 SVG 在部分组件里会被栅格化后整体着色，视觉效果可能不符预期。
