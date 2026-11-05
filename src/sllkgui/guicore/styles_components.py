"""``Styles`` 的组件级样式片段。

每个 ``update_*_style`` 方法对应一族组件（按钮、输入框、表格、滚动条……），
统一追加到宿主拼装的 ``self.style`` 字符串。本模块只做「颜色/状态/字体」的
文本生成，配色值全部来自 :class:`~sllkgui.guicore.styles.Styles` 预先算好的
调色属性（``tokens`` / ``glass`` / ``_stroke`` / ``_fill_*`` 等），因此
``Styles`` 继承本 mixin 即可，行为与拆分前一致。

``_mix`` 放在这里供两侧共用：``Styles`` 的调色计算与本模块的输入框 hover
描边都需要它，单独留在 ``styles.py`` 会形成循环导入。
"""

from __future__ import annotations

from PySide6.QtGui import QColor


def _mix(start: str, end: str, ratio: float) -> str:
    """两个颜色按比例混合（``ratio``=0 取 start，=1 取 end）。"""
    begin, finish = QColor(start), QColor(end)
    return QColor(
        round(begin.red() + (finish.red() - begin.red()) * ratio),
        round(begin.green() + (finish.green() - begin.green()) * ratio),
        round(begin.blue() + (finish.blue() - begin.blue()) * ratio),
    ).name()


