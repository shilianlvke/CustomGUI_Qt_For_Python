"""数据视图预览页：DataView / PickList / OrderList / Tree / TreeTable / Timeline。"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings
from customgui.guicore import (
    CDataView,
    COrderList,
    CPickList,
    CPreviewPage,
    CSelectButton,
    CTableColumn,
    CTag,
    CTimeline,
    CTree,
    CTreeTable,
)


class DataPreviewPage(CPreviewPage):
    """PAGE 协议入口：六类数据视图各占一张卡片。"""

    slug = "data_preview"

    @staticmethod
    def _products() -> list[dict]:
        return [
            {"name": "Bamboo Watch", "category": "Accessories", "price": 65, "status": "INSTOCK"},
            {"name": "Black Watch", "category": "Accessories", "price": 72, "status": "LOWSTOCK"},
            {"name": "Blue T-Shirt", "category": "Clothing", "price": 29, "status": "INSTOCK"},
            {"name": "Game Controller", "category": "Electronics", "price": 99, "status": "INSTOCK"},
            {"name": "Gaming Set", "category": "Electronics", "price": 299, "status": "LOWSTOCK"},
            {"name": "Gold Phone Case", "category": "Accessories", "price": 12, "status": "OUTOFSTOCK"},
        ]

    @staticmethod
    def _status_tag(row) -> CTag:
        severity = {"INSTOCK": "success", "LOWSTOCK": "warning", "OUTOFSTOCK": "danger"}.get(row.get("status"), "secondary")
        return CTag(str(row.get("status") or ""), severity=severity)

    @classmethod
    def _template(cls, row: dict) -> QWidget:
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
        layout.addWidget(cls._status_tag(row))
        return box

    @classmethod
    def _data_view_demo(cls) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        view = CDataView(cls._products(), cls._template, layout="list", columns=3, empty_text=cls.tr("empty"))
        switch = CSelectButton([cls.tr("layout_list"), cls.tr("layout_grid")], index=0)
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

    @classmethod
    def _pick_order_demo(cls) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        pick = CPickList(cls._products()[:3], cls._products()[3:])
        pick.setMinimumHeight(260)
        order = COrderList(cls._products())
        order.setMinimumHeight(260)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(QLabel(cls.tr("picklist")))
        left.addWidget(pick, 1)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(QLabel(cls.tr("orderlist")))
        right.addWidget(order, 1)
        layout.addLayout(left, 2)
        layout.addLayout(right, 1)
        return box

    @staticmethod
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

    @classmethod
    def _tree_demo(cls) -> QWidget:
        tree = CTree(cls._tree_nodes(), selection_mode="checkbox")
        tree.setMinimumHeight(280)
        return tree

    @staticmethod
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

    @classmethod
    def _tree_table_demo(cls) -> QWidget:
        columns = [
            CTableColumn("name", cls.tr("col_name"), 260),
            CTableColumn("size", cls.tr("col_size"), 120, "right"),
            CTableColumn("type", cls.tr("col_type"), 120),
        ]
        table = CTreeTable(columns, cls._tree_table_rows(), checkbox=True)
        table.setMinimumHeight(300)
        return table

    @classmethod
    def _timeline_events(cls) -> list[dict]:
        return [
            {"date": "2026-10-01", "title": cls.tr("event_1_title"), "description": cls.tr("event_1_desc"), "severity": "success"},
            {"date": "2026-10-08", "title": cls.tr("event_2_title"), "description": cls.tr("event_2_desc"), "severity": "info"},
            {"date": "2026-10-15", "title": cls.tr("event_3_title"), "description": cls.tr("event_3_desc"), "severity": "warning"},
            {"date": "2026-10-22", "title": cls.tr("event_4_title"), "description": cls.tr("event_4_desc"), "severity": "danger"},
        ]

    @classmethod
    def _timeline_demo(cls) -> QWidget:
        timeline = CTimeline(cls._timeline_events(), align="alternate")
        timeline.setMinimumHeight(420)
        return timeline

    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_dataview"), cls._data_view_demo()),
            (cls.tr("group_pick_order"), cls._pick_order_demo()),
            (cls.tr("group_tree"), cls._tree_demo()),
            (cls.tr("group_treetable"), cls._tree_table_demo()),
            (cls.tr("group_timeline"), cls._timeline_demo()),
        ]


PAGE = DataPreviewPage
