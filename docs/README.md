# 文档索引

本目录是 SllkGUI 的唯一文档来源，**手工维护**，不再自动生成。
内容与 `1.0.0` 代码同步；代码是最终事实，文档与代码冲突时以代码为准并提 issue。

| 文档 | 内容 | 适合谁 |
| --- | --- | --- |
| [../README.md](../README.md) | 定位、版本状态、安装、快速开始、目录结构、配置与限制 | 第一次接触项目的人 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 分层、包地图、启动时序、资源解析、扩展点、架构债 | 要改基座或做技术评审的人 |
| [PLUGIN.md](PLUGIN.md) | 应用目录、清单字段、协议 v1/v2、`AppContext`、语言与品牌层 | 写业务应用的人 |
| [COMPONENTS.md](COMPONENTS.md) | 组件分类、常用签名、窗口部件、设计令牌、设置项速查 | 写界面的人 |
| [API.md](API.md) | 门面 API 速查：配置、主题、语言、插件、遥测、存储、任务 | 集成基座的人 |
| [contributing.md](contributing.md) | 环境、分层规则、代码约定、测试、提交与发版 | 贡献者 |
| [icons/README.md](icons/README.md) | 图标资源库说明（2481 个通用 SVG，不随包分发） | 找图标的人 |

## 建议阅读顺序

1. **只想跑起来**：根 README 的「安装 / 快速开始」。
2. **想写页面**：PLUGIN.md + COMPONENTS.md 的对应组件章节，再照抄 `apps/` 里的同名预览应用。
3. **想改基座**：ARCHITECTURE.md → contributing.md → `tests/test_architecture_boundaries.py`。

## 维护约定

- 新增公开 API 时同步更新 API.md；新增组件时同步更新 COMPONENTS.md 的分类表与预览应用对照表。
- 协议、清单字段、错误码只在 PLUGIN.md 定义一次，README 只做摘要并链接过去。
- 不写「某次重构做了什么」的过程记录：历史变更归 CHANGELOG，架构现状归 ARCHITECTURE。
- 文档里出现的命令与代码片段必须可执行；路径、版本号、测试数量变更时一起改。
