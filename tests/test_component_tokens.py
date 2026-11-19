"""组件补齐后的契约：几何参数生效、颜色仍取自主题、缓存有上限。

这些断言刻意只覆盖"参数是否落到控件上"，不比对像素——视觉回归由
``docs/MANUAL_QA.md`` 与展厅负责。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_elided_label_elides_and_keeps_full_tooltip(qapp):
    from sllkgui.guicore import CElidedLabel

    label = CElidedLabel("a-very-long-plugin-name-that-does-not-fit.txt")
    label.resize(60, 20)
    label.show()
    QTest.qWait(10)

    assert label.full_text().endswith(".txt")
    assert label.text() != label.full_text()
    assert label.toolTip() == label.full_text()
    label.deleteLater()


def test_elided_label_without_truncation_has_no_tooltip(qapp):
    from sllkgui.guicore import CElidedLabel

    label = CElidedLabel("short")
    label.resize(240, 20)
    label.show()
    QTest.qWait(10)

    assert label.text() == "short"
    assert label.toolTip() == ""
    label.deleteLater()


def test_icon_tile_cache_is_bounded(qapp):
    from sllkgui.guicore import CIconTile
    from sllkgui.guicore.custom_ui.display import icon_tile

    assert icon_tile._file_pixmap.cache_info().maxsize == 64
    tile = CIconTile("icon_store", 38)
    assert tile.size().width() == 38
    icon_tile.clear_icon_cache()
    assert icon_tile._file_pixmap.cache_info().currsize == 0
    tile.deleteLater()


def test_metric_card_updates_value(qapp):
    from sllkgui.guicore import CMetricCard

    card = CMetricCard("已安装", 3)
    assert card.value() == "3"
    card.set_value(12)
    assert card.value() == "12"
    card.deleteLater()


def test_surface_panel_accepts_geometry_overrides(qapp):
    from sllkgui.guicore import CSurfacePanel

    panel = CSurfacePanel(radius=12)
    panel.set_surface(radius=6)
    assert panel.sizePolicy().horizontalPolicy().name == "Expanding"
    panel.deleteLater()


def test_chip_supports_compact_accent_variant(qapp):
    from sllkgui.guicore import CChip

    chip = CChip("内置", height=20, font_pixel_size=10, tone="accent")
    assert chip.height() == 20
    assert chip.font().pixelSize() == 10
    assert chip.sizeHint().height() == 20
    chip.deleteLater()


def test_side_nav_item_height_applies(qapp):
    from sllkgui.guicore import CSideNav, CSideNavGroup, CSideNavItem

    nav = CSideNav(
        [CSideNavGroup("", (CSideNavItem("a", "已安装"), CSideNavItem("b", "发现")))],
        item_height=56,
    )
    assert all(button.height() == 56 for button in nav._buttons)
    nav.deleteLater()


def test_text_with_role_maps_to_semantic_size(qapp):
    from sllkgui.guicore import CText

    title = CText.with_role("title", "插件管理")
    metric = CText.with_role("metric", "12")
    assert title.font().pixelSize() == 18
    assert title.font().weight().name == "DemiBold"
    assert metric.font().pixelSize() == 22
    assert "Cascadia" in metric.font().families()[0] or metric.is_mono()
    title.deleteLater()
    metric.deleteLater()


def test_elided_label_default_mode_is_right(qapp):
    from sllkgui.guicore import CElidedLabel

    label = CElidedLabel("x" * 200)
    assert label._mode == Qt.TextElideMode.ElideRight
    label.deleteLater()
