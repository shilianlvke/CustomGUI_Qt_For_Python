"""插件第三方 Python 依赖检测与安装。

运行时只检查、不静默安装：发现缺失时先询问用户，再通过 ``uv pip install``
安装到**当前 Python 环境**。镜像源可由 ``SLLKGUI_PIP_INDEX_URL`` /
``configure(pip_index_url=...)`` / ``--index-url`` 配置。
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from sllkgui.appcore import Logger, record_event

from .errors import (
    PYTHON_DEPENDENCY_INSTALL_FAILED,
    PYTHON_DEPENDENCY_MISSING,
    TOOL_MISSING,
    UV_MISSING,
    GalleryError,
)

_INSTALL_TIMEOUT = 300
_NORMALIZE_RE = re.compile(r"[-.]+")
#: 这些平台没有真实用户点击，不能弹模态框（否则 exec() 永久阻塞）
_NON_INTERACTIVE_PLATFORMS = frozenset({"offscreen", "minimal"})


def _gui_available() -> bool:
    """是否有可交互的 Qt 界面；无界面环境回落到终端提问。"""
    if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() in _NON_INTERACTIVE_PLATFORMS:
        return False
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return False
    return QApplication.instance() is not None


@dataclass(frozen=True)
class ToolStatus:
    uv: str = ""
    git: str = ""
    pip: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"uv": self.uv, "git": self.git, "pip": self.pip}


def parse_requirement(text: str) -> Requirement:
    try:
        return Requirement(str(text).strip())
    except InvalidRequirement as exc:
        raise GalleryError(
            PYTHON_DEPENDENCY_MISSING,
            f"非法的 Python 依赖声明: {text!r}",
            str(exc),
        ) from exc


def import_name(requirement: Requirement | str) -> str:
    name = requirement.name if isinstance(requirement, Requirement) else parse_requirement(requirement).name
    return _NORMALIZE_RE.sub("_", name)


def missing_packages(requirements: list[str] | tuple[str, ...]) -> list[str]:
    """返回当前解释器中缺失（或版本不满足）的依赖声明（保持原顺序）。

    优先用 ``importlib.metadata`` 查发行包版本：PyYAML 的导入名是 ``yaml``、
    Pillow 是 ``PIL``，按包名反推模块名并不可靠。
    """
    missing: list[str] = []
    for spec in requirements:
        requirement = parse_requirement(spec)
        try:
            installed = metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            installed = None
        if installed is not None:
            if not requirement.specifier or requirement.specifier.contains(installed, prereleases=True):
                continue
            missing.append(str(requirement))
            continue
        # 没有 dist-info 的模块（例如随程序附带的单文件库）回落到导入名探测
        try:
            found = importlib.util.find_spec(import_name(requirement)) is not None
        except (ModuleNotFoundError, ValueError):
            found = False
        if not found:
            missing.append(str(requirement))
    return missing


def tool_status() -> ToolStatus:
    pip_available = False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        pip_available = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        pip_available = False
    return ToolStatus(
        uv=find_uv(),
        git=find_git() or "",
        pip=pip_available,
    )


def find_git() -> str:
    """``shutil.which`` 找不到时再查常见安装目录（winget 装完当前进程 PATH 不会刷新）。"""
    found = shutil.which("git")
    if found:
        return found
    candidates: list[Path] = []
    if os.name == "nt":
        for base in (os.getenv("ProgramFiles"), os.getenv("ProgramFiles(x86)"), os.getenv("LOCALAPPDATA")):
            if base:
                candidates.append(Path(base) / "Git" / "cmd" / "git.exe")
                candidates.append(Path(base) / "Programs" / "Git" / "cmd" / "git.exe")
    else:
        candidates += [Path("/usr/bin/git"), Path("/usr/local/bin/git"), Path("/opt/homebrew/bin/git")]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def manual_command(requirements: list[str], index_url: str = "") -> str:
    packages = " ".join(requirements)
    index = f" --index-url {index_url}" if index_url else ""
    if find_uv():
        return f'uv pip install --python "{sys.executable}"{index} {packages}'
    return f'python -m pip install{index} {packages}'


def _redact(index_url: str) -> str:
    if "@" not in index_url:
        return index_url
    scheme, _, rest = index_url.partition("://")
    return f"{scheme}://***@{rest.split('@', 1)[-1]}" if rest else index_url


def _ask_choice(
    *,
    title: str,
    message: str,
    detail: str,
    parent: Any,
    interactive: bool,
) -> str:
    """返回 ``auto`` / ``manual`` / ``skip``。"""
    if not interactive:
        return "skip"
    if _gui_available():
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(message)
        box.setInformativeText(detail)
        auto = box.addButton("自动安装", QMessageBox.ButtonRole.AcceptRole)
        manual = box.addButton("手动安装", QMessageBox.ButtonRole.ActionRole)
        box.addButton("跳过", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is auto:
            return "auto"
        if clicked is manual:
            return "manual"
        return "skip"
    if not sys.stdin.isatty():
        return "skip"
    print(message)
    print(detail)
    print("[1] 自动安装  [2] 手动安装  [0] 跳过")
    answer = input("> ").strip()
    return {"1": "auto", "2": "manual"}.get(answer, "skip")


def _show_manual(*, title: str, command: str, parent: Any) -> None:
    text = f"请手动执行：\n\n{command}"
    if _gui_available():
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(text)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.exec()
        return
    print(text)


def uv_manual_command() -> str:
    if os.name == "nt":
        return 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    return "curl -LsSf https://astral.sh/uv/install.sh | sh"


def git_manual_command() -> str:
    if os.name == "nt":
        return "winget install --id Git.Git -e --source winget"
    if sys.platform == "darwin":
        return "brew install git"
    return "sudo apt install git"


def _install_uv() -> str:
    """用 uv 官方安装脚本安装，返回可执行路径（不使用 pip）。"""
    command = uv_manual_command()
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "ByPass", "-c", "irm https://astral.sh/uv/install.ps1 | iex"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_INSTALL_TIMEOUT,
                check=False,
            )
        else:
            result = subprocess.run(
                ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_INSTALL_TIMEOUT,
                check=False,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GalleryError(UV_MISSING, "uv 安装失败", str(exc)) from exc
    path = shutil.which("uv") or find_uv()
    if path:
        Logger.info(f"uv 安装完成: {path}")
        return path
    detail = (result.stderr or result.stdout or "").strip()[-2000:]
    raise GalleryError(UV_MISSING, "uv 安装后仍未找到可执行文件（可能需要重启终端）", detail or command)


def find_uv() -> str:
    """``shutil.which`` 找不到时再查安装脚本的默认目录。"""
    found = shutil.which("uv")
    if found:
        return found
    candidates: list[Path] = []
    home = Path.home()
    candidates.append(home / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv"))
    if os.name == "nt":
        local = os.getenv("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Microsoft" / "WindowsApps" / "uv.exe")
    else:
        candidates += [Path("/usr/local/bin/uv"), Path("/opt/homebrew/bin/uv")]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def ensure_uv(*, interactive: bool, index_url: str = "", parent: Any = None) -> str:
    existing = shutil.which("uv")
    if existing:
        return existing
    command = uv_manual_command()
    if not interactive:
        raise GalleryError(UV_MISSING, "未找到 uv，无法自动安装依赖", command)
    choice = _ask_choice(
        title="缺少 uv",
        message="自动安装第三方 Python 依赖需要 uv。是否现在安装 uv？",
        detail=f"也可以手动执行：\n\n{command}",
        parent=parent,
        interactive=interactive,
    )
    if choice == "manual":
        _show_manual(title="手动安装 uv", command=command, parent=parent)
        raise GalleryError(UV_MISSING, "已选择手动安装 uv", command)
    if choice != "auto":
        raise GalleryError(UV_MISSING, "已跳过 uv 安装", command)
    return _install_uv()


def _install_git() -> str:
    """Windows 用 winget 静默安装 Git；其它平台只支持手动。"""
    if os.name != "nt" or not shutil.which("winget"):
        raise GalleryError(TOOL_MISSING, "无法自动安装 Git，请手动安装", git_manual_command())
    Logger.info("正在通过 winget 安装 Git")
    try:
        result = subprocess.run(
            [
                "winget",
                "install",
                "--id",
                "Git.Git",
                "-e",
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_INSTALL_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GalleryError(TOOL_MISSING, "Git 安装失败", str(exc)) from exc
    path = find_git()
    if path:
        return path
    detail = (result.stderr or result.stdout or "").strip()[-2000:]
    raise GalleryError(TOOL_MISSING, "Git 安装后仍未找到可执行文件（可能需要重启终端）", detail)


def ensure_tools(*, interactive: bool = True, parent: Any = None) -> ToolStatus:
    """启动时检测 uv / Git；缺失时让用户选择自动或手动安装。

    只做提示与安装尝试，不抛异常：缺少工具时功能降级（无法从源安装插件），
    不影响基座启动。
    """
    status = tool_status()
    missing: list[str] = []
    if not status.uv:
        missing.append("uv（用于安装插件 Python 依赖）")
    if not status.git:
        missing.append("Git（用于从插件源安装/刷新）")
    if not missing:
        return status
    Logger.warning(f"未检测到工具: {', '.join(name.split('（')[0] for name in missing)}")

    lines: list[str] = []
    if not status.uv:
        lines.append(f"uv: {uv_manual_command()}")
    if not status.git:
        lines.append(f"Git: {git_manual_command()}")
    manual = "\n".join(lines)
    if not interactive:
        return status
    choice = _ask_choice(
        title="缺少运行工具",
        message="检测到以下工具缺失：\n" + "\n".join(f"  - {item}" for item in missing),
        detail=f"自动安装会使用 pip 安装 uv、使用 winget 安装 Git（非 Windows 需手动）。\n\n手动安装命令：\n{manual}",
        parent=parent,
        interactive=interactive,
    )
    if choice == "manual":
        _show_manual(title="手动安装工具", command=manual, parent=parent)
        return status
    if choice != "auto":
        Logger.warning("已跳过工具安装；从插件源安装/刷新插件的功能不可用")
        return status

    if not status.uv:
        try:
            path = _install_uv()
            status = ToolStatus(uv=path, git=status.git, pip=status.pip)
            Logger.info(f"uv 安装完成: {path}")
        except GalleryError as exc:
            Logger.warning(f"uv 自动安装失败: {exc.message}")
            _show_manual(title="手动安装 uv", command=uv_manual_command(), parent=parent)
    if not status.git:
        try:
            path = _install_git()
            status = ToolStatus(uv=status.uv, git=path, pip=status.pip)
            Logger.info(f"Git 安装完成: {path}")
        except GalleryError as exc:
            Logger.warning(f"Git 自动安装失败: {exc.message}")
            _show_manual(title="手动安装 Git", command=git_manual_command(), parent=parent)
    return status


def install_with_uv(packages: list[str], *, index_url: str = "", uv_path: str | None = None) -> None:
    executable = uv_path or ensure_uv(interactive=False)
    command = [executable, "pip", "install", "--python", sys.executable]
    if index_url:
        command += ["--index-url", index_url]
    command += packages
    Logger.info(f"安装 Python 依赖: {' '.join(packages)}（镜像: {_redact(index_url) or '默认'}）")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_INSTALL_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GalleryError(PYTHON_DEPENDENCY_INSTALL_FAILED, "uv 安装依赖失败", str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-4000:]
        raise GalleryError(PYTHON_DEPENDENCY_INSTALL_FAILED, "uv 安装依赖失败", detail)
    importlib.invalidate_caches()
    Logger.info("Python 依赖安装完成")


def ensure_python_dependencies(
    requirements: list[str] | tuple[str, ...],
    *,
    plugin_id: str = "",
    interactive: bool = False,
    install: bool = False,
    index_url: str = "",
    parent: Any = None,
) -> list[str]:
    """检查并按需安装依赖；返回仍然缺失的包（空列表表示就绪）。"""
    specs = [str(item).strip() for item in requirements if str(item).strip()]
    missing = missing_packages(specs)
    if not missing:
        return []
    command = manual_command(missing, index_url)
    message = f"插件 {plugin_id or '插件'} 缺少 Python 依赖：\n" + "\n".join(f"  - {item}" for item in missing)
    if not install:
        raise GalleryError(
            PYTHON_DEPENDENCY_MISSING,
            f"缺少 Python 依赖: {', '.join(missing)}",
            command,
            params={"packages": missing, "command": command},
        )

    choice = _ask_choice(
        title="缺少插件依赖",
        message=message,
        detail=(
            "自动安装会使用 uv 把依赖安装到当前 Python 环境。\n"
            f"镜像源：{_redact(index_url) or '默认'}\n\n"
            f"手动安装命令：\n{command}"
        ),
        parent=parent,
        interactive=interactive,
    )
    if choice == "manual":
        _show_manual(title="手动安装依赖", command=command, parent=parent)
        raise GalleryError(PYTHON_DEPENDENCY_MISSING, "已选择手动安装依赖", command)
    if choice != "auto":
        raise GalleryError(PYTHON_DEPENDENCY_MISSING, "已跳过依赖安装", command)

    uv_path = ensure_uv(interactive=interactive, index_url=index_url, parent=parent)
    install_with_uv(missing, index_url=index_url, uv_path=uv_path)
    remaining = missing_packages(specs)
    if remaining:
        raise GalleryError(
            PYTHON_DEPENDENCY_INSTALL_FAILED,
            f"依赖安装后仍缺少: {', '.join(remaining)}",
            command,
        )
    record_event(
        "plugin.dependencies_installed",
        category="plugin",
        payload={"plugin_id": plugin_id, "packages": missing, "mirror": bool(index_url)},
    )
    return []


__all__ = [
    "ToolStatus",
    "ensure_python_dependencies",
    "ensure_tools",
    "ensure_uv",
    "find_git",
    "find_uv",
    "git_manual_command",
    "import_name",
    "install_with_uv",
    "manual_command",
    "missing_packages",
    "parse_requirement",
    "tool_status",
    "uv_manual_command",
]
