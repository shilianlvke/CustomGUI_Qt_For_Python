"""表格预览页：按 Sakai 的 Table 页展示过滤、冻结列、行展开与分组。"""

from PySide6.QtCore import QMargins
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from customgui.appcore import AppSettings, Language
from customgui.guicore import CCard, CDataTable, CInputText, CScrollArea, CTableColumn

_LANG = "app.table_preview"


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _severity(row) -> tuple[str, str] | None:
    value = row.get("status")
    if value == "INSTOCK":
        return "success", _t("status_instock")
    if value == "LOWSTOCK":
        return "warning", _t("status_lowstock")
    if value == "OUTOFSTOCK":
        return "danger", _t("status_outofstock")
    return None


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


def _columns() -> list[CTableColumn]:
    return [
        CTableColumn("name", _t("col_name"), 180, frozen=True),
        CTableColumn("category", _t("col_category"), 130),
        CTableColumn("price", _t("col_price"), 110, "right", formatter=lambda value, _row: f"${value}"),
        CTableColumn("rating", _t("col_rating"), 100, "center", formatter=lambda value, _row: "★" * int(value)),
        CTableColumn("status", _t("col_status"), 140, "center", tag=_severity),
    ]


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


def _filter_demo() -> QWidget:
    table = CDataTable(_columns(), _products(), page_size=5)
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    search = CInputText(placeholder=_t("search_placeholder"), icon="icon_search")
    search.textChanged.connect(table.set_filter)
    layout.addWidget(search)
    layout.addWidget(table, 1)
    return box


def _frozen_demo() -> QWidget:
    table = CDataTable(_columns(), _products(), page_size=5, frozen_columns=1, striped=True)
    table.setMinimumHeight(300)
    return table


def _expand_demo() -> QWidget:
    table = CDataTable(_columns(), _products(), page_size=5)
    table.setMinimumHeight(300)

    def detail(record: dict) -> QWidget:
        label = QLabel(
            f"{record.get('name')} · {record.get('category')} · ${record.get('price')} · "
            f"{_t('rating')} {record.get('rating')}"
        )
        label.setWordWrap(True)
        return label

    table.set_row_detail_provider(detail)
    return table


def _group_demo() -> QWidget:
    table = CDataTable(_columns(), _products(), page_size=0, paginator=False, group_by="category")
    table.setMinimumHeight(360)
    return table


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("tablePreviewPage")
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
        (_t("group_filter"), _filter_demo()),
        (_t("group_frozen"), _frozen_demo()),
        (_t("group_expand"), _expand_demo()),
        (_t("group_grouping"), _group_demo()),
    ):
        layout.addWidget(_card(title, widget))
    layout.addStretch()
    return page


class TablePreviewPage:
    """PAGE 协议入口。"""

    def load_page(self):
        _build_page(self)


PAGE = TablePreviewPage
