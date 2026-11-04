"""表格预览页：按 Sakai 的 Table 页展示过滤、冻结列、行展开与分组。"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from customgui.guicore import CDataTable, CInputText, CPreviewPage, CTableColumn


class TablePreviewPage(CPreviewPage):
    """PAGE 协议入口：四种表格形态各占一张卡片。"""

    slug = "table_preview"

    @classmethod
    def _severity(cls, value, row) -> tuple[str, str] | None:
        if value == "INSTOCK":
            return "success", cls.tr("status_instock")
        if value == "LOWSTOCK":
            return "warning", cls.tr("status_lowstock")
        if value == "OUTOFSTOCK":
            return "danger", cls.tr("status_outofstock")
        return None

    @staticmethod
    def _products() -> list[dict]:
        return [
            {"name": "Bamboo Watch", "category": "Accessories", "price": 65, "rating": 5, "status": "INSTOCK"},
            {"name": "Black Watch", "category": "Accessories", "price": 72, "rating": 4, "status": "LOWSTOCK"},
            {"name": "Blue T-Shirt", "category": "Clothing", "price": 29, "rating": 5, "status": "INSTOCK"},
            {"name": "Bracelet", "category": "Accessories", "price": 15, "rating": 4, "status": "OUTOFSTOCK"},
            {"name": "Brown Purse", "category": "Accessories", "price": 120, "rating": 3, "status": "LOWSTOCK"},
            {"name": "Chakra Bracelet", "category": "Accessories", "price": 9, "rating": 5, "status": "INSTOCK"},
            {"name": "Galaxy Earrings", "category": "Accessories", "price": 34, "rating": 4, "status": "INSTOCK"},
            {"name": "Game Controller", "category": "Electronics", "price": 99, "rating": 5, "status": "INSTOCK"},
            {"name": "Gaming Set", "category": "Electronics", "price": 299, "rating": 3, "status": "LOWSTOCK"},
            {"name": "Gold Phone Case", "category": "Accessories", "price": 12, "rating": 4, "status": "OUTOFSTOCK"},
            {"name": "Green Earbuds", "category": "Electronics", "price": 89, "rating": 5, "status": "INSTOCK"},
            {"name": "Green Phone Case", "category": "Accessories", "price": 15, "rating": 4, "status": "INSTOCK"},
            {"name": "Yellow Stone", "category": "Clothing", "price": 45, "rating": 4, "status": "LOWSTOCK"},
        ]

    @classmethod
    def _columns(cls) -> list[CTableColumn]:
        return [
            CTableColumn("name", cls.tr("col_name"), 180, frozen=True),
            CTableColumn("category", cls.tr("col_category"), 130),
            CTableColumn("price", cls.tr("col_price"), 110, "right", formatter=lambda value, _row: f"${value}"),
            CTableColumn("rating", cls.tr("col_rating"), 100, "center", formatter=lambda value, _row: "★" * int(value)),
            CTableColumn("status", cls.tr("col_status"), 140, "center", tag=cls._severity),
        ]

    @classmethod
    def _filter_demo(cls) -> QWidget:
        table = CDataTable(cls._columns(), cls._products(), page_size=5)
        table.setMinimumHeight(320)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        search = CInputText(placeholder=cls.tr("search_placeholder"), icon="icon_search")
        search.textChanged.connect(table.set_filter)
        layout.addWidget(search)
        layout.addWidget(table, 1)
        return box

    @classmethod
    def _frozen_demo(cls) -> QWidget:
        table = CDataTable(cls._columns(), cls._products(), page_size=5, frozen_columns=1, striped=True)
        table.setMinimumHeight(300)
        return table

    @classmethod
    def _expand_demo(cls) -> QWidget:
        table = CDataTable(cls._columns(), cls._products(), page_size=5)
        table.setMinimumHeight(300)

        def detail(record: dict) -> QWidget:
            label = QLabel(
                f"{record.get('name')} · {record.get('category')} · ${record.get('price')} · "
                f"{cls.tr('rating')} {record.get('rating')}"
            )
            label.setWordWrap(True)
            label.setStyleSheet("padding: 6px 12px; color: palette(text); background: transparent;")
            return label

        table.set_row_detail_provider(detail)
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        hint = QLabel(cls.tr("hint_expand"))
        hint.setStyleSheet("color: palette(midlight);")
        layout.addWidget(hint)
        layout.addWidget(table, 1)
        return box

    @classmethod
    def _group_demo(cls) -> QWidget:
        table = CDataTable(cls._columns(), cls._products(), page_size=0, paginator=False, group_by="category")
        table.setMinimumHeight(360)
        return table

    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_filter"), cls._filter_demo()),
            (cls.tr("group_frozen"), cls._frozen_demo()),
            (cls.tr("group_expand"), cls._expand_demo()),
            (cls.tr("group_grouping"), cls._group_demo()),
        ]


PAGE = TablePreviewPage
