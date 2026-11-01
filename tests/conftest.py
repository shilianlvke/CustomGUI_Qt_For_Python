"""测试公共设置。

src layout 下测试必须导入**已安装的** ``customgui``（``pip install -e .``），
不再向 ``sys.path`` 塞源码目录——否则测的是源码树而不是安装产物，
"wheel 装完能不能用"这类问题就永远测不出来。
"""

import os

# 所有测试都在无显示环境下跑；需要真实窗口的用例自行 skip。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
