# 图标资源库

`library/` 下是 2483 个通用 SVG 图标（来自图标集），**不随 `customgui` wheel 分发**，也不参与运行时解析。

## 为什么放在这里

`AppCore/SYS/config/paths.py::PathFinder` 只从 `resource/customui/images/svg_icons/` 解析基座内置图标（49 个），
其余图标集此前以 `svg_icons_new/` 留在包内资源里，每个 `pip install` 都会多下载 10MB，但代码里没有任何引用。

## 怎么用

需要某个图标时，把它复制进你自己的应用资源目录：

```text
你的应用/
└── resource/
    └── icon/
        └── my_icon.svg      # 从 docs/icons/library/ 里挑
```

然后在页面里：

```python
from AppCore import PathFactory

icon_path = PathFactory.resolve_svg(app.resource("icon", "my_icon.svg"))
```

或者直接用自己的 QIcon 加载，与本基座无关。

## 想恢复成随包分发

如果某个图标成了基座内置图标（被 `Styles` 或组件默认值引用），把它移回
`customgui/resource/customui/images/svg_icons/` 并在代码里用 `PathFactory.set_svg_icon("<name>")` 引用。
