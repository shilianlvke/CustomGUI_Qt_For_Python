# Hello

SllkGUI 插件模板。

## 功能

- 一个最小 Surface（`home`）
- 日志/遥测全部接入基座：`ctx.log` / `ctx.event` / `ctx.timing`

## 权限

- `filesystem.write`：仅写入 `ctx.data_dir`

## 数据位置

`ctx.data_dir`（卸载默认保留，`--purge` 才删除）。

## 事件表

| 事件 | 时机 |
| --- | --- |
| `sample.loaded` | 插件加载完成 |
| `sample.unloaded` | 插件卸载 |
| `surface.ready` | Surface 构建完成 |

## 开发

```bash
sllkgui plugin lint .
sllkgui run --plugin-dir ../
```
