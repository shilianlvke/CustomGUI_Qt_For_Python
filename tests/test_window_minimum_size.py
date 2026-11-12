"""窗口最小尺寸：window.yaml 的 minimum_size 必须真正生效。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sllkgui.guis.windows.main_window import setup_main_window as module


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_apply_minimum_size_resizes_small_window(app, monkeypatch):
    monkeypatch.setattr(module, "AppSettings", SimpleNamespace(minimum_size=(900, 700)))
    window = module.QWidget()
    window.resize(400, 300)
    module.SetupMainWindow.apply_minimum_size(window)

    screen = window.screen()
    expected_width = min(900, screen.availableGeometry().width()) if screen else 900
    expected_height = min(700, screen.availableGeometry().height()) if screen else 700
    assert window.minimumWidth() == expected_width
    assert window.minimumHeight() == expected_height
    assert window.width() >= expected_width
    assert window.height() >= expected_height
    window.deleteLater()


def test_apply_minimum_size_ignores_zero(app, monkeypatch):
    monkeypatch.setattr(module, "AppSettings", SimpleNamespace(minimum_size=(0, 0)))
    window = module.QWidget()
    window.resize(400, 300)
    module.SetupMainWindow.apply_minimum_size(window)
    assert window.minimumWidth() == 0
    assert window.minimumHeight() == 0
    window.deleteLater()
