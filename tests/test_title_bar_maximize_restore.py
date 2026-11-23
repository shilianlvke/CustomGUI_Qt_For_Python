"""最大化按钮：再次点击还原到配置的 minimum_size，而不是启动尺寸。"""

from __future__ import annotations

import pytest

from sllkgui.guicore.window.title_bar import title_bar as module


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def title_bar(app, monkeypatch):
    # 启动尺寸 1000x700，配置的最小尺寸 600x500：两者必须可区分。
    # 只改 minimum_size，其余配置保持真实值，CTitleBar 构造需要其它字段。
    from sllkgui.appcore import AppLanguages, Language

    Language.update(AppLanguages["zh_cn"].data)
    monkeypatch.setattr(module.AppSettings, "minimum_size", (600, 500))
    widget = module.QWidget()
    widget.resize(1000, 700)
    widget.show()
    app.processEvents()
    bar = module.CTitleBar(widget, widget)
    yield bar
    bar.deleteLater()
    widget.deleteLater()


def test_maximize_then_restore_uses_minimum_size(app, title_bar):
    parent = title_bar._parent

    title_bar.maximize_restore()
    app.processEvents()
    assert parent.isMaximized()
    assert title_bar._is_maximized is True

    title_bar.maximize_restore()
    app.processEvents()
    assert not parent.isMaximized()
    assert (parent.width(), parent.height()) == (600, 500)
    assert (parent.width(), parent.height()) != (1000, 700)


def test_restore_again_maximizes(app, title_bar):
    parent = title_bar._parent

    title_bar.maximize_restore()
    app.processEvents()
    title_bar.maximize_restore()
    app.processEvents()
    assert (parent.width(), parent.height()) == (600, 500)

    title_bar.maximize_restore()
    app.processEvents()
    assert parent.isMaximized()


def test_restore_falls_back_when_minimum_size_missing(app, title_bar, monkeypatch):
    parent = title_bar._parent
    monkeypatch.setattr(title_bar.settings, "minimum_size", None)

    title_bar.maximize_restore()
    app.processEvents()
    title_bar.maximize_restore()
    app.processEvents()
    assert not parent.isMaximized()
    assert (parent.width(), parent.height()) == (1000, 700)
