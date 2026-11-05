"""按钮预览页：按 Sakai 按钮页的分组展示 CButton 的全部形态。

分组与 https://sakai.primevue.org/uikit/button 一一对应：
Default / Severities / Text / Outlined / Group / SplitButton / Templating /
Icons / Raised / Rounded / Rounded Icons / Rounded Text / Rounded Outlined / Loading。
"""

from PySide6.QtCore import QTimer

from sllkgui.appcore import Logger
from sllkgui.guicore import CButton, CButtonGroup, CPreviewPage, CSplitButton

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

#: 分体按钮的下拉菜单项（None = 分隔线，与 Sakai 的 items 一致）
_SPLIT_ITEMS: list[tuple[str, str | None] | None] = (
    ("Update", "icon_refresh"),
    ("Delete", "icon_close"),
    None,
    ("Home", "icon_home"),
)


class ButtonPreviewPage(CPreviewPage):
    """PAGE 协议入口：全部按钮形态按参考页分组排列。"""

    slug = "button_preview"
    columns = 4
    title_scale = "title"

    # ------------------------------------------------------------------
    # 按钮构造
    # ------------------------------------------------------------------
    @classmethod
    def _button(cls, **kwargs) -> CButton:
        button = CButton(**kwargs)
        button.clicked.connect(lambda: Logger.info(f"点击按钮: {button.text() or 'icon'}"))
        return button

    @classmethod
    def _loading_button(cls, **kwargs) -> CButton:
        button = CButton(**kwargs)
        button.clicked.connect(lambda: cls._run_loading(button))
        return button

    @staticmethod
    def _run_loading(button: CButton) -> None:
        button.set_loading(True)
        Logger.info("按钮进入加载态")
        QTimer.singleShot(1000, lambda: button.set_loading(False))

    @classmethod
    def _default_buttons(cls):
        disabled = cls._button(text=cls.tr("btn_disabled"))
        disabled.setEnabled(False)
        return [
            cls._button(text=cls.tr("btn_submit")),
            disabled,
            cls._button(text=cls.tr("btn_link"), variant="link"),
        ]

    @classmethod
    def _severity_buttons(cls):
        return [cls._button(text=name.title(), severity=name) for name in _SEVERITIES]

    @classmethod
    def _text_buttons(cls):
        buttons = [cls._button(text=name.title(), severity=name, variant="text") for name in _SEVERITIES[:-1]]
        buttons.append(cls._button(text=cls.tr("btn_plain"), variant="text", plain=True))
        return buttons

    @classmethod
    def _outlined_buttons(cls):
        return [cls._button(text=name.title(), severity=name, variant="outlined") for name in _SEVERITIES]

    @classmethod
    def _button_group(cls):
        return CButtonGroup(
            [
                cls._button(text=cls.tr("btn_save"), icon="icon_check"),
                cls._button(text=cls.tr("btn_delete"), icon="icon_trash"),
                cls._button(text=cls.tr("btn_cancel"), icon="icon_close"),
            ]
        )

    @classmethod
    def _split_buttons(cls):
        buttons = []
        for name in _SEVERITIES:
            split = CSplitButton(cls.tr("btn_save"), list(_SPLIT_ITEMS), severity=name)
            split.clicked.connect(lambda: Logger.info("点击分体按钮主操作"))
            split.actionTriggered.connect(lambda action: Logger.info(f"点击分体按钮菜单: {action}"))
            buttons.append(split)
        return buttons

    @classmethod
    def _templating_buttons(cls):
        # Sakai 原页用 1.5rem（24px）的 logo 图片占位，这里用同尺寸图标复刻同样的内容排布
        return [
            cls._button(icon="icon_star_fill", icon_size=24),
            cls._button(text="PrimeVue", icon="icon_star_fill", icon_size=24, variant="outlined", severity="success"),
        ]

    @classmethod
    def _icon_buttons(cls):
        return [
            cls._button(icon="icon_star_fill"),
            cls._button(text="Bookmark", icon="icon_bookmark"),
            cls._button(text="Bookmark", icon="icon_bookmark", icon_pos="right"),
        ]

    @classmethod
    def _raised_buttons(cls):
        return [cls._button(text=name.title(), severity=name, raised=True) for name in _SEVERITIES]

    @classmethod
    def _rounded_buttons(cls):
        return [cls._button(text=name.title(), severity=name, rounded=True) for name in _SEVERITIES]

    @classmethod
    def _round_icon_buttons(cls, variant: str):
        buttons = []
        for icon, severity in _ROUND_ICONS:
            kwargs = {"icon": icon, "rounded": True, "severity": severity or "primary"}
            if variant != "solid":
                kwargs["variant"] = variant
            if variant == "text":
                kwargs["raised"] = True
            buttons.append(cls._button(**kwargs))
        return buttons

    @classmethod
    def _loading_buttons(cls):
        return [
            cls._loading_button(text="Search", icon="icon_search"),
            cls._loading_button(text="Search", icon="icon_search", icon_pos="right"),
            cls._loading_button(icon="icon_search"),
            cls._loading_button(text="Search"),
        ]

    # ------------------------------------------------------------------
    # 页面结构
    # ------------------------------------------------------------------
    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_default"), cls._default_buttons(), 4),
            (cls.tr("group_severities"), cls._severity_buttons(), 4),
            (cls.tr("group_text"), cls._text_buttons(), 4),
            (cls.tr("group_outlined"), cls._outlined_buttons(), 4),
            (cls.tr("group_group"), [cls._button_group()], 1),
            (cls.tr("group_split"), cls._split_buttons(), 4),
            (cls.tr("group_templating"), cls._templating_buttons(), 4),
            (cls.tr("group_icons"), cls._icon_buttons(), 4),
            (cls.tr("group_raised"), cls._raised_buttons(), 4),
            (cls.tr("group_rounded"), cls._rounded_buttons(), 4),
            (cls.tr("group_rounded_icons"), cls._round_icon_buttons("solid"), 4),
            (cls.tr("group_rounded_text"), cls._round_icon_buttons("text"), 4),
            (cls.tr("group_rounded_outlined"), cls._round_icon_buttons("outlined"), 4),
            (cls.tr("group_loading"), cls._loading_buttons(), 4),
        ]


PAGE = ButtonPreviewPage
