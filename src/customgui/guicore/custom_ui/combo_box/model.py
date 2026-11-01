"""下拉框的数据模型：纯 Python，不依赖 Qt。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ComboEntry:
    """一个选项：显示文本 + 用户数据（对应 ``QComboBox`` 的 ``UserRole``）。"""

    text: str
    data: Any = None

    def matches_text(self, text: str) -> bool:
        return self.text == text

    def matches_data(self, data: Any) -> bool:
        """惰性比较：用户数据可能不可比较（如 dict），失败即视为不匹配。"""
        try:
            return bool(self.data == data)
        except Exception:
            return False


class EntryList:
    """选项集合，封装增删查改与索引归一化。

    保持与 ``QComboBox`` 一致的语义：

    - ``current_index`` 为 ``-1`` 表示无选中；
    - 删除当前项后，索引落到右邻项；删空则为 ``-1``；
    - 删除当前项左侧的项时，索引左移保持指向同一项。
    """

    def __init__(self) -> None:
        self._entries: list[ComboEntry] = []
        self._index: int = -1

    # ------------------------------------------------------------------
    # 只读视图
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __getitem__(self, index: int) -> ComboEntry:
        return self._entries[index]

    def entries(self) -> list[ComboEntry]:
        return list(self._entries)

    @property
    def index(self) -> int:
        return self._index

    @property
    def current(self) -> ComboEntry | None:
        if 0 <= self._index < len(self._entries):
            return self._entries[self._index]
        return None

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------
    def clear(self) -> bool:
        """清空全部选项，返回当前索引是否发生变化。"""
        changed = self._index != -1
        self._entries.clear()
        self._index = -1
        return changed

    def add(self, text: str, data: Any = None) -> bool:
        """追加一个选项；若原本无选中，自动选中新项。"""
        self._entries.append(ComboEntry(str(text), data))
        if self._index < 0:
            self._index = 0
            return True
        return False

    def insert(self, position: int, text: str, data: Any = None) -> bool:
        """在 *position* 插入；返回当前索引是否随之变化。"""
        position = max(0, min(len(self._entries), int(position)))
        self._entries.insert(position, ComboEntry(str(text), data))
        if self._index < 0:
            self._index = 0
            return True
        if position <= self._index:
            self._index += 1
            return True
        return False

    def remove(self, index: int) -> bool:
        """删除指定项；返回当前索引是否变化。"""
        if not (0 <= index < len(self._entries)):
            return False
        self._entries.pop(index)
        if self._index == index:
            self._index = -1 if not self._entries else min(index, len(self._entries) - 1)
            return True
        if self._index > index:
            self._index -= 1
            return True
        return False

    def normalize(self, index: int) -> int:
        """把任意整数归一化到 ``[-1, len-1]``。

        ``-1`` 原样保留（无选中）；越界正数夹到末项；``< -1`` 视为 ``-1``；
        空集合恒为 ``-1``。
        """
        index = int(index)
        if not self._entries:
            return -1
        if index < 0:
            return -1
        if index >= len(self._entries):
            return len(self._entries) - 1
        return index

    def set_index(self, index: int) -> bool:
        """设置当前索引；返回是否真的变化。"""
        target = self.normalize(index)
        changed = target != self._index
        self._index = target
        return changed

    # ------------------------------------------------------------------
    # 查找
    # ------------------------------------------------------------------
    def find_text(self, text: str) -> int:
        for position, entry in enumerate(self._entries):
            if entry.matches_text(text):
                return position
        return -1

    def find_data(self, data: Any) -> int:
        for position, entry in enumerate(self._entries):
            if entry.matches_data(data):
                return position
        return -1

    def texts(self) -> list[str]:
        return [entry.text for entry in self._entries]


__all__ = ["ComboEntry", "EntryList"]
