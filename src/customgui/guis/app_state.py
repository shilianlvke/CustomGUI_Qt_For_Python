"""应用加载器的可变状态：发现的目录、已加载句柄、是否已加载。

为什么要单独一个模块
--------------------
语言提供者（``app_manifest``）要读「当前发现了哪些应用目录」，而写入发生在
``app_loader.load_apps()``。如果状态留在 ``app_loader``，``app_manifest`` 就得
反向 import 加载器，形成环；放到这里两个模块都只是**读/写一个中立的位置**。

对外不构成契约：消费方用 ``load_app_handles()`` 拿句柄，不要碰这里的列表。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 只为类型标注，避免运行时循环 import
    from .app_context import AppHandle

#: 最近一次发现的应用目录（语言切换时复用）
app_dirs: list[Path] = []
#: 已成功加载的应用句柄
handles: list[AppHandle] = []
#: 是否已完成加载（``load_apps`` 幂等标记）
loaded: bool = False
