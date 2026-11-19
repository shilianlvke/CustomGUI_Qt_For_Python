"""公开名文档与 __all__ 的一致性（RV-07）。

文档里手写的导出数字会随组件增减漂移；这里锁定 docs/COMPONENTS.md 首段
声明的两个数字与运行期 ``__all__`` 一致，避免再次出现"126 / 94"式的过时陈述。
"""

from __future__ import annotations

import re
from pathlib import Path

import sllkgui.guicore as guicore
import sllkgui.guicore.custom_ui as custom_ui

DOC = Path(__file__).resolve().parents[1] / "docs" / "COMPONENTS.md"


def test_documented_export_counts_match_all():
    text = DOC.read_text(encoding="utf-8")
    header = "\n".join(text.splitlines()[:6])
    guicore_count = re.search(r"顶层导出\s*(\d+)\s*个公开名", header)
    custom_count = re.search(r"`custom_ui`\s*命名空间\s*(\d+)\s*个", header)

    assert guicore_count is not None, "COMPONENTS.md 首段须声明 guicore 导出数"
    assert custom_count is not None, "COMPONENTS.md 首段须声明 custom_ui 导出数"
    assert int(guicore_count.group(1)) == len(guicore.__all__)
    assert int(custom_count.group(1)) == len(custom_ui.__all__)


def test_removed_compat_shells_have_no_qss_selector():
    """已删除的兼容壳不应留下无消费点的 QSS 选择器。"""
    style_source = (Path(guicore.__file__).parent / "styles_components.py").read_text(encoding="utf-8")
    assert "CPushButton_PushButton" not in style_source
    assert "CLineEdit_LineEdit" not in style_source
