"""模块说明。"""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap

from AppCore.SYS import Logger
from AppCore.SYS.other.resource_locator import ResourceLocator


class PathFinder:
    """资源路径工厂。

    职责:
    - 提供图片、主题、语言和配置文件的统一路径解析入口。
    """

    images = r"resource/CustomUI/images/"
    languages = r"resource/CustomUI/languages/"
    themes = r"resource/CustomUI/themes/"
    settings = r"resource/CustomUI/settings/"
    others = r"resource/CustomUI/others/"

    @classmethod
    def __get_path(cls, folder: str, icon_name: str) -> str:
        """解析目标文件路径并在缺失时返回兜底图标路径。

        参数:
        - folder: 资源文件夹路径。
        - icon_name: 文件名。

        返回:
        - str: 可用文件路径。
        """
        path = ResourceLocator.resolve(folder)
        result = str(path / icon_name)
        if Path(result).exists():
            return result
        Logger.error(f"路径文件不存在{result}")
        return str(
            ResourceLocator.resolve(
                str(Path(cls.images) / "icon_pic_not_found.svg"),
            ),
        )

    @classmethod
    def set_svg_icon(cls, name: str) -> str:
        """获取 SVG 图标路径。

        参数:
        - name: 图标名称（不含扩展名）。

        返回:
        - str: SVG 图标绝对路径。
        """
        return cls.__get_path(str(Path(cls.images) / "svg_icons"), name + ".svg")

    @classmethod
    def set_svg_image(cls, name: str) -> str:
        """获取 SVG 图片路径。

        参数:
        - name: 图片名称（不含扩展名）。

        返回:
        - str: SVG 图片绝对路径。
        """
        return cls.__get_path(str(Path(cls.images) / "svg_images"), name + ".svg")

    @classmethod
    def set_png_image(cls, name: str) -> str:
        """获取 PNG 图片路径。

        参数:
        - name: 图片名称（不含扩展名）。

        返回:
        - str: PNG 图片绝对路径。
        """
        return cls.__get_path(str(Path(cls.images) / "png_images"), name + ".png")

    @classmethod
    def set_ico(cls, name: str) -> str:
        """获取 ICO 图标路径。

        参数:
        - name: 图标名称（不含扩展名）。

        返回:
        - str: ICO 图标绝对路径。
        """
        return cls.__get_path(str(Path(cls.images) / "ico"), name + ".ico")

    @classmethod
    def set_jpg_image(cls, name: str) -> str:
        """获取 JPG 图片路径。

        参数:
        - name: 图片名称（不含扩展名）。

        返回:
        - str: JPG 图片绝对路径。
        """
        return cls.__get_path(str(Path(cls.images) / "jpg_images"), name + ".jpg")

    @classmethod
    def set_themes(cls, name: str) -> str:
        """获取主题配置文件路径。

        参数:
        - name: 主题名（不含扩展名）。

        返回:
        - str: 主题配置绝对路径。
        """
        return cls.__get_path(cls.themes, name + ".yml")

    @classmethod
    def set_languages(cls, name: str) -> str:
        """获取语言配置文件路径。

        参数:
        - name: 语言名（不含扩展名）。

        返回:
        - str: 语言配置绝对路径。
        """
        return cls.__get_path(cls.languages, name + ".yml")

    @classmethod
    def set_settings(cls) -> str:
        """获取主设置文件路径。

        返回:
        - str: settings.yml 绝对路径。
        """
        return cls.__get_path(cls.settings, "settings" + ".yml")

    @classmethod
    def set_update_log(cls) -> str:
        """获取更新日志配置文件路径。

        返回:
        - str: UpdateLog.yml 绝对路径。
        """
        return cls.__get_path(cls.others, "UpdateLog" + ".yml")


class PicFixFactory:
    """图片处理工厂。"""

    @staticmethod
    def create_rounded_pixmap(pixmap: QPixmap, radius: float) -> QPixmap:
        """将图片裁剪为圆角图。

        参数:
        - pixmap: 原始图片对象。
        - radius: 圆角半径。

        返回:
        - QPixmap: 处理后的圆角图片。
        """
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
            ),
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
