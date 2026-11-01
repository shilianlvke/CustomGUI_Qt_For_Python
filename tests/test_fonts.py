"""字体注册工具测试（guicore.fonts）。"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from customgui.guicore import install_fonts, install_system_fonts


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_install_fonts_empty_is_noop(qapp):
    assert install_fonts([]) == 0


def test_install_fonts_skips_missing_files(qapp, tmp_path):
    missing = [tmp_path / "does_not_exist.ttf"]
    assert install_fonts(missing) == 0


def test_install_fonts_accepts_str_and_path(qapp, tmp_path):
    # 没有真实字体文件时只验证「不抛异常 + 跳过不存在的文件」
    result = install_fonts([tmp_path / "a.ttf", str(tmp_path / "b.otf")])
    assert result == 0


def test_install_system_fonts_is_noop_on_linux(qapp):
    """Linux 无 Windows 系统字体目录时返回 0 且不抛异常。"""
    assert install_system_fonts() == 0
