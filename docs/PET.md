# 桌面宠物

基座原生常驻桌面宠物：由 `temp/mihoutao.html` 原型 1:1 移植，39 情绪状态、18 种果形切面、
11 色果肉调色板、8 类装饰层与弹簧物理全部保留。

## 为什么是基座原生而不是插件

结论：**基座原生**。判定依据：

| 维度 | 插件 | 基座原生（采纳） |
| --- | --- | --- |
| Surface 契约 | 清单强制至少一个 Surface（`PLUGIN_SURFACE_EMPTY`），会污染 `surface_count()` | 不注册 Surface，空插件时 `surface_count()` 仍为 0 |
| 生命周期 | 跟随插件加载器，停用/热重载会连带销毁窗口 | 跟随主窗口，与托盘同级常驻 |
| 用户体验 | 需安装、启用、经版本与信任模型 | 开箱即用，无需安装步骤 |
| 适用边界 | 第三方扩展、可插拔页面 | 基座级常驻 UI（标题栏 / 托盘 / 宠物） |

`tests/test_mihoutao_pet.py::test_pet_does_not_add_surfaces` 固化了这条边界。

## 结构

```text
src/sllkgui/guicore/pet/
├── __init__.py          # 公开面：MihoutaoPetController / PetWindow
├── controller.py        # 生命周期、基座能力统一接入与状态同步
├── settings.py          # 宠物偏好默认值与键映射（设置页本体在 appcore 基座原生设置）
├── shortcuts.py         # 基座快捷键注册表接入与冲突提示
├── pet_window.py        # 无边框/置顶/透明窗口 + 右键菜单（随语言刷新）
└── engine/
    ├── core.py          # 角色引擎：几何 / 眼型 / 装饰 / 弹簧 / 状态机
    └── spec.json        # 规格唯一真源，与原型 window.MIHOUTAO_SPEC 逐字段一致
```

## 与原型的一致性

移植时保持几何与时间轴逐位一致，并由差分测试固化：

- **几何**：`superPoly` 超级椭圆 64 点采样、`eyePoints` 20 点眼型、`starPath`、`arcPath`
  的输出与原型 JS 逐字符相同（`tests/fixtures_mihoutao_geometry.json` 由 node 采样原型
  JS 得到，`test_geometry_is_identical_to_prototype` 逐项比对）。
- **时间轴**：单帧 `dt` 上限 50ms（对应原型 `_tick` 的 `Math.min(0.05, raw)`），
  弹簧使用同样的 240Hz 子步进定步长积分。
- **装饰层**：`dots` / `radar` / `progress` / `orbit` / `badge` / `pulse` / `sparkle` / `zzz`
  的半径、速度、透明度曲线与原型的 `_paintDeco` 一一对应。
- **渲染层级**：阴影 → 后置装饰 → （果皮体 + 果肉盘 + 放射籽 + 白心 + 双眼）→ 前置装饰 → 粒子。

渲染走 `QSvgRenderer`：引擎产出与原型同构的 SVG 字符串，不引入 WebEngine。

## 使用

启动 `sllkgui run` 后宠物自动出现在右下角。

| 操作 | 效果 |
| --- | --- |
| 左键拖拽 | 移动宠物 |
| 双击 | 跳一下（`hopOnce`） |
| 右键 | 菜单：39 态 / 18 果形 / 11 色 / 转圈 / 跳跃 / 粒子 / 置顶 / 退出 |
| 托盘 | 显示隐藏、转一圈、跳一下（基座托盘就绪时才注册） |
| 快捷键 | Ctrl/⌘+Alt+P 显隐、R 转圈、J 跳跃、B 粒子 |

## 基座基础能力接入

| 基础项 | 接入方式 |
| --- | --- |
| 设置页 | **基座原生设置**（`core.pet`），出现在设置窗口原生分类而非插件栏；含 7 项配置，值落 `user.yaml` 的 `pet_*` 键 |
| 配置读写 | SettingsSession / SettingsStore 统一读写；`settings_change_bus` 保存后即时同步 |
| 快捷键 | `shortcut_registry` 的 `sllkgui.pet` owner；冲突时拒绝注册并 toast 提示 |
| 主题色 | 订阅 ThemeManager，强调色覆盖默认描边/徽标；状态显式配色保持原型 |
| 语言 | 订阅 Language，标题/tooltip/菜单/托盘/快捷键说明随语言刷新 |
| 生命周期 | start 注册、shutdown 逐一退订并注销快捷键/托盘动作，全部幂等 |

快捷键与托盘动作使用基座已有机制：快捷键冲突不会覆盖基座锁定项；托盘只在基座托盘处于激活状态时添加动作，避免重复拉起托盘。

## 偏好

统一写在 `<data_root>/settings/user.yaml`（基座原生设置，键名 `pet_*`）：

```yaml
show_pet: true        # 是否显示
pinned: true          # 窗口置顶
follow_pointer: true  # 眼睛跟随鼠标
shape: blob           # 果形 id
color: green          # 果肉色 id
size: 220             # 窗口边长 px（96–480）
deco_scale: 1.32      # 特效层缩放（0.55–1.5）
```

窗口位置 `pos_x/pos_y` 仅保存在内存中，避免拖拽期间高频写盘。
读写失败只告警，绝不阻断启动；非法值回落默认。

## 降级行为

- 无 `QApplication`（headless / 早期加载）：跳过建窗，不崩溃。
- 系统托盘不可用：宠物窗口与右键菜单仍可用，只是没有托盘入口。
- 宠物启动异常：记录告警并继续启动主窗口（`_start_pet` 捕获后返回 `None`）。

## 事件控制

基座与插件可通过统一事件总线控制宠物、订阅状态变更，协议详见 [PET_EVENTS.md](PET_EVENTS.md)。
