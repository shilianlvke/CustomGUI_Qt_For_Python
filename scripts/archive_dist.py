import shutil
import sys
from pathlib import Path


def main() -> int:
    """函数：main。

    参数:
    - 按函数签名传入。

    返回:
    - 按函数实现返回。
    """
    if len(sys.argv) != 2:
        print("Usage: python scripts/archive_dist.py <target-name>")
        return 2

    target_name = sys.argv[1]
    root = Path(__file__).resolve().parents[1]
    dist_app = root / "dist" / "CustomGUI"
    releases_dir = root / "dist" / "release"
    releases_dir.mkdir(parents=True, exist_ok=True)

    if not dist_app.exists():
        print(f"Build output not found: {dist_app}")
        return 1

    archive_base = releases_dir / f"CustomGUI-{target_name}"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=dist_app)
    print(f"Created archive: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

