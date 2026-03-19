import os
from pathlib import Path


class ResourceLocator:
    """Resolve project resources independent of current working directory."""

    _ROOT_ENV = "CUSTOMGUI_ROOT_DIR"

    @classmethod
    def project_root(cls) -> Path:
        custom_root = os.getenv(cls._ROOT_ENV, "").strip()
        if custom_root:
            return Path(custom_root).expanduser().resolve()
        return Path(__file__).resolve().parents[3]

    @classmethod
    def resolve(cls, relative_path: str | Path) -> Path:
        rel = Path(relative_path)
        return (cls.project_root() / rel).resolve()

    @classmethod
    def find_files_by_extension(cls, extension: str, directory: str | Path) -> list[str]:
        suffix = extension if extension.startswith(".") else f".{extension}"
        base_dir = cls.resolve(directory)
        if not base_dir.exists():
            return []

        matched: list[str] = []
        for path in base_dir.rglob(f"*{suffix}"):
            if path.is_file():
                matched.append(str(path.resolve()))
        return matched
