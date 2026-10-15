"""示例应用私有样式（约定：供 gui/main.py 相对导入使用）。

- ``STYLE``：静态样式片段，直接拼接到页面样式表；
- ``build_style(colorpalette)``：按当前调色板生成主题敏感样式。

主题实时跟随建议：需要着色的控件优先使用基座组件（基座组件已内置
主题订阅刷新）；确有自定义着色需求时，在页面构建后订阅
``get_theme_manager()`` 并重新调用 ``build_style`` 重设样式。
"""

from AppCore import ColorPalette

STYLE = """
QWidget {
    font-family: "Microsoft YaHei";
}
"""


def build_style(colorpalette=None):
    """按当前调色板生成动态样式。"""
    palette = colorpalette or ColorPalette
    return f"""
QLabel {{
    color: {palette.custom_text_foreground};
}}
"""
