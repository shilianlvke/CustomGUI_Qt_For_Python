## 变更摘要

<!-- 一两句话说清「改了什么、为什么」。 -->

## 关联 issue

<!-- 关联的 issue 编号，如 Closes #123 -->

## 变更类型

- [ ] 缺陷修复
- [ ] 新功能
- [ ] 重构（行为不变）
- [ ] 破坏性变更（**请在下方单独说明迁移方式**）
- [ ] 文档

## 破坏性变更

<!--
若勾选了破坏性变更，请写明：
1. 哪些符号 / 行为变了
2. 下游要怎么迁移
没有破坏性变更则写「无」。
-->

## 验证情况

<!-- 贴上你实际跑过的命令与结果。CI 门禁为： -->

- [ ] `uv run ruff check src tests examples scripts`
- [ ] `uv run ruff format --check src tests examples scripts`
- [ ] `uv run mypy`
- [ ] `uv run pytest --cov=sllkgui --cov-fail-under=71`

CI 链接：______（请贴本 PR 对应门禁运行的链接）

实际输出：

```
```

## 补充说明

<!--
若改动了插件协议、清单字段或公开 API，请在此说明并同步更新
docs/PLUGIN.md 与 CHANGELOG.md。
-->
