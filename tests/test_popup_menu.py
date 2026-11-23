"""自绘弹出菜单：布局、键盘、鼠标、边界与样式。"""

from __future__ import annotations

from sllkgui.guicore.custom_ui.menu import CPopupMenu, MenuItem, MenuStyle


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


def test_menu_items_and_separators(qapp):
    menu = CPopupMenu(_items())
    labels = [item.label for item in menu.items()]
    assert labels[0] == "打开剪贴板面板"
    assert labels[2] == ""
    assert menu.items()[2].separator
    assert [child.label for child in menu.items()[3].items] == ["开始专注", "暂停"]


def test_popup_shows_root_panel_and_stays_on_screen(qapp):
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


def test_keyboard_skips_disabled_and_wraps(qapp):
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


def test_keyboard_opens_and_closes_submenu(qapp):
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


def test_activate_emits_triggered_and_closes(qapp):
    seen: list[str] = []
    menu = _open()
    menu.triggered.connect(lambda item: seen.append(item.key))
    try:
        menu.activate_active()
        assert seen == ["clip"]
        assert menu.is_open() is False
    finally:
        menu.dismiss()


def test_disabled_item_is_not_activated(qapp):
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


def test_submenu_flips_left_near_right_edge(qapp):
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


def test_tall_panel_scrolls_into_view(qapp):
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


def test_style_override_changes_palette(qapp):
    menu = CPopupMenu(_items(), style=MenuStyle(background="#102030", text="#ffffff", row_height=40))
    assert menu.colors()["background"] == "#102030"
    assert menu.colors()["text"] == "#ffffff"
    assert menu.style().row_height == 40


def test_mouse_click_triggers_item(qapp):
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


def test_hover_opens_submenu_with_delay(qapp):
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


# ----------------------------------------------------------------------
# §11：勾选态、图标列、亚克力底
# ----------------------------------------------------------------------
def test_checkable_item_toggles_and_emits(qapp):
    items = [MenuItem(label="开机自启", key="auto", checked=False), MenuItem(label="退出", key="quit")]
    menu = _open(items)
    states: list[tuple[str, bool]] = []
    menu.toggled.connect(lambda item, state: states.append((item.key, state)))
    try:
        assert menu.activate_active() is True
        assert items[0].checked is True
        assert states == [("auto", True)]
        assert menu.is_open() is False
    finally:
        menu.dismiss()


def test_checked_item_starts_checked_and_unchecked_starts_empty(qapp):
    items = [MenuItem(label="A", checked=True), MenuItem(label="B", checked=False), MenuItem(label="C")]
    menu = _open(items)
    try:
        assert [item.checked for item in menu.items()] == [True, False, None]
        assert menu.icon_column(0) > 0, "可勾选项必须占用图标列"
    finally:
        menu.dismiss()


def test_disabled_checkable_item_does_not_toggle(qapp):
    items = [MenuItem(label="专注模式", checked=False, disabled=True)]
    menu = _open(items)
    try:
        menu.set_active_index(0)
        assert menu.activate_active() is False
        assert items[0].checked is False
    finally:
        menu.dismiss()


def test_icon_and_check_share_one_column(qapp):
    """有图标/可勾选项时整列留白，其他行文案不会左移。"""
    mixed = CPopupMenu([MenuItem(label="A", icon="icon_home"), MenuItem(label="B", checked=True), MenuItem(label="C")])
    plain = CPopupMenu([MenuItem(label="A"), MenuItem(label="B")])
    assert mixed.icon_column(0) > 0
    assert plain.icon_column(0) == 0


def test_backdrop_is_composited_when_background_translucent(qapp):
    """半透明底色 + 模糊底：面板像素应带上背景色，而不是纯底色。"""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QColor, QPixmap

    menu = CPopupMenu([MenuItem(label="A")], style=MenuStyle(background="#00000080"))
    menu.popup(QPoint(120, 120), above=False, align="left")
    try:
        assert menu.uses_backdrop() is True
        pixmap = QPixmap(40, 40)
        pixmap.fill(QColor("#00ff00"))
        menu._backdrop = pixmap
        menu._backdrop_rect = QRect(menu.pos(), menu.size())
        image = menu.grab().toImage()
        color = image.pixelColor(menu.width() // 2, menu.height() // 2)
        assert color.green() > color.red(), "模糊底应透到面板上"
    finally:
        menu.dismiss()


def test_opaque_style_skips_backdrop(qapp):
    from PySide6.QtCore import QPoint

    menu = CPopupMenu([MenuItem(label="A")], style=MenuStyle(background="#101010"))
    menu.popup(QPoint(120, 120))
    try:
        assert menu.uses_backdrop() is False
        assert menu.backdrop() is None
    finally:
        menu.dismiss()


# ----------------------------------------------------------------------
# 回归：子菜单在指针移动中保持打开 / 锚点定位
# ----------------------------------------------------------------------
def _move(menu, pos):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(pos - menu.pos()),
        QPointF(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    menu.mouseMoveEvent(event)


def test_submenu_survives_pointer_travelling_to_child(qapp):
    """从父行移向子菜单（含箭头、面板边缘）时不能收起子菜单。"""
    from PySide6.QtCore import QPoint

    menu = _open()
    try:
        menu.set_active_index(3)  # 番茄钟
        assert menu.open_active_submenu() is True
        parent_row = menu.row_rect(3)
        parent, child = menu.panel_rects()
        for x in (parent_row.right() - 30, parent_row.right() - 3, child.left() + 6):
            _move(menu, QPoint(x, parent_row.center().y()))
            assert menu.open_depth() == 1, f"移动到 x={x} 时子菜单被关闭"
        _move(menu, menu.row_rect(1, depth=1).center())
        assert menu.open_depth() == 1
        assert menu.active_label() == "暂停"
    finally:
        menu.dismiss()


def test_hovering_another_row_closes_submenu(qapp):

    menu = _open()
    try:
        menu.set_active_index(3)
        menu.open_active_submenu()
        # 悬停到「网络诊断」行（无子菜单）
        _move(menu, menu.row_rect(4).center())
        assert menu.open_depth() == 0
    finally:
        menu.dismiss()


def test_popup_rect_anchor_aligns_and_keeps_gap(qapp):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QGuiApplication

    area = QGuiApplication.primaryScreen().availableGeometry()
    # 图标矩形落在可用区之内，便于验证「右对齐 + 间距」的精确关系
    icon = QRect(area.center().x(), area.center().y(), 24, 24)
    menu = CPopupMenu(_items())
    menu.popup(icon, above=True, align="right", gap=6)
    try:
        panel = menu.panel_rects()[0]
        assert panel.right() == icon.right()
        # QRect.bottom() 是闭区间，gap=6 即面板底边与图标顶部之间留 6px
        assert panel.bottom() == icon.top() - 1 - 6
    finally:
        menu.dismiss()


def test_popup_stays_above_taskbar_when_anchor_inside_it(qapp):
    """右键点在任务栏上时，菜单底边应停在可用区底部，不压住任务栏。"""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QGuiApplication

    area = QGuiApplication.primaryScreen().availableGeometry()
    point = QPoint(area.right() - 30, area.bottom() + 20)
    icon = QRect(point.x() - 12, point.y() - 12, 24, 24)
    menu = CPopupMenu(_items())
    menu.popup(icon, above=True, align="right")
    try:
        panel = menu.panel_rects()[0]
        assert panel.bottom() <= area.bottom(), (panel, area)
        assert area.bottom() - panel.bottom() <= 6, "底边应贴近可用区底部"
    finally:
        menu.dismiss()
