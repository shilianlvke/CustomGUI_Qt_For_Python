"""预览应用冒烟测试：每个 Apps/<name>/gui/main.py 都能构建页面。"""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QStackedWidget

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "Apps"


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
    page = module.PAGE()
    page.ui = SimpleNamespace(load_pages=SimpleNamespace(pages=stack))
    page.load_page()
    assert stack.count() == 1
    widget = stack.widget(0)
    assert widget.objectName().endswith("Page")
