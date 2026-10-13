from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap

from AppCore.SYS import Logger
from AppCore.SYS.config.paths import resolve_path


class PathFinder:
    """
    路径工厂类
    """

    images = r"resource/CustomUI/images/"
    languages = r"resource/CustomUI/languages/"
    themes = r"resource/CustomUI/themes/"
    settings = r"resource/CustomUI/settings/"
    others = r"resource/CustomUI/others/"

    @classmethod
    def __get_path(cls, folder, icon_name):
        path = resolve_path(folder) / icon_name
        if path.is_file():
            return str(path)
        Logger.error(f"路径文件不存在{path}")
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


class PicFixFactory:
    @staticmethod
    def create_rounded_pixmap(pixmap: QPixmap, radius: int | float) -> QPixmap:
        # 不处理空数据或者错误数据
        if pixmap.isNull():
            return pixmap

        # 获取图片尺寸
        image_width = pixmap.width()
        image_height = pixmap.height()

        # 处理大尺寸的图片,保证图片显示区域完整
        new_pixmap = QPixmap(
            pixmap.scaled(
                image_width,
                image_width if image_height == 0 else image_height,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        dest_image = QPixmap(image_width, image_height)
        dest_image.fill(Qt.transparent)

        painter = QPainter(dest_image)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        painter.setRenderHint(QPainter.SmoothPixmapTransform)  # 平滑处理
        # 裁圆角
        path = QPainterPath()
        rect = QRectF(0, 0, image_width, image_height)
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, image_width, image_height, new_pixmap)

        return dest_image
