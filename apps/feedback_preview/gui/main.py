"""反馈与状态预览页：按 Sakai 的 Message / Misc 两页复刻 P0 组件。

分组：内联消息、消息变体、浮出通知、标签、徽标、标签片、头像、骨架屏、
进度条、分割线。
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from customgui.appcore import PathFactory
from customgui.guicore import (
    CAvatar,
    CBadge,
    CButton,
    CChip,
    CDivider,
    CMessage,
    CPreviewPage,
    CProgressBar,
    CSkeleton,
    CTag,
    CToast,
)

_MESSAGES = (
    ("info", "Info", "This is an info message."),
    ("success", "Success", "Your changes have been saved."),
    ("warn", "Warn", "Storage is almost full."),
    ("error", "Error", "Something went wrong, please retry."),
    ("secondary", "Secondary", "Secondary message for neutral hints."),
    ("contrast", "Contrast", "High contrast message for emphasis."),
)


class FeedbackPreviewPage(CPreviewPage):
    """PAGE 协议入口：消息、通知、标识与进度类组件。"""

    slug = "feedback_preview"

    # ------------------------------------------------------------------
    # 分组内容
    # ------------------------------------------------------------------
    @classmethod
    def _messages(cls):
        cards = []
        for severity, title, text in _MESSAGES:
            message = CMessage(text, title=title, severity=severity)
            message.setFixedWidth(380)
            cards.append(message)
        return cards

    @staticmethod
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
        widgets = [outlined_success, outlined_danger, closable, long_text, simple]
        for widget in widgets:
            widget.setFixedWidth(380)
        return widgets

    @staticmethod
    def _toast_offset(window) -> int:
        """通知避开标题栏：优先取真实标题栏高度，取不到时退回 56。"""
        bar = getattr(getattr(window, "ui", None), "title_bar", None)
        return bar.height() + 8 if bar is not None else 56

    @classmethod
    def _toasts(cls, window):
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
            button = CButton(cls.tr(key), severity=severity)
            button.clicked.connect(
                lambda _checked=False, s=severity, ti=title, tx=text: CToast.show_message(
                    window, tx, ti, s, offset_top=cls._toast_offset(window)
                )
            )
            layout.addWidget(button)

        clear = CButton(cls.tr("toast_clear"), variant="outlined", severity="secondary")
        clear.clicked.connect(lambda: CToast.clear(window))
        layout.addWidget(clear)
        layout.addStretch()
        return [box]

    @staticmethod
    def _tags():
        severities = ("primary", "secondary", "success", "info", "warn", "help", "danger", "contrast")
        tags = [CTag(severity.title(), severity) for severity in severities]
        tags.append(CTag("Rounded", "primary", rounded=True))
        tags.append(CTag("With icon", "success", icon="icon_check"))
        tags.append(CTag("Bookmark", "secondary", rounded=True, icon="icon_bookmark"))
        return tags

    @staticmethod
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

    @staticmethod
    def _chips():
        removable = CChip("Removable", removable=True)
        removable.removed.connect(removable.hide)
        return [
            CChip("React"),
            CChip("Vue", icon="icon_star_fill"),
            CChip("Angular", icon="icon_bell"),
            removable,
        ]

    @staticmethod
    def _avatars():
        return [
            CAvatar("SL"),
            CAvatar(icon="icon_users"),
            CAvatar("AB", shape="square"),
            CAvatar("XL", size="xl"),
            CAvatar(image=PathFactory.set_jpg_image("头像"), size="lg"),
        ]

    @staticmethod
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

    @staticmethod
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

    @classmethod
    def _dividers(cls):
        vertical = QWidget()
        layout = QHBoxLayout(vertical)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Left"))
        layout.addWidget(CDivider(orientation="vertical"))
        layout.addWidget(QLabel("Right"))
        vertical.setFixedHeight(60)

        return [
            cls.fixed(CDivider(), 720),
            cls.fixed(CDivider(style="dashed"), 720),
            cls.fixed(CDivider(style="dotted"), 720),
            cls.fixed(CDivider(text="Content", align="left"), 720),
            vertical,
        ]

    # ------------------------------------------------------------------
    # 页面结构
    # ------------------------------------------------------------------
    @classmethod
    def sections(cls, page, window):
        return [
            (cls.tr("group_message"), cls._messages(), 2),
            (cls.tr("group_message_variant"), cls._message_variants(), 2),
            (cls.tr("group_toast"), cls._toasts(window), 1),
            (cls.tr("group_tag"), cls._tags(), 6),
            (cls.tr("group_badge"), cls._badges(), 4),
            (cls.tr("group_chip"), cls._chips(), 4),
            (cls.tr("group_avatar"), cls._avatars(), 4),
            (cls.tr("group_skeleton"), cls._skeletons(), 2),
            (cls.tr("group_progress"), cls._progress(), 2),
            (cls.tr("group_divider"), cls._dividers(), 1),
        ]


PAGE = FeedbackPreviewPage
