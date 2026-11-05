"""标题栏 logo 尺寸：按 SVG 原始宽高比缩放，不随容器被拉伸变形。

契约：``QSvgWidget`` 本身会把图稿拉伸填满控件矩形；标题栏的 logo 容器宽度
固定为 ``icon_size``、高度跟随标题栏，两者不相等时方形图标会被压扁。
``fit_logo_size`` 负责先算出等比尺寸再固定控件，本测试锁定该行为。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QApplication

from sllkgui.guicore.window.title_bar.title_bar import fit_logo_size


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _write_svg(tmp_path, width: int, height: int) -> str:
    path = tmp_path / f"logo_{width}x{height}.svg"
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="#1b2b4b"/></svg>',
        encoding="utf-8",
    )
    return str(path)


def _load(tmp_path, width: int, height: int) -> QSvgWidget:
    widget = QSvgWidget()
    widget.load(_write_svg(tmp_path, width, height))
    return widget


def test_square_logo_is_not_squashed(qapp, tmp_path):
    """256x256 的 logo 在 icon_size=32 下必须是 32x32，而不是被容器高度拉伸。"""
    widget = _load(tmp_path, 256, 256)
    size = fit_logo_size(widget, 32)

    assert (size.width(), size.height()) == (32, 32)
    assert (widget.width(), widget.height()) == (32, 32)
    widget.deleteLater()


def test_wide_logo_keeps_aspect_ratio(qapp, tmp_path):
    """横幅型 logo 等比缩放，宽度贴合上限、高度按比例收缩。"""
    widget = _load(tmp_path, 512, 256)
    size = fit_logo_size(widget, 32)

    assert (size.width(), size.height()) == (32, 16)
    widget.deleteLater()


def test_tall_logo_keeps_aspect_ratio(qapp, tmp_path):
    widget = _load(tmp_path, 128, 256)
    size = fit_logo_size(widget, 32)

    assert (size.width(), size.height()) == (16, 32)
    widget.deleteLater()


def test_missing_pixmap_falls_back_to_square(qapp):
    """未加载图稿时退回正方形容器，避免零尺寸。"""
    widget = QSvgWidget()
    size = fit_logo_size(widget, 24)

    assert (size.width(), size.height()) == (24, 24)
    widget.deleteLater()
