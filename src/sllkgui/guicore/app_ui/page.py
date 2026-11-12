"""预览应用页面基类：统一页面外壳、分区卡片与多语言入口。

``apps/*/gui/main.py`` 原先各自抄了一份同样的脚手架——外层滚动区、卡片标题
字号、把控件按行左对齐排布的循环——十份几乎逐字相同。本模块把它收成
:class:`CPreviewPage`，子类只声明 ``slug`` 并实现 :meth:`CPreviewPage.sections`。

用法::

    from sllkgui.guicore import CPreviewPage

    class ButtonPreviewPage(CPreviewPage):
        slug = "button_preview"   # 语言命名空间 app.button_preview
        columns = 4               # 分区内默认每行放 4 个控件

        @classmethod
        def sections(cls, page, window):
            return [(cls.tr("group_default"), [button_a, button_b], 4)]

    PAGE = ButtonPreviewPage

为什么钩子都是 ``classmethod``：页面协议（``PAGE``）允许模块暴露「类」或「实例」，
加载器按 ``PAGE.load_page(window)`` 调用；``PAGE`` 是类时 ``self`` 拿到的是主窗口，
而非页面对象。用类方法就不依赖实例状态，两种写法都能正常装配。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from sllkgui.appcore import AppSettings, Language
from sllkgui.guicore.custom_ui import CCard, CScrollArea, CScrollTop

__all__ = ["CPreviewPage"]

#: 卡片外边距（左、上、右、下），与 Fluent 卡片的内边距一致
_CARD_MARGINS = (12, 10, 12, 12)
#: 卡片标题与内容之间、行与行之间的间距
_CARD_SPACING = 8
#: 页面内容区外边距与分区之间的间距
_CONTENT_MARGINS = (6, 6, 6, 6)
_CONTENT_SPACING = 6


class CPreviewPage:
    """预览页装配基类：拼页面外壳，再按 :meth:`sections` 的结果填分区卡片。"""

    #: 应用标识，同时用于语言命名空间与页面 objectName（如 ``button_preview``）
    slug: ClassVar[str] = ""

    #: 页面 objectName；留空时按 ``slug`` 推导（``button_preview`` → ``buttonPreviewPage``）
    page_object: ClassVar[str] = ""

    #: 分区内默认每行控件数，条目自带列数时以条目为准
    columns: ClassVar[int] = 3

    #: 分区标题字号档位：``"subtitle"``（默认）或 ``"title"``
    title_scale: ClassVar[str] = "subtitle"

    #: 是否在滚动区挂「回到顶部」浮动按钮
    scroll_top: ClassVar[bool] = False

    #: 插件 Surface 注入的翻译函数：``(key, default) -> str``；为空时走 Language
    _translator: ClassVar[Any] = None

    # ------------------------------------------------------------------
    # 语言
    # ------------------------------------------------------------------
    @classmethod
    def lang_namespace(cls) -> str:
        """返回本页的语言命名空间，如 ``app.button_preview``。"""
        return f"app.{cls.slug}" if cls.slug else ""

    @classmethod
    def tr(cls, key: str, default: str | None = None) -> str:
        """优先用插件注入的翻译函数；否则在 ``app.<slug>`` 命名空间内取文案。"""
        fallback = default if default is not None else key
        translator = getattr(cls, "_translator", None)
        if translator is not None:
            try:
                return str(translator(key, fallback))
            except Exception:  # noqa: BLE001 - 翻译失败回落到基座语言表
                pass
        return str(Language.resolve(f"{cls.lang_namespace()}.{key}", fallback))

    # ------------------------------------------------------------------
    # 标识与排版基元
    # ------------------------------------------------------------------
    @classmethod
    def object_name(cls) -> str:
        """返回页面 objectName，须与清单 ``config.yml`` 的 ``page_object`` 一致。"""
        if cls.page_object:
            return cls.page_object
        head, *rest = cls.slug.split("_")
        return f"{head}{''.join(word[:1].upper() + word[1:] for word in rest)}Page"

    @classmethod
    def title_font(cls) -> QFont:
        """分区标题字体：半粗体，字号取 ``AppSettings`` 的标题档位。"""
        size = AppSettings.title_size if cls.title_scale == "title" else AppSettings.subtitle_size
        font = QFont(AppSettings.family, size)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    @classmethod
    def title_label(cls, text: str) -> QLabel:
        """构造分区标题标签。"""
        label = QLabel(text)
        label.setFont(cls.title_font())
        return label

    @classmethod
    def fixed(cls, widget: QWidget, width: int) -> QWidget:
        """给控件一个稳定的演示宽度（否则 fluid 控件会铺满整行）。"""
        widget.setFixedWidth(width)
        return widget

    # ------------------------------------------------------------------
    # 卡片
    # ------------------------------------------------------------------
    @classmethod
    def card(cls, title: str, content: QWidget) -> CCard:
        """单内容卡片：标题 + 一个控件。"""
        card = CCard()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(QMargins(*_CARD_MARGINS))
        layout.setSpacing(_CARD_SPACING)
        title_label = cls.title_label(title)
        # 卡片被同行拉高时，标题不能跟着纵向膨胀，否则内容被推到底部。
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(title_label)
        layout.addWidget(content, 1)
        return card

    @classmethod
    def section_card(cls, title: str, widgets: Sequence[QWidget], columns: int | None = None) -> CCard:
        """多控件卡片：标题 + 按 ``columns`` 分行的控件，行内左对齐。"""
        card = CCard()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(QMargins(*_CARD_MARGINS))
        layout.setSpacing(_CARD_SPACING)
        title_label = cls.title_label(title)
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(title_label)

        step = max(1, int(columns or cls.columns))
        for start in range(0, len(widgets), step):
            row = QHBoxLayout()
            row.setSpacing(8)
            for widget in widgets[start : start + step]:
                row.addWidget(widget, 0, Qt.AlignLeft | Qt.AlignVCenter)
            row.addStretch()
            layout.addLayout(row)
        layout.addStretch(1)
        return card

    # ------------------------------------------------------------------
    # 子类实现点
    # ------------------------------------------------------------------
    @classmethod
    def sections(cls, page: QWidget, window: Any) -> Sequence[Any]:
        """返回页面分区列表（子类必须实现）。

        每个条目可以是下列三种写法之一：

        * ``(标题, 控件)``——一张卡片放一个控件；
        * ``(标题, [控件, ...], 每行列数)``——卡片内按行左对齐排布；
        * 现成的 ``QWidget``——原样放进内容区（分区内部已自定义装配时用）。

        ``page`` 是正在装配的页面容器（需要往页面挂浮动组件、以页面为父对象时用），
        ``window`` 是主窗口（需要弹通知、切换栏目时用）。
        """
        raise NotImplementedError(f"{cls.__name__} 未实现 sections()")

    @classmethod
    def card_for(cls, item: Any, page: QWidget, window: Any) -> QWidget:
        """把单个分区条目渲染成控件；分区结构特殊时可整段覆写。"""
        if isinstance(item, QWidget):
            return item
        if len(item) == 3:
            title, widgets, columns = item
            return cls.section_card(title, widgets, columns)
        title, content = item
        return cls.card(title, content)

    # ------------------------------------------------------------------
    # 页面外壳
    # ------------------------------------------------------------------
    @classmethod
    def build(cls, window: Any) -> QWidget:
        """装配页面外壳并返回页面控件。"""
        page = QWidget()
        page.setObjectName(cls.object_name())
        window.ui.load_pages.pages.addWidget(page)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(QMargins(0, 0, 0, 0))
        outer.setSpacing(0)

        scroller = CScrollArea()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(QMargins(*_CONTENT_MARGINS))
        content_layout.setSpacing(_CONTENT_SPACING)
        scroller.setWidget(content)
        scroller.setWidgetResizable(True)
        outer.addWidget(scroller)

        if cls.scroll_top:
            CScrollTop(scroller).raise_()

        for item in cls.sections(page, window):
            content_layout.addWidget(cls.card_for(item, page, window))
        content_layout.addStretch()
        return page

    @classmethod
    def load_page(cls, window: Any) -> QWidget:
        """页面协议入口：加载器以 ``PAGE.load_page(window)`` 调用。"""
        return cls.build(window)
