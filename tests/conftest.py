"""测试公共设置。

src layout 下测试必须导入**已安装的** ``customgui``（``pip install -e .``），
不再向 ``sys.path`` 塞源码目录——否则测的是源码树而不是安装产物，
"wheel 装完能不能用"这类问题就永远测不出来。
"""

import os
import tempfile

# 所有测试都在无显示环境下跑；需要真实窗口的用例自行 skip。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 用户配置持久化会写入 data_dir；测试统一落到临时目录，避免污染开发者
# 真实的 %APPDATA%/CustomGUI，也防止本机既有 user.yaml 影响断言。
os.environ.setdefault("CUSTOMGUI_DATA_DIR", tempfile.mkdtemp(prefix="customgui-tests-"))
