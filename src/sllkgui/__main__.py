"""``python -m sllkgui`` 等价于 ``sllkgui`` 命令。"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
