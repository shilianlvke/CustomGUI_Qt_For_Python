import os
import shutil
import subprocess
import sys
from pathlib import Path


def _build_add_data_arg(src: str, dest: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{src}{separator}{dest}"


def main() -> int:
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
        # Apps 应用模组（基座启动时扫描加载，必须随包分发）
        "--add-data",
        _build_add_data_arg("Apps", "Apps"),
        "main.py",
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