class _ComponentStyles:
    """组件样式 mixin：把各组件的 QSS 片段追加到宿主的 ``self.style``。"""

    def update_region_card_style(self):
        """内容区与四向抽屉共用的区域背景卡片。

        卡片只提供**底色 + 圆角**，不再描边：描边会在卡片与内部内容之间夹出
        一圈异色窄环，内容也就不可能和卡片"无缝拼接"。底色见
        :func:`region_card_tint`，圆角取 ``radius.window``，五个区域完全同一
        套规则，深浅主题自动跟随。

        亚克力模式下底色是半透明玻璃层，与上方的标题栏/侧栏形成层次；页面
        过场采用透明擦除，擦除空白直接露出这层玻璃，不再用实色近似。内容与
        卡片齐平由挂载处保证（``ui_main`` 的内容区布局、三向栏目的标题条布局
        边距均为 0），本文件只负责颜色，几何留在实例侧。
        """
        self.style += f"""
            #CRegion_Card_Frame {{
                background-color: {self._region_bg};
                border: 0px solid transparent;
                border-radius: {self.tokens.radius.window}px;
            }}
        """

    def update_btn_style(self):
        """按钮族样式。

        ``CMenuButton`` / ``CPushButton`` 的圆角与边框宽度属实例级几何，由组件
        本地覆盖；这里只提供颜色、内边距与 ``::menu-indicator`` 的图标资源。
        """
        self.style += f"""
            #CMenuButton_PushButton {{
                border-style: solid;
                border-color: {self._control_stroke_secondary};
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
                padding-left: {self.tokens.spacing.padding_md}px;
            }}
            #CMenuButton_PushButton:hover {{
                background-color: {self._fill_hover};
                border-color: {self._stroke_strong};
            }}
            #CMenuButton_PushButton:pressed {{
                background-color: {self._fill_pressed};
            }}
            #CMenuButton_PushButton:focus {{
                border: 2px solid {self._accent_border};
            }}
            #CMenuButton_PushButton:disabled {{
                background-color: {self._fill_rest};
                border-color: {self._stroke};
                color: {self.tokens.colors.text_muted};
            }}
            #CMenuButton_PushButton::menu-indicator {{
                image: url({self._icon_arrow_right});
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
                subcontrol-position: right;
            }}
            #CMenuButton_PushButton::menu-indicator:pressed, #CMenuButton_PushButton::menu-indicator:open {{
                image: url({self._icon_arrow_down});
                width: {self.tokens.size.icon}px;
                height: {self.tokens.size.icon}px;
            }}
        """
        self.style += f"""
            #CPushButton_PushButton {{
                border-style: solid;
                border-color: {self._control_stroke_secondary};
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
            }}
            #CPushButton_PushButton:hover {{
                background-color: {self._fill_hover};
                border-color: {self._stroke_strong};
            }}
            #CPushButton_PushButton:pressed {{
                background-color: {self._fill_pressed};
            }}
            #CPushButton_PushButton:focus {{
                border: 2px solid {self._accent_border};
            }}
            #CPushButton_PushButton:disabled {{
                background-color: {self._fill_rest};
                border-color: {self._stroke};
                color: {self.tokens.colors.text_muted};
            }}
            #CPushButton_PushButton:flat {{
                border: 1px solid {self.tokens.colors.text_primary};
            }}
        """

    def update_lineedit_style(self):
        """输入框族：颜色与状态（高度/圆角/内边距/字号由组件本地覆盖）。

        hover 描边取「常态描边 → 正文色」的 35% 混合：深色主题变亮、浅色主题变深，
        两个方向都更醒目；玻璃模式下描边本身已是低透明度正文色，混合后仍是
        同一色相，不会出现"浮在玻璃上的另一个色块"。文字色用 ``text_active``
        保证输入内容的可读性。
        """
        border = self._control_stroke
        hover_border = _mix(border, self.tokens.colors.text_primary, 0.25)
        selection_bg = self._accent_soft
        self.style += f"""
            #CInputText_LineEdit, #CTextarea_PlainTextEdit {{
                background-color: {self._control_bg};
                border: 1px solid {border};
                border-radius: {self.tokens.radius.control}px;
                color: {self.tokens.colors.text_active};
                placeholder-text-color: {self.tokens.colors.text_muted};
                selection-color: {self.tokens.colors.text_active};
                selection-background-color: {selection_bg};
            }}
            #CInputText_LineEdit:hover, #CTextarea_PlainTextEdit:hover {{
                border-color: {hover_border};
            }}
            #CInputText_LineEdit:focus, #CTextarea_PlainTextEdit:focus {{
                border-bottom: 2px solid {self._accent_border};
            }}
            #CInputText_LineEdit[invalid="true"], #CTextarea_PlainTextEdit[invalid="true"] {{
                border-color: {self._danger};
            }}
            #CInputText_LineEdit:disabled, #CTextarea_PlainTextEdit:disabled {{
                background-color: {self._fill_rest};
                border-color: {self._stroke};
                color: {self.tokens.colors.text_muted};
            }}
            #CLineEdit_LineEdit {{
                background-color: {self._fill_rest};
                border-radius: {self.tokens.radius.control}px;
                border: 1px solid {self._control_stroke};
                padding-left: {self.tokens.spacing.padding_sm}px;
                padding-right: {self.tokens.spacing.padding_sm}px;
                selection-color: {self.tokens.colors.text_active};
                selection-background-color: {self._accent_soft};
                color: {self.tokens.colors.text_primary};
            }}
            #CLineEdit_LineEdit:focus {{
                border-bottom: 2px solid {self._accent_border};
            }}
            #CLineEdit_LineEdit:disabled {{
                color: {self.tokens.colors.text_muted};
            }}
        """

    def update_combobox_style(self):
        """CComboBox：自绘下拉框的底色、描边与三态（hover / focused / disabled）。

        ``CComboBox`` 不再继承 ``QComboBox``，弹层与箭头都是自绘的，因此这里
        不再声明 ``::drop-down`` / ``::down-arrow`` / ``QAbstractItemView`` 等
        子控件规则——那些规则只对原生弹出层生效，留着只会误导后来者。
        弹层内部的列表样式由组件自身按当前主题实时生成（见 ``popup.py``）。
        """
        self.style += f"""
            #CComboBox_Field {{
                border: 1px solid {self._control_stroke};
                border-radius: {self.tokens.radius.control}px;
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
            }}
            #CComboBox_Field[hovered="true"] {{
                border-color: {self._stroke_strong};
                background-color: {self._fill_hover};
            }}
            #CComboBox_Field[focused="true"] {{
                border-bottom: 2px solid {self._accent_border};
                background-color: {self._fill_hover};
            }}
            #CComboBox_Field:disabled {{
                background-color: {self._fill_rest};
                border-color: {self._stroke};
                color: {self.tokens.colors.text_muted};
            }}
        """

    def update_status_button_style(self):
        """CStatusButton：颜色与三态边框色。

        圆角（``radius``）与边框宽度（``border_size``）是实例参数，由组件本地
        用一条只含几何属性的样式覆盖。状态经动态属性 ``status`` 选择。
        """
        self.style += f"""
            #CStatusButton_PushButton {{
                border-style: solid;
                border-color: {self._control_stroke_secondary};
                background-color: {self._fill_rest};
                color: {self.tokens.colors.text_primary};
            }}
            #CStatusButton_PushButton:hover {{
                background-color: {self._fill_hover};
                border-color: {self._stroke_strong};
            }}
            #CStatusButton_PushButton:pressed {{
                background-color: {self._fill_pressed};
            }}
            #CStatusButton_PushButton:focus {{
                border: 2px solid {self._accent_border};
            }}
            #CStatusButton_PushButton:disabled {{
                color: {self.tokens.colors.text_muted};
                border-color: {self._stroke};
            }}
            #CStatusButton_PushButton[status="1"] {{
                border-color: {self._accent_border};
                background-color: {self._accent_soft};
            }}
            #CStatusButton_PushButton[status="-1"] {{
                border-color: {self.tokens.colors.state_active};
            }}
        """

    def update_menu_style(self):
        """CMenu 弹出菜单：颜色与结构。

        弹出菜单是独立顶层窗口，不经过 CWindow，故依赖 ``CWindow.apply_style``
        下发的应用级样式表着色。圆角/边框宽度/菜单项内边距为实例级几何，由组件
        本地覆盖；``is_transparent`` 经动态属性 ``transparent`` 选择。

        玻璃模式下菜单保持高不透明度（``GLASS_MENU``）：弹层背后没有应用窗口
        的玻璃层可透，过低会直接看到未模糊的桌面。
        """
        self.style += f"""
            #CMenu_Menu {{
                border-style: solid;
                border-color: {self._control_stroke_secondary};
                background-color: {self._menu_bg};
                color: {self.tokens.colors.text_primary};
            }}
            #CMenu_Menu[transparent="true"] {{
                background-color: {self.tokens.colors.border_transparent};
            }}
            #CMenu_Menu::item {{
                border-style: solid;
                border-color: {self.tokens.colors.border_transparent};
                background-color: transparent;
            }}
            #CMenu_Menu::item:selected {{
                background-color: {self._accent_soft};
            }}
        """

    def update_show_card_style(self):
        """CShowCard：上下分区配色（颜色随主题；圆角由组件按实例覆盖）。"""
        self.style += f"""
            #CShowCard #topArea {{
                background-color: {self._fill_pressed};
            }}
            #CShowCard #bottomArea {{
                background-color: {self._fill_hover};
            }}
            #CShowCard #SourceLabel {{
                color: {self.tokens.colors.text_primary};
                background-color: {self._fill_hover};
            }}
            #CShowCard #IconLabel {{
                background-color: {self._fill_hover};
            }}
            /* 外观配置里的背景图手风琴：Fluent 设置卡片 */
            #CBackgroundAccordion_Frame {{
                background-color: {self._card_bg};
                border: 1px solid {self._control_stroke_secondary};
                border-radius: {self.tokens.radius.window}px;
            }}
            #CBackgroundAccordionHeader, #CBackgroundAccordionContent {{
                background: transparent;
            }}
        """

    def update_tooltip_style(self):
        """提示气泡（``CToolTip``）：三种按钮共用一套样式。

        提示气泡挂在主窗口下（不经过 CWindow），故依赖应用级样式表；强调边方向
        通过动态属性 ``accent`` 选择（left / top / right）。圆角与左右内边距是
        实例级几何，由组件本地覆盖。

        气泡是顶层弹窗，与菜单同理保持较高不透明度，保证浮在任意背景上可读。
        """
        self.style += f"""
            #label_tooltip {{
                background-color: {self._tooltip_bg};
                color: {self.tokens.colors.text_primary};
                border: 1px solid {self._control_stroke_secondary};
                font: {self.tokens.typography.weight_tooltip} {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
            }}
        """

    def update_title_bar_style(self):
        """标题栏标题文字。"""
        self.style += f"""
            #CTitleBar_Title_Label {{
                font: {self.tokens.typography.size_title}pt "{self.tokens.typography.family}";
            }}
        """

    def update_columns_style(self):
        """四向抽屉（栏目）的标题区与无背景容器框。

        左/右/顶/底四列同构：标题背景框 + 标题文字，图标位/按钮位/内容框保持
        透明。背景框圆角与标题的内边距/字体是组件本地几何，由组件覆盖。容器框
        改用 ID 选择器（原来是不带选择器的裸规则，会级联到所有子孙控件）。
        """
        self.style += f"""
            #CLeftColumnTitle_Frame, #CTopColumnTitle_Frame, #CBottomColumnTitle_Frame {{
                background-color: transparent;
            }}
            #CLeftColumnTitle_Label, #CTopColumnTitle_Label, #CBottomColumnTitle_Label {{
                color: {self.tokens.colors.text_muted};
                background: none;
            }}
            #CLeftColumnIcon_Frame, #CLeftColumnBtn_Frame, #CLeftColumnContent_Frame,
            #CTopColumnIcon_Frame, #CTopColumnBtn_Frame, #CTopColumnContent_Frame,
            #CBottomColumnIcon_Frame, #CBottomColumnBtn_Frame, #CBottomColumnContent_Frame {{
                background: none;
            }}
        """

    def update_grips_style(self):
        """窗口缩放夹点（调试边界）。

        颜色沿用原有调试配色以保持外观不变；``hide_grips`` 为真时经动态属性
        ``colored="false"`` 置为透明。

        四角夹点内嵌一个 ``QSizeGrip``（原生缩放角）。历史实现用**裸规则**
        ``background: transparent`` 覆盖夹点，该规则会级联到子控件 ``QSizeGrip``，
        使其改用 ``QStyleSheetStyle`` 绘制、不再画出原生点阵；若这里只写 ID
        选择器，子控件不受影响会重新画出灰色点阵，故须显式补一条后代规则。
        """
        self.style += """
            #top_left_grip, #top_right_grip, #bottom_left_grip, #bottom_right_grip {
                background-color: #333;
                border: 2px solid #55FF00;
            }
            #top_left_grip QSizeGrip, #top_right_grip QSizeGrip,
            #bottom_left_grip QSizeGrip, #bottom_right_grip QSizeGrip {
                background: transparent;
            }
            #top_grip {
                background-color: rgb(85, 255, 255);
            }
            #bottom_grip {
                background-color: rgb(85, 170, 0);
            }
            #left {
                background-color: rgb(255, 121, 198);
            }
            #right {
                background-color: rgb(255, 0, 127);
            }
            #top_left_grip[colored="false"], #top_right_grip[colored="false"],
            #bottom_left_grip[colored="false"], #bottom_right_grip[colored="false"],
            #top_grip[colored="false"], #bottom_grip[colored="false"],
            #left[colored="false"], #right[colored="false"] {
                background: transparent;
                border: none;
            }
        """

    def update_table_style(self):
        """数据表格与分页条：Fluent 列表式表头、行悬浮与选中态。

        表格表面使用卡片层底色，表头不铺实色块，仅用底部细线区分；
        选中态用强调色的低透明度叠加，避免整行高饱和色块。
        """
        selection = self._accent_soft
        radius = self.tokens.radius.window
        self.style += f"""
            #CDataTable_View, #CDataTable_FrozenView {{
                background-color: {self._card_bg};
                alternate-background-color: {self._card_bg};
                color: {self.tokens.colors.text_primary};
                border: 1px solid {self._control_stroke_secondary};
                border-radius: {self.tokens.radius.window}px;
                gridline-color: {self._gridline};
                selection-background-color: {selection};
                selection-color: {self.tokens.colors.text_active};
                outline: 0;
            }}
            #CDataTable_View::item, #CDataTable_FrozenView::item {{
                padding-left: 12px;
                padding-right: 12px;
                border: none;
                border-bottom: 1px solid {self._gridline};
            }}
            #CDataTable_View::item:hover, #CDataTable_FrozenView::item:hover {{
                background-color: {self._fill_hover};
            }}
            #CDataTable_View QHeaderView::section,
            #CDataTable_FrozenView QHeaderView::section {{
                background-color: {self._card_bg};
                color: {self.tokens.colors.text_muted};
                border: none;
                border-bottom: 1px solid {self._stroke};
                padding: 8px 12px;
                font-weight: 600;
            }}
            #CDataTable_View QTableCornerButton::section,
            #CDataTable_FrozenView QTableCornerButton::section {{
                background-color: {self._card_bg};
                border: none;
            }}
            #CDataTable_Empty, #CDataTable_Loading {{
                background-color: {self._card_bg};
                color: {self.tokens.colors.text_muted};
                border: 1px solid {self._control_stroke_secondary};
                border-radius: {radius}px;
            }}
            #CDataTable_Detail {{
                background-color: {self._fill_rest};
                border: 1px solid {self._control_stroke_secondary};
                border-radius: {radius}px;
            }}
            #CPaginator_Label {{
                color: {self.tokens.colors.text_muted};
                font: {self.tokens.typography.size_text}pt "{self.tokens.typography.family}";
                padding-left: 8px;
            }}
        """

    def update_scrollbar_style(self):
        """全局滚动条：透明轨道 + 细圆角把手，横纵一致，无原生箭头。

        历史实现只在表格与文件上传列表里各写了一份滚动条规则，
        ``CScrollArea``、``CTextarea`` 等可滚动控件没有规则，仍由平台样式
        绘制（带上下箭头、方形深色轨道）。此前 ``CScrollArea`` 一直隐藏滚动条
        所以看不出来；启用“按需显示”后，原生滚动条就与 Fluent 卡片格格不入。
        这里改为一条**全局规则**统一横/纵滚动条，各组件不再各写一份：

        - 轨道透明、无边框、无箭头（``add-line``/``sub-line`` 归零）；
        - 把手 12px 轨道内缩 3px，得到 6px 宽的胶囊形（圆角 3px）；
        - 常态/悬停/按下三档透明度，深浅主题与亚克力开关下都保持可辨。
        """
        thickness = 10
        inset = 3
        min_length = 32
        radius = 2
        self.style += f"""
            QScrollBar:vertical {{
                background: transparent;
                width: {thickness}px;
                margin: 0px;
                border: none;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: {thickness}px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {self._scroll_handle};
                min-height: {min_length}px;
                margin: {inset}px;
                border-radius: {radius}px;
            }}
            QScrollBar::handle:horizontal {{
                background: {self._scroll_handle};
                min-width: {min_length}px;
                margin: {inset}px;
                border-radius: {radius}px;
            }}
            QScrollBar::handle:vertical:hover,
            QScrollBar::handle:horizontal:hover {{
                background: {self._scroll_handle_hover};
            }}
            QScrollBar::handle:vertical:pressed,
            QScrollBar::handle:horizontal:pressed {{
                background: {self._scroll_handle_pressed};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            QAbstractScrollArea::corner {{
                background: transparent;
                border: none;
            }}
        """
