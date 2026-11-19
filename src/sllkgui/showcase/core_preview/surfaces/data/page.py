"""数据展示预览页：DataView、穿梭 / 排序列表、树、树形表格与时间线。

对应清单里的 ``data`` Surface。五个分区各自展示一种"数据组织形态"，
让主数据区（DataView）与层级 / 时序数据（Tree / TreeTable / Timeline）
在同一页里可对照。
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sllkgui.appcore import ColorPalette
from sllkgui.guicore import (
    CDataView,
    COrderList,
    CPickList,
    CPreviewPage,
    CSelectButton,
    CTableColumn,
    CTimeline,
    CTree,
    CTreeTable,
)

_FILES: list[dict] = [
    {"name": "设计规范.fig", "type": "Figma", "size": "12.4 MB"},
    {"name": "接口文档.pdf", "type": "PDF", "size": "3.1 MB"},
    {"name": "组件清单.xlsx", "type": "Excel", "size": "486 KB"},
    {"name": "主题预览.png", "type": "Image", "size": "1.8 MB"},
    {"name": "发布说明.md", "type": "Markdown", "size": "24 KB"},
    {"name": "构建产物.zip", "type": "Archive", "size": "88.2 MB"},
]


class DataPreviewPage(CPreviewPage):
    """PAGE 协议入口：五种数据视图各占一张卡片。"""

    slug = "data_preview"
    columns = 2

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    @classmethod
    def _item(cls, row: dict) -> QWidget:
        """DataView 条目模板：名称 + 「类型 · 大小」副标题。"""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        name = QLabel(str(row.get("name", "")))
        name.setStyleSheet(f"color: {ColorPalette.custom_text_foreground}; font-weight: 600;")
        meta = QLabel(f"{row.get('type', '')} · {row.get('size', '')}")
        meta.setStyleSheet(f"color: {ColorPalette.custom_text_description};")

        layout.addWidget(name)
        layout.addWidget(meta)
        return box

    @classmethod
    def _nodes(cls) -> list[dict]:
        return [
            {
                "label": cls.tr("col_name"),
                "key": "docs",
                "children": [
                    {
                        "label": "规范",
                        "key": "docs/spec",
                        "children": [
                            {"label": "色彩.md", "key": "docs/spec/color"},
                            {"label": "间距.md", "key": "docs/spec/spacing"},
                        ],
                    },
                    {"label": "接口", "key": "docs/api"},
                ],
            },
            {
                "label": "资源",
                "key": "assets",
                "children": [
                    {"label": "图标", "key": "assets/icons"},
                    {"label": "字体", "key": "assets/fonts"},
                ],
            },
            {"label": "构建", "key": "build", "disabled": True},
        ]

    @classmethod
    def _tree_rows(cls) -> list[dict]:
        return [
            {
                "name": "src",
                "type": "目录",
                "size": "—",
                "children": [
                    {
                        "name": "guicore",
                        "type": "目录",
                        "size": "—",
                        "children": [
                            {"name": "button.py", "type": "Python", "size": "18 KB"},
                            {"name": "table.py", "type": "Python", "size": "26 KB"},
                        ],
                    },
                    {"name": "appcore", "type": "目录", "size": "—"},
                ],
            },
            {"name": "README.md", "type": "Markdown", "size": "9 KB"},
            {"name": "pyproject.toml", "type": "TOML", "size": "2 KB"},
        ]

    @classmethod
    def _events(cls) -> list[dict]:
        return [
            {
                "date": "2026-01",
                "title": cls.tr("event_1_title"),
                "description": cls.tr("event_1_desc"),
                "severity": "info",
            },
            {
                "date": "2026-04",
                "title": cls.tr("event_2_title"),
                "description": cls.tr("event_2_desc"),
                "severity": "success",
            },
            {
                "date": "2026-08",
                "title": cls.tr("event_3_title"),
                "description": cls.tr("event_3_desc"),
                "severity": "warning",
            },
            {
                "date": "2026-11",
                "title": cls.tr("event_4_title"),
                "description": cls.tr("event_4_desc"),
                "severity": "success",
            },
        ]

    # ------------------------------------------------------------------
    # 分区
    # ------------------------------------------------------------------
    @classmethod
    def _dataview_demo(cls) -> QWidget:
        view = CDataView(
            _FILES,
            cls._item,
            layout="grid",
            columns=2,
            empty_text=cls.tr("empty"),
        )
        view.setMinimumHeight(260)

        toggle = CSelectButton([cls.tr("layout_grid"), cls.tr("layout_list")], index=0, size="sm")
        toggle.setFixedWidth(140)
        toggle.selectionChanged.connect(lambda index: view.set_layout("grid" if index == 0 else "list"))

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(toggle, 0)
        layout.addWidget(view, 1)
        return box

    @classmethod
    def _pick_order_demo(cls) -> QWidget:
        pick = CPickList(
            source=[cls.tr("col_name"), cls.tr("col_type"), cls.tr("col_size")],
            target=[cls.tr("col_name")],
        )
        order = COrderList(items=[cls.tr("col_name"), cls.tr("col_type"), cls.tr("col_size")])

        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(pick, 1)
        layout.addWidget(order, 1)
        return box

    @classmethod
    def _tree_demo(cls) -> QWidget:
        tree = CTree(cls._nodes(), selection_mode="checkbox")
        tree.setMinimumHeight(240)
        return tree

    @classmethod
    def _treetable_demo(cls) -> QWidget:
        columns = [
            CTableColumn("name", cls.tr("col_name"), 220),
            CTableColumn("type", cls.tr("col_type"), 120, "center"),
            CTableColumn("size", cls.tr("col_size"), 100, "right"),
        ]
        table = CTreeTable(columns, cls._tree_rows(), checkbox=False)
        table.setMinimumHeight(240)
        return table

    @classmethod
    def _timeline_demo(cls) -> QWidget:
        timeline = CTimeline(cls._events(), align="left", layout="vertical")
        timeline.setMinimumHeight(260)
        return timeline

    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_dataview"), cls._dataview_demo()),
            (cls.tr("group_pick_order"), cls._pick_order_demo()),
            (cls.tr("group_tree"), cls._tree_demo()),
            (cls.tr("group_treetable"), cls._treetable_demo()),
            (cls.tr("group_timeline"), cls._timeline_demo()),
        ]


def build(ctx):
    """Gallery Surface 工厂：注入插件上下文与翻译表。"""
    from ...common import bind_context

    bind_context(ctx)
    DataPreviewPage._translator = lambda key, default=None: ctx.text(f"data.{key}", default)
    page = DataPreviewPage.build(ctx.parent_window())
    ctx.event("surface.ready", {"surface": "data"})
    return page
