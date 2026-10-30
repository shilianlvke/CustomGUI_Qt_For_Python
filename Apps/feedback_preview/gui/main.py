"""反馈与状态预览页：按 Sakai 的 Message / Misc 两页复刻 P0 组件。

分组：内联消息、消息变体、浮出通知、标签、徽标、标签片、头像、骨架屏、
进度条、分割线。页面协议（``PAGE``）由基座以 ``load_page(window)`` 调用。
"""

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from AppCore import AppSettings, Language, PathFactory
from GuiCore import (
    CAvatar,
    CBadge,
    CButton,
    CCard,
    CChip,
    CDivider,
    CMessage,
    CProgressBar,
    CScrollArea,
    CSkeleton,
    CTag,
    CToast,
)

_LANG = "app.feedback_preview"

_MESSAGES = (
    ("info", "Info", "This is an info message."),
    ("success", "Success", "Your changes have been saved."),
    ("warn", "Warn", "Storage is almost full."),
    ("error", "Error", "Something went wrong, please retry."),
    ("secondary", "Secondary", "Secondary message for neutral hints."),
    ("contrast", "Contrast", "High contrast message for emphasis."),
)


def _t(key: str) -> str:
    return Language.resolve(f"{_LANG}.{key}", key)


def _fixed(widget, width: int):
    widget.setFixedWidth(width)
    return widget


# ----------------------------------------------------------------------
# 分组内容
# ----------------------------------------------------------------------
def _messages():
    cards = []
    for severity, title, text in _MESSAGES:
        message = CMessage(text, title=title, severity=severity)
        message.setFixedWidth(380)
        cards.append(message)
    return cards


def _message_variants():
    outlined_success = CMessage("Outlined success message.", title="Success", severity="success", outlined=True)
    outlined_danger = CMessage("Outlined error message.", title="Error", severity="error", outlined=True)
    closable = CMessage("You can close this message.", title="Closable", severity="info", closable=True)
    long_text = CMessage(
        "A longer message that wraps onto a second line to show the layout behaviour of the component.",
        title="Multi-line",
        severity="warn",
        closable=True,
    )
    simple = CMessage("Simple message without background or border.", title="Simple", severity="success", simple=True)
    for widget in (outlined_success, outlined_danger, closable, long_text, simple):
        widget.setFixedWidth(380)
    return [outlined_success, outlined_danger, closable, long_text, simple]


def _toast_offset(window) -> int:
    """通知避开标题栏：优先取真实标题栏高度，取不到时退回 56。"""
    bar = getattr(getattr(window, "ui", None), "title_bar", None)
    return bar.height() + 8 if bar is not None else 56


def _toasts(window):
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    samples = (
        ("success", "toast_success", "Success", "Event booked successfully."),
        ("info", "toast_info", "Info", "PrimeVue rocks!"),
        ("warn", "toast_warn", "Warning", "Something went wrong."),
        ("error", "toast_error", "Error", "Failed to save the record."),
    )
    for severity, key, title, text in samples:
        button = CButton(_t(key), severity=severity)
        button.clicked.connect(
            lambda _checked=False, s=severity, ti=title, tx=text: CToast.show_message(
                window, tx, ti, s, offset_top=_toast_offset(window)
            )
        )
        layout.addWidget(button)

    clear = CButton(_t("toast_clear"), variant="outlined", severity="secondary")
    clear.clicked.connect(lambda: CToast.clear(window))
    layout.addWidget(clear)
    layout.addStretch()
    return [box]


def _tags():
    severities = ("primary", "secondary", "success", "info", "warn", "help", "danger", "contrast")
    tags = [CTag(severity.title(), severity) for severity in severities]
    tags.append(CTag("Rounded", "primary", rounded=True))
    tags.append(CTag("With icon", "success", icon="icon_check"))
    tags.append(CTag("Bookmark", "secondary", rounded=True, icon="icon_bookmark"))
    return tags


