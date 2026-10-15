"""example 应用范式验证：基座能力访问 + 自身能力使用（逐项断言）。"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from AppCore import ColorPalette, PluginRegistry, get_theme_manager
from AppCore.SYS.module.telemetry_module import read_recent_events
from Guis.app_loader import register_app
from Guis.language_service import apply_language

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "Apps" / "example"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def diagnostics_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    apply_language("zh_cn")


class _Pages:
    def __init__(self):
        self.widgets = []

    def addWidget(self, widget):
        self.widgets.append(widget)


def _build_window():
    pages = _Pages()
    ui = type("Ui", (), {"load_pages": type("Pages", (), {"pages": pages})()})()
    return type("Window", (), {"ui": ui})(), pages


def _load_example():
    registry = PluginRegistry()
    context = register_app(EXAMPLE_DIR, registry=registry)
    return registry, context


def test_example_paradigm_base_access(qapp, diagnostics_dir):
    """基座类/方法/资源访问：组件、配置、设计令牌、遥测、主题色。"""
    registry, _context = _load_example()
    pages = registry.page_plugins()
    assert len(pages) == 1
    assert pages[0].plugin_id == "app.page.example"

    window, container = _build_window()
    pages[0].loader(window)
    page = container.widgets[0]

    # 基座组件（CCard/CPushButton）已挂载
    from GuiCore import CCard, CPushButton

    assert len(page.findChildren(CCard)) >= 1
    assert len(page.findChildren(CPushButton)) == 1
    # 基座配置（AppSettings.family 参与字体样式）
    assert "微软雅黑" in page.title_label.styleSheet()
    # 基座设计令牌
    assert "10px" in page.token_label.text()
    # 基座主题色（ColorPalette 实时值）
    assert page.palette_color == ColorPalette.custom_bg_one
    # 基座遥测事件
    assert any(e["name"] == "example.build_page" for e in read_recent_events(limit=10))


def test_example_paradigm_own_capabilities(qapp, diagnostics_dir):
    """自身能力：lib 逻辑、语言、图标、样式。"""
    registry, context = _load_example()
    pages = registry.page_plugins()
    window, container = _build_window()
    pages[0].loader(window)
    page = container.widgets[0]

    # 自身逻辑目录（lib 相对导入，add/sub 计算结果 (1+2)-(10-7)=0）
    assert page.result_label.text() == "用户逻辑计算结果: 0"
    # 自身语言（app.lang_text，zh_cn）
    assert page.title_label.text() == "示例插件"
    # 自身图标（app.icon_path 指向应用内 resource/icon/app_icon.svg）
    assert context.icon_path.is_file()
    assert not page.icon_button.icon().isNull()
    # 自身样式（gui/style.py 的 STYLE + build_style）
    assert "Microsoft YaHei" in page.styleSheet()
    assert ColorPalette.custom_text_foreground in page.styleSheet()


def test_example_paradigm_language_switch_rebuild(qapp, diagnostics_dir):
    """语言切换 + 页面重建后，自身语言/样式刷新。"""
    registry, _context = _load_example()
    pages = registry.page_plugins()

    window, container = _build_window()
    pages[0].loader(window)
    assert container.widgets[0].title_label.text() == "示例插件"

    apply_language("en_us")
    window2, container2 = _build_window()
    pages[0].loader(window2)
    assert container2.widgets[0].title_label.text() == "Example App"
    assert container2.widgets[0].result_label.text() == "User logic result: 0"


def test_example_paradigm_theme_manager_accessible(qapp):
    """基座主题管理器可访问（应用可订阅主题变更）。"""
    manager = get_theme_manager()
    assert manager.current() in ("default", "bright", "dracula", "eye")


def test_example_paradigm_resource_accessor(qapp, diagnostics_dir):
    """自身资源统一访问器：icon/image/voice/resource/lang_file 均指向应用内路径。"""
    _registry, context = _load_example()

    # icon
    assert context.icon("app_icon.svg").is_file()
    # images
    assert context.image("mihoutao.svg").is_file()
    assert context.image("头像.jpg").is_file()
    # voice（目录存在，具体音频文件由应用自备）
    assert context.voice("welcome.wav").parent.is_dir()
    # 通用 resource + lang_file
    assert context.resource("images", "mihoutao.svg") == context.image("mihoutao.svg")
    assert context.lang_file("zh_cn").is_file()
    assert context.lang_file("en_us").is_file()

    # 页面演示控件
    registry, _context2 = _load_example()
    window, container = _build_window()
    registry.page_plugins()[0].loader(window)
    page = container.widgets[0]
    assert "mihoutao.svg" in page.image_label.text()
    assert "有" in page.image_label.text()  # 文件存在
    assert "有" in page.voice_label.text()  # voice 目录存在
