"""模块说明。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _build_add_data_arg(src: str, dest: str) -> str:
    """函数：_build_add_data_arg。

    参数:
    - 按函数签名传入。

    返回:
    - 按函数实现返回。
    """
    separator = ";" if os.name == "nt" else ":"
    return f"{src}{separator}{dest}"


def main() -> int:
    """函数：main。"""
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)

    dist_dir = root / "dist"
    build_dir = root / "build"

    if build_dir.exists():
        shutil.rmtree(build_dir)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "CustomGUI",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(root),
        "--add-data",
        _build_add_data_arg("resource", "resource"),
        "--add-data",
        _build_add_data_arg("ReadMeRes", "ReadMeRes"),
        "main.py",
    ]

    sys.stdout.write(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, check=False)  # noqa: S603
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
