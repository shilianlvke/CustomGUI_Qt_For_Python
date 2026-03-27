import os
from pathlib import Path


class ResourceLocator:
    """资源定位器。

    职责:
    - 统一解析项目根目录。
    - 在不依赖当前工作目录的前提下定位资源文件。
    """

    _ROOT_ENV = "CUSTOMGUI_ROOT_DIR"

    @classmethod
    def project_root(cls) -> Path:
        """获取项目根目录。

        返回:
        - Path: 项目根目录绝对路径。
        """

        custom_root = os.getenv(cls._ROOT_ENV, "").strip()
        if custom_root:
            return Path(custom_root).expanduser().resolve()
        return Path(__file__).resolve().parents[3]

    @classmethod
    def resolve(cls, relative_path: str | Path) -> Path:
        """将相对路径解析为项目内绝对路径。

        参数:
        - relative_path: 相对路径或 Path 对象。

        返回:
        - Path: 解析后的绝对路径。
        """

        rel = Path(relative_path)
        return (cls.project_root() / rel).resolve()

    @classmethod
    def find_files_by_extension(cls, extension: str, directory: str | Path) -> list[str]:
        """在指定目录递归查找扩展名匹配的文件。

        参数:
        - extension: 扩展名，可带或不带前导点。
        - directory: 目录路径（相对项目根目录）。

        返回:
        - list[str]: 匹配文件的绝对路径字符串列表。
        """

        suffix = extension if extension.startswith(".") else f".{extension}"
        base_dir = cls.resolve(directory)
        if not base_dir.exists():
            return []

        matched: list[str] = []
        for path in base_dir.rglob(f"*{suffix}"):
            if path.is_file():
                matched.append(str(path.resolve()))
        return matched
