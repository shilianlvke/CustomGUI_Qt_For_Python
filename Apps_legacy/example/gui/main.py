"""示例应用（Apps/example）：应用模组「完美范式」。

本范本逐项演示：

【基座能力访问】
- AppCore 公共 API：AppSettings（配置）、Logger（日志）、ColorPalette（主题色）、
  get_design_tokens（设计令牌）、record_event（遥测）、PathFactory（基座资源）；
- GuiCore 组件库：CCard / CPushButton / CScrollArea 等（全部内置主题跟随）。

【自身能力】
- 自身逻辑目录：``from ..lib import add, sub``（应用内相对导入）；
- 自身语言：``app.lang_text("key")``（resource/lang/<lang>.yml，随语言切换刷新）；
- 自身图标：``app.icon_path`` / ``app.icon(name)``（resource/icon/）；
- 自身图片：``app.image(name)``（resource/images/）；
- 自身语音：``app.voice(name)``（resource/voice/）；
- 任意自身资源：``app.resource(*parts)``（resource/ 下任意路径，插件自包含）；
- 自身样式：``from .style import STYLE, build_style``（gui/style.py 同包相对导入）；
- 自身清单：``app.config``（config.yml 全部字段）。

【页面协议】``build_page(app) -> QWidget``（最简形态；PAGE / register_plugins
见 README「Apps 应用模组」章节）。
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from AppCore import (
    AppSettings,
    ColorPalette,
    Logger,
    PathFactory,
    get_design_tokens,
    record_event,
)
from GuiCore import CCard, CPushButton

from ..lib import add, sub
from .style import STYLE, build_style


def build_page(app):
    """构建应用页面：返回 QWidget，基座负责挂载。"""
    # ---- 自身逻辑目录（lib）----
    result = add(1, 2) - sub(10, 7)  # (1+2) - (10-7) = 0

    # ---- 基座日志 + 遥测 ----
    Logger.info(f"[example] 用户逻辑计算结果: {result}")
    record_event("example.build_page", category="app", payload={"result": result})

    # ---- 基座设计令牌（主题/字体/间距等强类型配置）----
    tokens = get_design_tokens()

    # ---- 页面本体 ----
    page = QWidget()
    page.setObjectName(app.config.get("page_object") or "examplePage")
    # 自身样式：静态片段 + 主题敏感片段
    page.setStyleSheet(STYLE + build_style(ColorPalette))

    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    card = CCard()  # 基座组件（主题跟随）
    card_layout = QVBoxLayout(card)
    card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # 自身图标：resource/icon/app_icon.svg（config.yml 的 app_icon 资源键解析而来）
    icon_path = str(app.icon_path) if app.icon_path.is_file() else PathFactory.set_svg_icon("icon_home")
    icon_button = CPushButton(size=QSize(64, 64), icon=icon_path)

    # 自身语言：resource/lang/<lang>.yml（语言切换后页面重建自动刷新）
    title_label = QLabel(app.lang_text("app_text"))
    title_label.setStyleSheet(f'font: 700 20pt "{AppSettings.family}";')  # 基座配置

    detail_label = QLabel(app.lang_text("detail_text"))
    detail_label.setWordWrap(True)

    result_label = QLabel(app.lang_text("result_text").format(result))
    result_label.setObjectName("resultLabel")

    token_label = QLabel(app.lang_text("token_text").format(tokens.radius.window))

    # 自身图片：resource/images（经统一资源访问器 app.image() 引用，插件自包含）
    hero_image = app.image("mihoutao.svg")
    image_label = QLabel(app.lang_text("image_text").format(hero_image.name, "有" if hero_image.is_file() else "无"))
    svg_widget = QSvgWidget(str(hero_image)) if hero_image.is_file() else None

    # 自身语音：resource/voice（app.voice() 返回应用内路径，可交给 QSoundEffect 等使用）
    voice_dir = app.resource("voice")
    voice_file = app.voice("welcome.wav")
    voice_label = QLabel(app.lang_text("voice_text").format("有" if voice_dir.is_dir() else "无", voice_file.name))

    card_layout.addWidget(icon_button)
    card_layout.addWidget(title_label)
    card_layout.addWidget(detail_label)
    card_layout.addWidget(result_label)
    card_layout.addWidget(token_label)
    card_layout.addWidget(image_label)
    if svg_widget is not None:
        card_layout.addWidget(svg_widget)
    card_layout.addWidget(voice_label)

    layout.addWidget(card)

    # 挂载关键控件/状态供外部（测试/扩展）访问：范式演示用
    page.icon_button = icon_button
    page.title_label = title_label
    page.detail_label = detail_label
    page.result_label = result_label
    page.token_label = token_label
    page.image_label = image_label
    page.voice_label = voice_label
    page.palette_color = ColorPalette.custom_bg_one  # 基座主题色
    return page
