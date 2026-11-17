"""自绘弹出菜单：布局、键盘、鼠标、边界与样式。"""

from __future__ import annotations

import pytest

from sllkgui.guicore.custom_ui.menu import CPopupMenu, MenuItem, MenuStyle


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _items():
    return [
        MenuItem(label="打开剪贴板面板", key="clip"),
        MenuItem(label="立即测速", key="speed"),
        MenuItem(separator=True),
        MenuItem(
            label="番茄钟",
            key="pomodoro",
            items=[MenuItem(label="开始专注", key="start"), MenuItem(label="暂停", key="pause")],
        ),
        MenuItem(label="网络诊断", key="net", items=[MenuItem(label="Ping 测试", key="ping")]),
        MenuItem(separator=True),
        MenuItem(label="专注中 · 剩 12:34", disabled=True),
        MenuItem(separator=True),
        MenuItem(label="显示主窗口", key="show"),
        MenuItem(label="退出", key="quit"),
    ]


def _open(items=None, *, anchor=None, above=True, align="right"):
    from PySide6.QtCore import QPoint

    menu = CPopupMenu(items if items is not None else _items())
    point = anchor if anchor is not None else QPoint(400, 600)
    menu.popup(point, above=above, align=align)
    return menu


def test_menu_items_and_separators(app):
    menu = CPopupMenu(_items())
    labels = [item.label for item in menu.items()]
    assert labels[0] == "打开剪贴板面板"
    assert labels[2] == ""
    assert menu.items()[2].separator
    assert [child.label for child in menu.items()[3].items] == ["开始专注", "暂停"]


def test_popup_shows_root_panel_and_stays_on_screen(app):
    from PySide6.QtGui import QGuiApplication

    area = QGuiApplication.primaryScreen().availableGeometry()
    menu = _open(anchor=area.bottomRight())
    try:
        assert menu.is_open()
        assert menu.panel_count() == 1
        rect = menu.panel_rects()[0]
        assert area.contains(rect), (rect, area)
    finally:
        menu.dismiss()


def test_keyboard_skips_disabled_and_wraps(app):
    menu = _open()
    seen: list[str] = []
    menu.hovered.connect(lambda item: seen.append(item.label))
    try:
        assert menu.active_label() == "打开剪贴板面板"
        menu.move_active(1)
        assert menu.active_label() == "立即测速"
        menu.move_active(1)  # 跳过分隔线，落到「番茄钟」
        assert menu.active_label() == "番茄钟"
        menu.move_active(-1)
        menu.move_active(-1)
        assert menu.active_label() == "打开剪贴板面板"
        menu.move_active(-1)
        assert menu.active_label() == "退出"  # 首尾循环，跳过禁用行
        assert seen[-1] == "退出", "键盘移动也要发 hovered"
    finally:
        menu.dismiss()


def test_keyboard_opens_and_closes_submenu(app):
    menu = _open()
    try:
        menu.move_active(1)
        menu.move_active(1)
        assert menu.open_active_submenu() is True
        assert menu.open_depth() == 1
        assert menu.active_label() == "开始专注"
        assert menu.visible_labels()[1] == ["开始专注", "暂停"]
        assert menu.close_submenu() is True
        assert menu.open_depth() == 0
        assert menu.active_label() == "番茄钟"
    finally:
        menu.dismiss()


def test_activate_emits_triggered_and_closes(app):
    seen: list[str] = []
    menu = _open()
    menu.triggered.connect(lambda item: seen.append(item.key))
    try:
        menu.activate_active()
        assert seen == ["clip"]
        assert menu.is_open() is False
    finally:
        menu.dismiss()


def test_disabled_item_is_not_activated(app):
    seen: list[str] = []
    menu = _open()
    menu.triggered.connect(lambda item: seen.append(item.key))
    try:
        # 直接高亮禁用行（模拟鼠标），激活应被拒绝
        menu.set_active_index(6)
        assert menu.activate_active() is False
        assert seen == []
    finally:
        menu.dismiss()


def test_submenu_flips_left_near_right_edge(app):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication

    area = QGuiApplication.primaryScreen().availableGeometry()
    menu = _open(anchor=QPoint(area.right() - 4, area.bottom() - 4))
    try:
        menu.move_active(1)
        menu.move_active(1)
        menu.open_active_submenu()
        root, child = menu.panel_rects()
        assert menu.panel_count() == 2
        assert child.right() <= root.left() + 1, (root, child)
        assert area.contains(child), (child, area)
    finally:
        menu.dismiss()


def test_tall_panel_scrolls_into_view(app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QKeyEvent

    area = QGuiApplication.primaryScreen().availableGeometry()
    items = [MenuItem(label=f"动作 {index}", key=f"k{index}") for index in range(60)]
    menu = _open(items, anchor=area.bottomRight())
    try:
        assert menu.content_height(0) > menu.visible_height(0), "超屏时应启用滚动"
        menu.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_End, Qt.NoModifier))
        assert menu.scroll_offset(0) > 0
        rect = menu.panel_rects()[0]
        assert area.contains(rect)
    finally:
        menu.dismiss()


def test_style_override_changes_palette(app):
    menu = CPopupMenu(_items(), style=MenuStyle(background="#102030", text="#ffffff", row_height=40))
    assert menu.colors()["background"] == "#102030"
    assert menu.colors()["text"] == "#ffffff"
    assert menu.style().row_height == 40


def test_mouse_click_triggers_item(app):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    seen: list[str] = []
    menu = _open()
    menu.triggered.connect(lambda item: seen.append(item.key))
    try:
        panel = menu.panel_rects()[0]
        # 第一行在面板内边距之后，取行中心做命中测试
        local_y = 5 + 34 // 2
        global_pos = QPoint(panel.center().x(), panel.top() + local_y)
        local_pos = QPointF(global_pos - menu.pos())
        event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            local_pos,
            QPointF(global_pos),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        menu.mouseReleaseEvent(event)
        assert seen == ["clip"]
    finally:
        menu.dismiss()


def test_hover_opens_submenu_with_delay(app):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest

    menu = _open()
    try:
        panel = menu.panel_rects()[0]
        # 第三行是「番茄钟」（两行之后），带子菜单
        local_y = 5 + 34 * 2 + 9 + 34 // 2
        global_pos = QPoint(panel.center().x(), panel.top() + local_y)
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(global_pos - menu.pos()),
            QPointF(global_pos),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        menu.mouseMoveEvent(event)
        assert menu.open_depth() == 0
        QTest.qWait(320)
        assert menu.open_depth() == 1
        assert menu.visible_labels()[1] == ["开始专注", "暂停"]
    finally:
        menu.dismiss()