def _badges():
    badges = [
        CBadge("8", "danger"),
        CBadge("12", "warn"),
        CBadge("99+", "success"),
        CBadge("", "info", dot=True),
        CBadge("New", "primary", size="lg"),
    ]

    avatar = CAvatar(label="SL", size="lg")
    CBadge.attach(avatar, "3", "danger", "sm")
    badges.append(avatar)

    button = CButton("Inbox", variant="outlined", size="sm")
    CBadge.attach(button, "5", "danger", "sm")
    badges.append(button)
    return badges


def _chips():
    removable = CChip("Removable", removable=True)
    removable.removed.connect(removable.hide)
    return [
        CChip("React"),
        CChip("Vue", icon="icon_star_fill"),
        CChip("Angular", icon="icon_bell"),
        removable,
    ]


def _avatars():
    return [
        CAvatar("SL"),
        CAvatar(icon="icon_users"),
        CAvatar("AB", shape="square"),
        CAvatar("XL", size="xl"),
        CAvatar(image=PathFactory.set_jpg_image("头像"), size="lg"),
    ]


def _skeletons():
    card = QWidget()
    layout = QHBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    layout.addWidget(CSkeleton(48, 48, shape="circle"))

    column = QVBoxLayout()
    column.setSpacing(8)
    column.addWidget(CSkeleton(160, 12, shape="text"))
    column.addWidget(CSkeleton(110, 12, shape="text"))
    layout.addLayout(column)
    layout.addWidget(CSkeleton(120, 72))
    card.setFixedWidth(400)

    static = CSkeleton(180, 12, shape="text", animation=False)
    return [card, static]


def _progress():
    bars = [
        CProgressBar(25),
        CProgressBar(60),
        CProgressBar(80, show_value=True),
        CProgressBar(indeterminate=True, show_value=True),
    ]
    for bar in bars:
        bar.setFixedWidth(260)

    vertical = QWidget()
    layout = QHBoxLayout(vertical)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    for value, indeterminate in ((65, False), (0, True)):
        bar = CProgressBar(value, orientation="vertical", indeterminate=indeterminate, height=10)
        bar.setFixedHeight(110)
        layout.addWidget(bar)
    vertical.setFixedSize(90, 120)
    return bars + [vertical]


def _dividers():
    vertical = QWidget()
    layout = QHBoxLayout(vertical)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    layout.addWidget(QLabel("Left"))
    layout.addWidget(CDivider(orientation="vertical"))
    layout.addWidget(QLabel("Right"))
    vertical.setFixedHeight(60)

    return [
        _fixed(CDivider(), 720),
        _fixed(CDivider(style="dashed"), 720),
        _fixed(CDivider(style="dotted"), 720),
        _fixed(CDivider(text="Content", align="left"), 720),
        vertical,
    ]


def _sections(window):
    return [
        (_t("group_message"), _messages(), 2),
        (_t("group_message_variant"), _message_variants(), 2),
        (_t("group_toast"), _toasts(window), 1),
        (_t("group_tag"), _tags(), 6),
        (_t("group_badge"), _badges(), 4),
        (_t("group_chip"), _chips(), 4),
        (_t("group_avatar"), _avatars(), 4),
        (_t("group_skeleton"), _skeletons(), 2),
        (_t("group_progress"), _progress(), 2),
        (_t("group_divider"), _dividers(), 1),
    ]


# ----------------------------------------------------------------------
# 页面装配
# ----------------------------------------------------------------------
def _section_card(title: str, widgets, columns: int = 3) -> CCard:
    card = CCard()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(QMargins(12, 10, 12, 12))
    layout.setSpacing(8)

    label = QLabel(title)
    font = QFont(AppSettings.family, AppSettings.subtitle_size)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    layout.addWidget(label)

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
    page.setObjectName("feedbackPreviewPage")
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

    for title, widgets, columns in _sections(window):
        content_layout.addWidget(_section_card(title, widgets, columns))
    content_layout.addStretch()
    return page


class FeedbackPreviewPage:
    """PAGE 协议入口：``load_page(window)`` 的 self 是主窗口。"""

    def load_page(self):
        _build_page(self)


PAGE = FeedbackPreviewPage
