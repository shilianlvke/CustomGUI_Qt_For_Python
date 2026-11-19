# 图标资源

本目录说明**内置图标**的存放位置与使用方式。

## 内置图标（随包分发）

位置：`src/sllkgui/_resources/sllkgui/images/svg_icons/`，随 wheel 分发，
是基座样式与组件默认值唯一引用的图标集。

```python
from sllkgui.appcore import PathFactory

path = PathFactory.set_svg_icon("icon_arrow_right")   # 自动补 .svg，返回绝对路径
path = PathFactory.set_ico("icon")                    # images/ico/icon.ico
```

`set_svg_icon()` / `set_svg_image()` / `set_png_image()` / `set_jpg_image()` 都只在资源根里查找，
因此应用品牌层的 `brand/sllkgui/images/svg_icons/` 可以同名覆盖基座图标。

## 往里加图标

如果某个图标被 `Styles` 或组件默认值引用，它就应该进包：

1. 把文件放到 `src/sllkgui/_resources/sllkgui/images/svg_icons/`；
2. 代码里用 `PathFactory.set_svg_icon("<name>")` 引用（不带 `.svg`）；
3. 同步更新 `docs/COMPONENTS.md` 中相关的默认值说明（如有）。

图标建议：24×24 viewBox、`currentColor` 或单色填充，方便按主题着色。
多色 SVG 在部分组件里会被栅格化后整体着色，视觉效果可能不符预期。

## 需要更多图标时

仓库**不**附带通用图标库。曾经这里放过 2483 个第三方 SVG，但它们不参与运行时解析、
不被任何代码引用，却会让源码分发包（sdist）多出约 3 MB，与「基座只带自己用到的
图标」的原则相悖，因此已移除。

按需获取的方式：

- 从 [Material Symbols](https://fonts.google.com/icons) / [Lucide](https://lucide.dev)
  等图标库取单个文件，放进应用自己的 `resource/icon/`；
- 应用内的图标由 `ctx.icon("<name>.svg")` 解析，或在清单里声明 `app_icon`，
  由基座解析菜单图标：

```text
apps/myapp/
└── resource/
    └── icon/
        └── my_icon.svg
```

第三方图标的版权与许可证由使用者自行确认，混进基座包前需确认可再分发。
