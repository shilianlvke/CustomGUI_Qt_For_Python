"""字体注册工具测试（guicore.fonts）。"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication

from sllkgui.guicore import install_fonts, install_system_fonts


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


@pytest.mark.skipif(sys.platform != "linux", reason="仅在无 Windows 系统字体目录的 Linux 上断言返回 0")
def test_install_system_fonts_is_noop_on_linux(qapp):
    """Linux 无 Windows 系统字体目录时返回 0 且不抛异常。"""
    assert install_system_fonts() == 0


def test_select_system_fonts_skips_available_families(tmp_path):
    """系统已能发现的字体族不再注册，避免重复加载整套 CJK 字体。"""
    from sllkgui.guicore.fonts import _select_system_fonts

    (tmp_path / "msyh.ttc").write_bytes(b"font")
    (tmp_path / "msyhbd.ttc").write_bytes(b"font")
    (tmp_path / "segoeui.ttf").write_bytes(b"font")

    assert _select_system_fonts(tmp_path, {"Microsoft YaHei", "Segoe UI"}) == []
    assert [path.name for path in _select_system_fonts(tmp_path, set())] == ["msyh.ttc", "segoeui.ttf"]
    # 只要组内任一字体族可用就整组跳过（CJK 覆盖字体不重复注册）
    assert [path.name for path in _select_system_fonts(tmp_path, {"Noto Sans SC"})] == ["segoeui.ttf"]
