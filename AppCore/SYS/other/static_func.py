import os
from AppCore.SYS import Logger
from AppCore.SYS.other.resource_locator import ResourceLocator
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPixmap, QPainter, QPainterPath


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
        path = ResourceLocator.resolve(folder)
        result = os.path.normpath(os.path.join(str(path), icon_name))
        if os.path.exists(result):
            return result
        else:
            Logger.error(f"路径文件不存在{result}")
            result = str(
                ResourceLocator.resolve(
                    os.path.join(cls.images, "icon_pic_not_found.svg")
                )
            )
            return result

    # 设置svg类型的icon
    @classmethod
    def set_svg_icon(cls, name):
        return cls.__get_path(os.path.join(cls.images, r"svg_icons/"), name + ".svg")

    # 设置svg类型的image
    @classmethod
    def set_svg_image(cls, name):
        return cls.__get_path(os.path.join(cls.images, r"svg_images/"), name + ".svg")

    # 设置png类型的image
    @classmethod
    def set_png_image(cls, name):
        return cls.__get_path(os.path.join(cls.images, r"png_images/"), name + ".png")

    # 设置ico
    @classmethod
    def set_ico(cls, name):
        return cls.__get_path(os.path.join(cls.images, r"ico/"), name + ".ico")

    @classmethod
    def set_jpg_image(cls, name):
        return cls.__get_path(os.path.join(cls.images, r"jpg_images"), name + ".jpg")

    @classmethod
    def set_themes(cls, name):
        return cls.__get_path(cls.themes, name + ".yml")

    @classmethod
    def set_languages(cls, name):
        return cls.__get_path(cls.languages, name + ".yml")

    @classmethod
    def set_settings(cls):
        return cls.__get_path(cls.settings, "settings" + ".yml")

    @classmethod
    def set_update_log(cls):
        return cls.__get_path(cls.others, "UpdateLog" + ".yml")


class PicFixFactory:
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
