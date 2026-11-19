"""资源路径解析：只依赖标准库，不引入 Qt。

绘制相关的图像处理（圆角位图）已下沉到 ``guicore.custom_ui.paint_utils``，
本模块因此可以在无 PySide6 的环境下导入（插件校验 CLI 依赖此性质）。
"""

from pathlib import Path

from sllkgui.appcore.sysx.config.paths import find_resource, resolve_path
from sllkgui.appcore.sysx.modules.logger_module import Logger


class PathFinder:
    """
    路径工厂类
    """

    images = r"resource/sllkgui/images/"
    languages = r"resource/sllkgui/languages/"
    themes = r"resource/sllkgui/themes/"
    settings = r"resource/sllkgui/settings/"
    others = r"resource/sllkgui/others/"

    @classmethod
    def __get_path(cls, folder, icon_name):
        candidate = Path(folder) / icon_name
        path = find_resource(candidate)
        if path is not None and path.is_file():
            return str(path)
        Logger.error(f"路径文件不存在{candidate}")
        fallback = find_resource(Path(cls.images) / "icon_pic_not_found.svg")
        if fallback is None:
            fallback = resolve_path(Path(cls.images) / "icon_pic_not_found.svg")
        return str(fallback)

    # 设置svg类型的icon
    @classmethod
    def resolve_svg(cls, name_or_path):
        """解析 SVG 图标：已存在的文件路径直接使用，否则按内置图标名解析。"""
        if Path(name_or_path).is_file():
            return str(Path(name_or_path))
        return cls.set_svg_icon(name_or_path)

    # 设置svg类型的icon
    @classmethod
    def set_svg_icon(cls, name):
        return cls.__get_path(Path(cls.images) / "svg_icons", name + ".svg")

    # 设置svg类型的image
    @classmethod
    def set_svg_image(cls, name):
        return cls.__get_path(Path(cls.images) / "svg_images", name + ".svg")

    # 设置png类型的image
    @classmethod
    def set_png_image(cls, name):
        return cls.__get_path(Path(cls.images) / "png_images", name + ".png")

    # 设置ico
    @classmethod
    def set_ico(cls, name):
        return cls.__get_path(Path(cls.images) / "ico", name + ".ico")

    @classmethod
    def set_jpg_image(cls, name):
        return cls.__get_path(Path(cls.images) / "jpg_images", name + ".jpg")

    @classmethod
    def set_themes(cls, name):
        return cls.__get_path(cls.themes, name + ".yaml")

    @classmethod
    def set_languages(cls, name):
        return cls.__get_path(cls.languages, name + ".yaml")

    @classmethod
    def set_settings(cls):
        return cls.__get_path(cls.settings, "config" + ".yaml")

    @classmethod
    def set_update_log(cls):
        return cls.__get_path(cls.others, "DevelopLog" + ".yaml")
