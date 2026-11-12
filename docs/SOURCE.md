# 源仓库协议

源仓库只存**插件元信息**，不存插件代码。一个插件代码仓库对应源中的一条
`plugins/<id>/entry.yaml`。官方源由维护者审核合并，用户也可以自建同结构源。

## 1. 目录结构

```text
sllkgui-source/
├── source.yaml
├── schema/
│   ├── source.schema.json
│   └── plugin-entry.schema.json
├── categories.yaml
├── plugins/
│   └── com.example.notes/
│       ├── entry.yaml
│       ├── icon.svg
│       └── screenshots/
├── scripts/validate_source.py
├── CONTRIBUTING.md
└── README.md
```

## 2. `source.yaml`

```yaml
schema: 1
id: official
name: SllkGUI Official Source
description: 官方审核的 SllkGUI 插件源
maintainers: [shilianlvke]
homepage: https://gitee.com/shilianlvke/sllkgui-source
updated_at: 2026-11-12
```

## 3. `plugins/<id>/entry.yaml`

```yaml
schema: 1
id: com.example.notes
name: Notes
summary: 通用便签
description: |
  支持多 Surface 的便签插件。
author: example
license: MIT
homepage: https://gitee.com/example/sllkgui-notes
repository: https://gitee.com/example/sllkgui-notes.git
categories: [productivity, tools]
icon: icon.svg
compliance: 1
versions:
  - version: 1.2.0
    ref: v1.2.0
    commit: 0123456789abcdef0123456789abcdef01234567
    manifest_sha256: 9f2c...
    api: 1
    sllkgui: ">=2.0.0,<3.0.0"
    python: ">=3.12"
    permissions: [filesystem.write]
    dependencies:
      - id: com.example.core
        version: ">=1.0.0,<2.0.0"
    yanked: false
```

要求：

- `id` 必须与插件清单一致，目录名与 `id` 一致。
- `commit` 为完整 commit；`manifest_sha256` 为插件仓库 `sllkgui-plugin.yml` 的 SHA-256。
- 发布后的版本条目不修改；撤回用 `yanked: true`。
- `compliance: 1` 表示已通过 `docs/PLUGIN_STANDARD.md`。

## 4. PR 流程

1. 插件仓库完成开发并打 SemVer tag。
2. Fork 官方源，新增/更新 `plugins/<id>/entry.yaml` 与图标/截图。
3. 运行校验：
   ```powershell
   sllkgui plugin lint <插件仓库>
   python scripts/validate_source.py
   ```
4. 维护者审核元信息、权限、分类、许可证与合规状态。
5. 合并后用户 `sllkgui source refresh` 即可搜索安装。

## 5. 用户源

```powershell
sllkgui source add https://gitee.com/my-team/sllkgui-source.git --id my-team
sllkgui source add "file:///D:/tmp/source.git" --allow-local --id local
sllkgui source list --json
sllkgui source refresh --all
```

- 同一插件 ID 出现在多个源时，安装必须用 `--source` 指定。
- 自建源安装前会提示“非官方源”，需要确认。
- 源审核保证元信息质量，不保证插件代码安全。
