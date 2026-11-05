"""轮子安装后的最小冒烟：配置装载、资源解析与全局样式构建。

用法（先构建并安装 wheel，再从仓库根运行）::

    uv build
    uv pip install --reinstall dist/sllkgui-*.whl
    python scripts/wheel_smoke.py

脚本不依赖源码树：`src/` 不在 `sys.path` 时导入的是已安装 wheel。
失败以非零码退出，供 CI 判定。
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    try:
        import sllkgui
        from sllkgui.appcore import get_app_context
        from sllkgui.guicore import Styles

        context = get_app_context()
        if context.settings is None:
            raise RuntimeError("配置上下文未加载 settings")
        sheet = Styles().style
        for selector in ("#CWindow_Frame", "#CCard_Frame"):
            if selector not in sheet:
                raise RuntimeError(f"全局样式表缺少关键选择器: {selector}")
        print(f"wheel smoke ok: sllkgui {sllkgui.__version__}, qss {len(sheet)} chars")
        return 0
    except Exception as exc:
        print(f"wheel smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
