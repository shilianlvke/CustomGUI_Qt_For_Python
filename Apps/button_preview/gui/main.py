"""按钮预览页：按 Sakai 按钮页的分组展示 CButton 的全部形态。

分组与 https://sakai.primevue.org/uikit/button 一一对应：
Default / Severities / Text / Outlined / Group / SplitButton / Templating /
Icons / Raised / Rounded / Rounded Icons / Rounded Text / Rounded Outlined / Loading。

页面协议（``PAGE``）由基座以 ``load_page(window)`` 调用，因此 ``self`` 是主窗口，
全部构建逻辑放在模块级函数里。
"""

from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings, Language, Logger
from GuiCore import CButton, CButtonGroup, CCard, CScrollArea, CSplitButton

_LANG = "app.button_preview"

_SEVERITIES = ("primary", "secondary", "success", "info", "warn", "help", "danger", "contrast")

#: 圆角图标类分组：图标 + 语义色（primary 留空）
_ROUND_ICONS = (
    ("icon_check", None),
    ("icon_bookmark", "secondary"),
    ("icon_search", "success"),
    ("icon_users", "info"),
    ("icon_bell", "warn"),
    ("icon_heart", "help"),
    ("icon_close", "danger"),
)

_SPLIT_ITEMS = (
    ("Update", "icon_refresh"),
    ("Delete", "icon_trash"),
    ("Home", "icon_home"),
)


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _severity(value):
    return value or "primary"


# ----------------------------------------------------------------------
# 按钮构造
# ----------------------------------------------------------------------
def _button(**kwargs) -> CButton:
    button = CButton(**kwargs)
    button.clicked.connect(lambda: Logger.info(f"点击按钮: {button.text() or 'icon'}"))
    return button


def _loading_button(**kwargs) -> CButton:
    button = CButton(**kwargs)
    button.clicked.connect(lambda: _run_loading(button))
    return button


def _run_loading(button: CButton) -> None:
    button.set_loading(True)
    Logger.info("按钮进入加载态")
    QTimer.singleShot(1000, lambda: button.set_loading(False))


def _default_buttons():
    disabled = _button(text=_t("btn_disabled"))
    disabled.setEnabled(False)
    return [
        _button(text=_t("btn_submit")),
        disabled,
        _button(text=_t("btn_link"), variant="link"),
    ]


def _severity_buttons():
    return [_button(text=name.title(), severity=name) for name in _SEVERITIES]


def _text_buttons():
    buttons = [_button(text=name.title(), severity=name, variant="text") for name in _SEVERITIES[:-1]]
    buttons.append(_button(text=_t("btn_plain"), variant="text", plain=True))
    return buttons


def _outlined_buttons():
    return [_button(text=name.title(), severity=name, variant="outlined") for name in _SEVERITIES]


def _button_group():
    return CButtonGroup(
        [
            _button(text=_t("btn_save"), icon="icon_check"),
            _button(text=_t("btn_delete"), icon="icon_trash"),
            _button(text=_t("btn_cancel"), icon="icon_close"),
        ]
    )


def _split_buttons():
    buttons = []
    for name in _SEVERITIES:
        split = CSplitButton(_t("btn_save"), list(_SPLIT_ITEMS), severity=name)
        split.clicked.connect(lambda: Logger.info("点击分体按钮主操作"))
        split.actionTriggered.connect(lambda action: Logger.info(f"点击分体按钮菜单: {action}"))
        buttons.append(split)
    return buttons


def _templating_buttons():
    # Sakai 原页用 logo 图片占位，这里用图标 + 文字复刻同样的内容排布
    return [
        _button(icon="icon_star_fill"),
        _button(text="PrimeVue", icon="icon_star_fill", variant="outlined", severity="success"),
    ]


def _icon_buttons():
    return [
        _button(icon="icon_star_fill"),
        _button(text="Bookmark", icon="icon_bookmark"),
        _button(text="Bookmark", icon="icon_bookmark", icon_pos="right"),
    ]


def _raised_buttons():
    return [_button(text=name.title(), severity=name, raised=True) for name in _SEVERITIES]


def _rounded_buttons():
    return [_button(text=name.title(), severity=name, rounded=True) for name in _SEVERITIES]


def _round_icon_buttons(variant: str):
    buttons = []
    for icon, severity in _ROUND_ICONS:
        kwargs = {"icon": icon, "rounded": True, "severity": _severity(severity)}
        if variant != "solid":
            kwargs["variant"] = variant
        if variant == "text":
            kwargs["raised"] = True
        buttons.append(_button(**kwargs))
    return buttons


def _loading_buttons():
    return [
        _loading_button(text="Search", icon="icon_search"),
        _loading_button(text="Search", icon="icon_search", icon_pos="right"),
        _loading_button(icon="icon_search"),
        _loading_button(text="Search"),
    ]


def _sections():
    return [
        (_t("group_default"), _default_buttons(), 4),
        (_t("group_severities"), _severity_buttons(), 4),
        (_t("group_text"), _text_buttons(), 4),
        (_t("group_outlined"), _outlined_buttons(), 4),
        (_t("group_group"), [_button_group()], 1),
        (_t("group_split"), _split_buttons(), 4),
        (_t("group_templating"), _templating_buttons(), 4),
        (_t("group_icons"), _icon_buttons(), 4),
        (_t("group_raised"), _raised_buttons(), 4),
        (_t("group_rounded"), _rounded_buttons(), 4),
        (_t("group_rounded_icons"), _round_icon_buttons("solid"), 4),
        (_t("group_rounded_text"), _round_icon_buttons("text"), 4),
        (_t("group_rounded_outlined"), _round_icon_buttons("outlined"), 4),
        (_t("group_loading"), _loading_buttons(), 4),
    ]


# ----------------------------------------------------------------------
# 页面装配
# ----------------------------------------------------------------------
def _section_card(title: str, widgets, columns: int = 4) -> CCard:
    card = CCard()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(QMargins(12, 10, 12, 12))
    layout.setSpacing(8)

    label = QLabel(title)
    font = QFont(AppSettings.family, AppSettings.subtitle_size)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    layout.addWidget(label)

    # 按行分批，行内左对齐排列（对齐 Sakai 的 flex-wrap 手感，避免网格列被拉宽）
    for start in range(0, len(widgets), columns):
        row = QHBoxLayout()
        row.setSpacing(8)
        for widget in widgets[start : start + columns]:
            row.addWidget(widget, 0, Qt.AlignLeft | Qt.AlignVCenter)
        row.addStretch()
        layout.addLayout(row)
    return card


def _build_page(window) -> QWidget:
    page = QWidget()
    page.setObjectName("buttonPreviewPage")
    window.ui.load_pages.pages.addWidget(page)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(QMargins(0, 0, 0, 0))
    outer.setSpacing(0)

    scroller = CScrollArea()
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(QMargins(6, 6, 6, 6))
    content_layout.setSpacing(6)
    scroller.setWidget(content)
    scroller.setWidgetResizable(True)
    outer.addWidget(scroller)

    for title, widgets, columns in _sections():
        content_layout.addWidget(_section_card(title, widgets, columns))
    content_layout.addStretch()
    return page


class ButtonPreviewPage:
    """PAGE 协议入口：``load_page(window)`` 的 self 是主窗口。"""

    def load_page(self):
        _build_page(self)


PAGE = ButtonPreviewPage
