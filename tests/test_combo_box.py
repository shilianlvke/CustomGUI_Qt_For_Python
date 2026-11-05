"""``CComboBox`` 重写后的行为契约。

重点回归用户反馈过的三类问题：

1. 弹层必须挂在 **top-level window** 上（否则被页面/滚动区裁剪，且深色
   主题下露黑角）；
2. 鼠标滚轮 **不得** 改变选中项（原生 ``QComboBox`` 的老毛病）；
3. 尺寸必须可伸展（原生实现是 ``setFixedSize``，且只能显示 3 项）。
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from sllkgui.guicore import CComboBox


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _wheel(widget: QWidget, delta: int = -120) -> QWheelEvent:
    center = QPointF(widget.width() / 2, widget.height() / 2)
    global_center = QPointF(widget.mapToGlobal(QPoint(int(center.x()), int(center.y()))))
    return QWheelEvent(
        center,
        global_center,
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


@pytest.fixture()
def host(qapp):
    """一个真实的顶层窗口，模拟弹层的真实父级。"""
    window = QWidget()
    window.resize(640, 480)
    combo = CComboBox(items=["简体中文", "English", "日本語", "繁體中文"], parent=window)
    combo.move(40, 40)
    combo.resize(200, combo.height())
    window.show()
    QApplication.processEvents()
    yield window, combo
    combo.hidePopup()
    window.close()
    window.deleteLater()
    QApplication.processEvents()


# --------------------------------------------------------------------------
# 1. 滚轮不误改选择
# --------------------------------------------------------------------------
def test_wheel_does_not_change_selection(host):
    """滚动页面时鼠标经过下拉框，选中项必须保持不变。"""
    _window, combo = host
    combo.setCurrentIndex(0)
    before = combo.currentIndex()
    combo.wheelEvent(_wheel(combo, -120))
    combo.wheelEvent(_wheel(combo, 120))
    assert combo.currentIndex() == before


def test_wheel_event_is_ignored(host):
    """``wheelEvent`` 必须 ``ignore()``，把滚动交还给父级滚动区域。"""
    _window, combo = host
    event = _wheel(combo)
    combo.wheelEvent(event)
    assert not event.isAccepted()


# --------------------------------------------------------------------------
# 2. 弹层父级与生命周期
# --------------------------------------------------------------------------
def test_popup_is_child_of_top_level_window(host):
    """弹层父级必须是顶层窗口，而不是页面容器——这是不露黑角、不被裁剪的前提。"""
    window, combo = host
    combo.showPopup()
    QApplication.processEvents()
    popup = combo._popup  # noqa: SLF001 - 断言内部结构是契约的一部分
    assert popup is not None
    assert popup.parentWidget() is window
    assert popup.isVisible()


def test_popup_closes_on_escape(host):
    _window, combo = host
    combo.showPopup()
    QApplication.processEvents()
    assert combo._popup.isVisible()  # noqa: SLF001
    combo.keyPressEvent(_key_event(Qt.Key.Key_Escape))
    assert not combo._popup.isVisible()  # noqa: SLF001


def test_popup_closes_when_window_resized(host):
    window, combo = host
    combo.showPopup()
    QApplication.processEvents()
    assert combo._popup.isVisible()  # noqa: SLF001
    window.resize(700, 500)
    QApplication.processEvents()
    assert not combo._popup.isVisible()  # noqa: SLF001


def _key_event(key):
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


# --------------------------------------------------------------------------
# 3. 尺寸可伸展
# --------------------------------------------------------------------------
def test_size_policy_is_expanding(host):
    """横向可伸展（原生实现是 setFixedSize，无法自适应容器宽度）。"""
    _window, combo = host
    policy = combo.sizePolicy()
    assert policy.horizontalPolicy() == policy.Policy.Expanding
    assert policy.verticalPolicy() == policy.Policy.Fixed
    combo.resize(320, combo.height())
    assert combo.width() == 320


def test_max_visible_items_is_configurable(qapp):
    """显示条数可配置（原生实现硬编码 3 项）。"""
    assert CComboBox().maxVisibleItems() == 10
    combo = CComboBox(max_visible_items=5)
    assert combo.maxVisibleItems() == 5
    combo.setMaxVisibleItems(8)
    assert combo.maxVisibleItems() == 8


# --------------------------------------------------------------------------
# 4. 数据 API 与 QComboBox 语义对齐
# --------------------------------------------------------------------------
def test_data_api_matches_qcombobox_semantics(qapp):
    combo = CComboBox()
    assert combo.count() == 0
    assert combo.currentIndex() == -1
    assert combo.currentText() == ""

    combo.addItem("甲", 1)
    combo.addItem("乙", 2)
    assert combo.count() == 2
    assert combo.currentIndex() == 0  # 首个项自动选中
    assert combo.currentText() == "甲"
    assert combo.currentData() == 1

    combo.setCurrentIndex(1)
    assert combo.currentText() == "乙"
    assert combo.findText("甲") == 0
    assert combo.findData(2) == 1
    assert combo.findText("不存在") == -1

    combo.removeItem(0)
    assert combo.count() == 1
    assert combo.currentText() == "乙"

    combo.clear()
    assert combo.count() == 0
    assert combo.currentIndex() == -1


def test_current_index_signals(qapp):
    combo = CComboBox(items=["a", "b", "c"])
    seen: list[tuple[int, str]] = []
    combo.currentIndexChanged.connect(lambda index: seen.append(("index", index)))
    combo.currentTextChanged.connect(lambda text: seen.append(("text", text)))

    combo.setCurrentIndex(2)
    assert ("index", 2) in seen
    assert ("text", "c") in seen

    # 相同索引不重复发信号
    seen.clear()
    combo.setCurrentIndex(2)
    assert seen == []


def test_set_current_index_is_clamped(qapp):
    combo = CComboBox(items=["a", "b"])
    combo.setCurrentIndex(99)
    assert combo.currentIndex() == 1
    combo.setCurrentIndex(-5)
    assert combo.currentIndex() == -1


# --------------------------------------------------------------------------
# 5. 主题切换不崩
# --------------------------------------------------------------------------
def test_theme_switch_repaints_without_error(qapp):
    from sllkgui.appcore import get_theme_manager

    manager = get_theme_manager()
    original = manager.current()
    combo = CComboBox(items=["x", "y"])
    try:
        for name in ("bright", "default"):
            manager.apply(name)
            combo.update()
            combo.showPopup()
            combo.hidePopup()
    finally:
        manager.apply(original)
