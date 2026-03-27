from qt_core import QHBoxLayout, QIcon, QLabel, QSize, QVBoxLayout, Qt

from AppCore import PathFactory, Language
from GuiCore import CDialog, CCard, CPushButton, CLineEdit


class TeamSearchDialog:
    """团队检索对话框。"""

    @staticmethod
    def setup_ui(title) -> None:
        """构建并展示团队检索对话框。

        参数:
        - title: 对话框标题。

        返回:
        - None
        """

        create_team = CDialog(title)

        team_name = CCard()
        team_name_layout = QHBoxLayout(team_name)
        team_name_label = QLabel(Language.P2PTester.team_create_dialog.team_name_label)
        team_name_line_edit = CLineEdit(place_holder_text=Language.P2PTester.team_create_dialog.team_name_input)
        team_name_layout.addWidget(team_name_label)
        team_name_layout.addWidget(team_name_line_edit)

        team_doc = CCard()
        team_doc_layout = QHBoxLayout(team_doc)
        team_doc_label = QLabel(Language.P2PTester.team_create_dialog.team_doc_label)
        team_doc_line_edit = CLineEdit(place_holder_text=Language.P2PTester.team_create_dialog.team_doc_input)
        team_doc_layout.addWidget(team_doc_label)
        team_doc_layout.addWidget(team_doc_line_edit)

        team_submit = CCard()
        team_submit_layout = QVBoxLayout(team_submit)
        team_submit_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        team_submit_btn = CPushButton(
            size=QSize(192, 32),
            text=Language.P2PTester.team_create_dialog.team_create_btn,
            icon=QIcon(PathFactory.set_svg_icon("icon_new_build")),
        )
        team_submit_layout.addWidget(team_submit_btn)

        create_team.content_layout.addWidget(team_name)
        create_team.content_layout.addWidget(team_doc)
        create_team.content_layout.addStretch()
        create_team.content_layout.addWidget(team_submit)
        create_team.setModal(True)
        create_team.show()
        create_team.exec()
