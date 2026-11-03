"""预览应用冒烟测试：每个 apps/<name>/gui/main.py 都能构建页面。"""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QStackedWidget

from customgui.guis.app_manifest import load_app_manifest

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _app_dirs() -> list[Path]:
    return sorted(path for path in APPS.iterdir() if (path / "gui" / "main.py").is_file())


@pytest.mark.parametrize("app_dir", _app_dirs(), ids=lambda path: path.name)
def test_preview_page_builds(qapp, app_dir):
    spec = importlib.util.spec_from_file_location(f"_preview_{app_dir.name}", app_dir / "gui" / "main.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "PAGE")

    stack = QStackedWidget()
    stack.resize(1000, 720)
    # 与加载器一致：以 PAGE.load_page(window) 形式调用，类/实例两种写法都成立
    window = SimpleNamespace(ui=SimpleNamespace(load_pages=SimpleNamespace(pages=stack)))
    module.PAGE.load_page(window)
    assert stack.count() == 1
    widget = stack.widget(0)
    assert widget.objectName().endswith("Page")
    # 真正显示并触发一次绘制，捕获绘制回调里的签名/空指针问题
    stack.show()
    qapp.processEvents()
    stack.grab()
    stack.hide()


@pytest.mark.parametrize("app_dir", _app_dirs(), ids=lambda path: path.name)
def test_page_object_matches_manifest(app_dir):
    """页面 objectName 必须与清单声明的 ``page_object`` 一致（跳转靠它定位页面）。"""
    config = load_app_manifest(app_dir)
    expected = str(config.get("page_object") or "")
    assert expected, f"{app_dir.name} 的 config.yml 缺少 page_object"

    spec = importlib.util.spec_from_file_location(f"_manifest_{app_dir.name}", app_dir / "gui" / "main.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PAGE.object_name() == expected
