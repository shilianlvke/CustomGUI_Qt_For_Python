"""插件管理页的错误码 → 用户话术。

错误码是给日志与支持用的稳定标识，**不直接展示**；用户看到的是「发生了什么 +
下一步怎么做」。未知码回落到通用文案，并保留错误码在 ``detail`` 里。

放在页面目录内而不是 ``appcore``：这些文案属于插件管理页的命名空间
（``language.plugin_store.*``），不是基座通用协议的一部分。
"""

from __future__ import annotations

from typing import Any

#: code → (语言键, 中文兜底, 级别)
_FAILURE_COPY: dict[str, tuple[str, str, str]] = {
    "PLUGIN_STORE_TOGGLE_FAILED": ("error.toggle_failed", "无法切换插件状态，请查看日志后重试。", "error"),
    "PLUGIN_STORE_UPDATE_FAILED": ("error.update_failed", "插件更新失败，请检查网络或版本后重试。", "error"),
    "PLUGIN_STORE_ROLLBACK_FAILED": ("error.rollback_failed", "回滚失败，插件可能仍停在旧版本，请查看日志。", "error"),
    "PLUGIN_STORE_REMOVE_FAILED": ("error.remove_failed", "卸载未完成，请关闭占用该插件的窗口后重试。", "error"),
    "PLUGIN_STORE_INSTALL_FAILED": ("error.install_failed", "安装失败，请检查网络或依赖后重试。", "error"),
    "PLUGIN_STORE_ACTION_FAILED": ("error.action_failed", "操作未能完成，请稍后重试。", "error"),
    "PLUGIN_STORE_SOURCE_ADD_FAILED": ("error.source_add_failed", "添加来源失败，请检查仓库地址是否正确。", "warn"),
    "PLUGIN_STORE_SOURCE_REFRESH_FAILED": ("error.source_refresh_failed", "来源刷新失败，已保留上次结果。", "warn"),
    "PLUGIN_STORE_SOURCE_FAILED": ("error.source_failed", "来源操作失败，请稍后重试。", "error"),
    "PLUGIN_STORE_SOURCE_REMOVE_FAILED": ("error.source_remove_failed", "移除来源失败，请稍后重试。", "error"),
    "PLUGIN_STORE_SOURCE_TOGGLE_FAILED": ("error.source_toggle_failed", "切换源状态失败，请稍后重试。", "warn"),
}

#: 插件管理页使用的语言命名空间（与 ``PageContext.text`` 一致）
_NAMESPACE = "language.plugin_store"


def failure_copy(ctx: Any, code: str) -> tuple[str, str]:
    """返回 ``(用户话术, 级别)``；未知码走通用文案。"""
    spec = _FAILURE_COPY.get(str(code or "").upper())
    if spec is None:
        return str(ctx.text("status.failed", "操作未能完成，请重试。")), "error"
    key, default, level = spec
    return str(ctx.text(key, default)), level


__all__ = ["failure_copy"]
