# 文档索引

本目录是 SllkGUI 的唯一文档来源，**手工维护**，不再自动生成。
内容与 `4.0.0` 代码同步；代码是最终事实，文档与代码冲突时以代码为准并提 issue。

| 文档 | 内容 | 适合谁 |
| --- | --- | --- |
| [../README.md](../README.md) | 项目定位、版本、Windows 启动器与源码运行入口 | 第一次接触项目的人 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 分层、包地图、关键约定、扩展点 | 要改基座或做技术评审的人 |
| [API.md](API.md) | 门面 API 速查：配置、主题、语言、插件、遥测、存储、任务 | 集成基座的人 |
| [PLUGIN.md](PLUGIN.md) | 插件结构、清单字段、`GalleryContext`、设置、快捷键、语言 | 写插件的人 |
| [PLUGIN_STANDARD.md](PLUGIN_STANDARD.md) | 插件开发规范（强制）与 lint 规则 | 写插件的人 |
| [SOURCE.md](SOURCE.md) | 源仓库协议：`entry.yaml`、审核与发布流程 | 维护插件源的人 |
| [GALLERY.md](GALLERY.md) | gallery / run 两种模式、存储布局、加载流程、命令 | 用命令行、排查加载问题的人 |
| [SETTINGS.md](SETTINGS.md) | 统一设置系统：命名空间、存储、基座页面、插件 `ctx.settings`、组件与保存语义 | 改设置或给插件加配置的人 |
| [COMPONENTS.md](COMPONENTS.md) | 组件分类、常用签名、窗口部件、设计令牌、设置项速查 | 写界面的人 |
| [TOAST.md](TOAST.md) | 统一 Toast 协议 v1（**设计稿**）：类型、去重、通道/并发、事件、错误码、注册规范、场景覆盖 | 写插件反馈、做通知一致性改造的人 |
| [POPUP_MENU.md](POPUP_MENU.md) | 自绘弹出菜单：接口、交互、边界与 `QMenu` 迁移 | 写菜单的人 |
| [TRAY.md](TRAY.md) | 托盘所有权、槽位裁决、插件动作协议 | 写托盘动作的人 |
| [SHORTCUTS.md](SHORTCUTS.md) | 快捷键作用域、优先级、冲突策略与插件协议 | 写快捷键的人 |
| [contributing.md](contributing.md) | 环境、分层规则、代码约定、测试、提交与 tag 发版 | 贡献者 |
| [CHANGE_PLAN.md](CHANGE_PLAN.md) | 1.0.0 时期的一次性规划矩阵与变更追溯（已归档） | 做变更追溯的人 |
| [MANUAL_QA.md](MANUAL_QA.md) | 历史人工验收档案：视觉与交互问题清单（0.6.0 基线） | 回归时人工复测的人 |
| [reviews/](reviews/) | 技术评审与专项审计存档（第三方评审、热重载可行性、Toast 接入审计） | 做技术决策追溯的人 |
| [icons/README.md](icons/README.md) | 内置图标位置与添加方式 | 加图标的人 |

## 建议阅读顺序

1. **只想跑起来**：根 README 的「安装 / 快速开始」。
2. **想写页面**：PLUGIN.md + COMPONENTS.md 的对应组件章节，再照抄
   `src/sllkgui/showcase/core_preview/surfaces/` 里的同名 Surface 实现。
3. **想改基座**：ARCHITECTURE.md → contributing.md → `tests/test_architecture_boundaries.py`。

## 维护约定

- 新增公开 API 时同步更新 API.md；新增组件时同步更新 COMPONENTS.md 的分类表与预览应用对照表。
- 协议、清单字段、错误码只在 PLUGIN.md 定义一次，README 只做摘要并链接过去。
- 不写「某次重构做了什么」的过程记录：历史变更归 CHANGELOG，架构现状归 ARCHITECTURE。
- 文档里出现的命令与代码片段必须可执行；路径、版本号、测试数量变更时一起改。
