"""数据视图预览页：DataView / PickList / OrderList / Tree / TreeTable / Timeline。"""

from PySide6.QtCore import QMargins
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, Language
from customgui.guicore import (
    CCard,
    CDataView,
    COrderList,
    CPickList,
    CScrollArea,
    CSelectButton,
    CTableColumn,
    CTag,
    CTimeline,
    CTree,
    CTreeTable,
)

_LANG = "app.data_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _products() -> list[dict]:
    return [
        {"name": "Bamboo Watch", "category": "Accessories", "price": 65, "status": "INSTOCK"},
        {"name": "Black Watch", "category": "Accessories", "price": 72, "status": "LOWSTOCK"},
        {"name": "Blue T-Shirt", "category": "Clothing", "price": 29, "status": "INSTOCK"},
        {"name": "Game Controller", "category": "Electronics", "price": 99, "status": "INSTOCK"},
        {"name": "Gaming Set", "category": "Electronics", "price": 299, "status": "LOWSTOCK"},
        {"name": "Gold Phone Case", "category": "Accessories", "price": 12, "status": "OUTOFSTOCK"},
    ]


def _status_tag(row) -> CTag:
    severity = {"INSTOCK": "success", "LOWSTOCK": "warning", "OUTOFSTOCK": "danger"}.get(row.get("status"), "secondary")
    return CTag(str(row.get("status") or ""), severity=severity)


def _template(row: dict) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(10)
    text = QVBoxLayout()
    text.setContentsMargins(0, 0, 0, 0)
    text.setSpacing(2)
    name = QLabel(str(row.get("name") or ""))
    font = QFont(AppSettings.family, AppSettings.text_size)
    font.setWeight(QFont.Weight.DemiBold)
    name.setFont(font)
    category = QLabel(str(row.get("category") or ""))
    category.setStyleSheet("color: palette(mid);")
    text.addWidget(name)
    text.addWidget(category)
    layout.addLayout(text, 1)
    layout.addWidget(QLabel(f"${row.get('price')}"))
    layout.addWidget(_status_tag(row))
    return box


def _data_view_demo() -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    view = CDataView(_products(), _template, layout="list", empty_text=_t("empty"))
    switch = CSelectButton([_t("layout_list"), _t("layout_grid")], index=0)
    switch.selectionChanged.connect(lambda index: view.set_layout("list" if index == 0 else "grid"))
    header = QWidget()
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.addStretch(1)
    header_layout.addWidget(switch)
    view.add_header_widget(header)
    view.setMinimumHeight(320)
    layout.addWidget(view)
    return box


def _pick_order_demo() -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    pick = CPickList(_products()[:3], _products()[3:])
    pick.setMinimumHeight(260)
    order = COrderList(_products())
    order.setMinimumHeight(260)
    left = QVBoxLayout()
    left.setContentsMargins(0, 0, 0, 0)
    left.addWidget(QLabel(_t("picklist")))
    left.addWidget(pick, 1)
    right = QVBoxLayout()
    right.setContentsMargins(0, 0, 0, 0)
    right.addWidget(QLabel(_t("orderlist")))
    right.addWidget(order, 1)
    layout.addLayout(left, 2)
    layout.addLayout(right, 1)
    return box


def _tree_nodes() -> list[dict]:
    return [
        {
            "key": "src",
            "label": "src",
            "icon": "icon_books",
            "children": [
                {"key": "main", "label": "main.py", "icon": "icon_bookmark"},
                {"key": "utils", "label": "utils.py", "icon": "icon_bookmark"},
                {
                    "key": "gui",
                    "label": "gui",
                    "icon": "icon_books",
                    "children": [
                        {"key": "window", "label": "window.py", "icon": "icon_bookmark"},
                        {"key": "theme", "label": "theme.py", "icon": "icon_bookmark"},
                    ],
                },
            ],
        },
        {
            "key": "tests",
            "label": "tests",
            "icon": "icon_books",
            "children": [
                {"key": "test_a", "label": "test_app.py", "icon": "icon_bookmark"},
                {"key": "test_b", "label": "test_ui.py", "icon": "icon_bookmark"},
            ],
        },
        {"key": "readme", "label": "README.md", "icon": "icon_bookmark"},
    ]


def _tree_demo() -> QWidget:
    tree = CTree(_tree_nodes(), selection_mode="checkbox")
    tree.setMinimumHeight(280)
    return tree


def _tree_table_rows() -> list[dict]:
    return [
        {
            "name": "Documents",
            "size": "—",
            "type": "Folder",
            "children": [
                {"name": "Report.pdf", "size": "2.4 MB", "type": "PDF"},
                {"name": "Notes.txt", "size": "12 KB", "type": "Text"},
            ],
        },
        {
            "name": "Images",
            "size": "—",
            "type": "Folder",
            "children": [
                {"name": "avatar.jpg", "size": "86 KB", "type": "JPEG"},
                {"name": "tray.jpg", "size": "54 KB", "type": "JPEG"},
            ],
        },
        {"name": "config.yml", "size": "3 KB", "type": "YAML"},
    ]


def _tree_table_demo() -> QWidget:
    columns = [
        CTableColumn("name", _t("col_name"), 260),
        CTableColumn("size", _t("col_size"), 120, "right"),
        CTableColumn("type", _t("col_type"), 120),
    ]
    table = CTreeTable(columns, _tree_table_rows(), checkbox=True)
    table.setMinimumHeight(300)
    return table


def _timeline_events() -> list[dict]:
    return [
        {"date": "2026-10-01", "title": _t("event_1_title"), "description": _t("event_1_desc"), "severity": "success"},
        {"date": "2026-10-08", "title": _t("event_2_title"), "description": _t("event_2_desc"), "severity": "info"},
        {"date": "2026-10-15", "title": _t("event_3_title"), "description": _t("event_3_desc"), "severity": "warning"},
        {"date": "2026-10-22", "title": _t("event_4_title"), "description": _t("event_4_desc"), "severity": "danger"},
    ]


def _timeline_demo() -> QWidget:
    timeline = CTimeline(_timeline_events(), align="alternate")
    timeline.setMinimumHeight(420)
    return timeline


def _card(title: str, content: QWidget) -> CCard:
    card = CCard()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(QMargins(12, 10, 12, 12))
    layout.setSpacing(8)
    label = QLabel(title)
    font = QFont(AppSettings.family, AppSettings.subtitle_size)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    layout.addWidget(label)
    layout.addWidget(content)
    return card


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("dataPreviewPage")
    window.ui.load_pages.pages.addWidget(page)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(QMargins(0, 0, 0, 0))
    outer.setSpacing(0)

    scroller = CScrollArea()
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(QMargins(6, 6, 6, 6))
    layout.setSpacing(6)
    scroller.setWidget(content)
    scroller.setWidgetResizable(True)
    outer.addWidget(scroller)

    for title, widget in (
        (_t("group_dataview"), _data_view_demo()),
        (_t("group_pick_order"), _pick_order_demo()),
        (_t("group_tree"), _tree_demo()),
        (_t("group_treetable"), _tree_table_demo()),
        (_t("group_timeline"), _timeline_demo()),
    ):
        layout.addWidget(_card(title, widget))
    layout.addStretch()
    return page


class DataPreviewPage:
    """PAGE 协议入口。"""

    def load_page(self):
        _build_page(self)


PAGE = DataPreviewPage

