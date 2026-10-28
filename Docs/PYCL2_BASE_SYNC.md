# PyCL2 基座同步记录（2026-10）

## 结论

本次把 PyCL2 开发过程中验证过的**通用基座能力**回流到 CustomGUI，保留 CustomGUI 自带的
示例应用、内置菜单、主题与资源，不把 PyCL2 的业务页面、品牌文案、主题色和窗口尺寸带进基座。

同步后基座测试：

```text
165 passed
```

## 已合并

### AppCore

| 模块 | 变更 | 原因 |
| --- | --- | --- |
| `language_module.py` | 绑定方法监听改用 `__self__` 判定；支持弱引用订阅与控件销毁清理 | 避免语言切换回调持有已删除控件 |
| `plugin_module.py` | 增加 `eager` 参数、`load_page_plugin()` 单页加载 | 启动时只创建默认页，导航时按需创建 |
| `theme_module.py` | 支持可选强调色覆盖，并从主题色推导 hover/pressed | 基座可安全接受应用层强调色 |
| `theme_module.py` | 记录主题/强调色切换事件 | 便于诊断和遥测 |

### GuiCore

| 模块 | 变更 | 原因 |
| --- | --- | --- |
| `title_bar/title_bar.py` | 菜单点击/释放信号使用实际 sender，sender 为空时回退到菜单按钮 | 修复标题栏多个按钮都路由到最后一个菜单 |
| `title_bar/title_button.py` | 状态/图标刷新从 `repaint()` 改为 `update()` | 交给 Qt 合并重绘，避免同步重绘卡顿 |
| `left_menu/menu.py` | 展开/收起改为按父控件宽度判断，抽出 `expand()` / `collapse()` | 修复窄窗口下展开状态判断错误 |
| `left_menu/menu_button.py` | 增加图标 QPixmap 缓存；状态刷新使用 `update()` | 避免语言/主题切换时重复解码 SVG |
| `left_column/left_button.py` | 状态刷新使用 `update()` | 减少同步重绘 |
| `credits_bar/credits.py` | 订阅语言变化并刷新版权/版本 | 修复切换语言后底部文本不更新 |

### Guis

| 模块 | 变更 | 原因 |
| --- | --- | --- |
| `app_loader.py` | 使用 `setattr(Language, "app", ...)` | 避免属性描述符/类型检查器误判 |
| `language_service.py` | 关闭残留弹窗；重建页面时只建默认页，再按当前路由确保目标页存在 | 避免语言切换实例化全部隐藏页面 |
| `main_window/registry.py` | 新增 `ensure_registered_page()`；`load_registered_pages(eager=False)` | 延迟页面加载的公共入口 |
| `main_window/controller.py` | 路由前确保页面已创建；支持应用自定义主题循环 | 懒加载页面可正常导航 |
| `main_window/setup_main_window.py` | 默认页按需创建并设置初始标题 | 启动阶段减少不必要的页面构建 |

## 未合并（保持 CustomGUI 独立）

- PyCL2 的四语言默认集合：基座目前只有 `zh_cn` / `en_us` 资源；直接启用四语言会出现空翻译。
- PyCL2 的中日繁语言文件、PyCL2 品牌文案、导航图标、Logo。
- PyCL2 的主题色板、窗口尺寸、`pycl2` 应用设置。
- PyCL2 的 `Apps/` 业务页面、组件（`Card`、`SubPageHost`、`TaskProgressPanel` 等）。
- PyCL2 将基座内置菜单清空的做法：CustomGUI 保留自己的搜索/信息/语言/主题入口。

## 后续合并建议

1. **先合并基础设施，再合并视觉资源**：懒加载、主题强调色、信号路由属于基座；颜色和文案属于应用。
2. **把语言集合改为数据驱动**：由 `resource/customui/languages/*.yaml` 是否存在决定可用语言，而不是硬编码四语言。
3. **把懒加载入口补进基座测试**：首屏只创建默认页、导航时创建目标页、语言切换只重建当前页。
4. **把标题栏/菜单的 sender 修复补回归测试**：语言、主题、搜索按钮都必须命中自己的按钮。
5. **不要在基座里清空 `BUILTIN_MENU_PLUGINS`**：业务应用可以注册自己的菜单，但基座演示仍需要内置入口。
6. 基座稳定后打基座版本标签，再让 PyCL2 通过依赖或工作区引用，而不是继续复制文件。
