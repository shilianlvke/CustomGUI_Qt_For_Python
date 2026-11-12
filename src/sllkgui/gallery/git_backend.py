"""Git 后端：只做 fetch/checkout/rev-parse，不执行仓库 hooks。

安全约束（对应方案 §13.2）：

- 仅允许 ``https://`` / ``ssh://`` / ``git@host:path``；``file://`` 需显式放行；
- 禁止 ``ext::`` 传输协议；
- ``core.hooksPath`` 指向空目录，仓库内 hooks 永远不会执行；
- ``GIT_TERMINAL_PROMPT=0``，认证失败立即返回而不是卡住终端；
- 不递归子模块；
- 所有调用带超时。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sllkgui.appcore import Logger

from .defaults import GIT_CLONE_TIMEOUT, GIT_LS_REMOTE_TIMEOUT
from .errors import GIT_TIMEOUT, GIT_UNAVAILABLE, GIT_URL_REJECTED, SOURCE_REFRESH_FAILED, GalleryError

_SCP_RE = re.compile(r"^git@[A-Za-z0-9._-]+:[^\s]+$")
_HOOKS_DIR = Path(tempfile.gettempdir()) / "sllkgui-empty-hooks"


def redact_url(url: str) -> str:
    """日志脱敏：去掉 ``https://user:token@host`` 中的凭据。"""
    text = str(url or "")
    if "://" not in text:
        return text
    parts = urlsplit(text)
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def validate_url(url: str, *, allow_local: bool = False) -> str:
    text = str(url or "").strip()
    if not text:
        raise GalleryError(GIT_URL_REJECTED, "Git URL 不能为空")
    lowered = text.lower()
    if lowered.startswith("ext::") or "ext::" in lowered:
        raise GalleryError(GIT_URL_REJECTED, "拒绝 ext:: 传输协议")
    if lowered.startswith("file://"):
        if not allow_local:
            raise GalleryError(GIT_URL_REJECTED, "file:// 源需要 --allow-local 显式放行")
        return text
    if lowered.startswith(("https://", "ssh://")):
        return text
    if _SCP_RE.match(text):
        return text
    if lowered.startswith(("http://",)):
        raise GalleryError(GIT_URL_REJECTED, "只允许 HTTPS/SSH，拒绝明文 HTTP")
    raise GalleryError(GIT_URL_REJECTED, f"不支持的 Git URL: {redact_url(text)}")


def git_available() -> bool:
    return shutil.which("git") is not None


def _git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise GalleryError(GIT_UNAVAILABLE, "未找到 Git，请先安装并加入 PATH")
    return executable


def _hooks_dir() -> Path:
    _HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    return _HOOKS_DIR


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = GIT_CLONE_TIMEOUT,
    code: str = SOURCE_REFRESH_FAILED,
) -> str:
    executable = _git_executable()
    command = [
        executable,
        "-c",
        "protocol.ext.allow=never",
        "-c",
        f"core.hooksPath={_hooks_dir()}",
        "-c",
        "advice.detachedHead=false",
        "-c",
        "submodule.recurse=false",
        *args,
    ]
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    Logger.debug(f"git {' '.join(args)}")
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GalleryError(GIT_TIMEOUT, f"Git 操作超时（{timeout}s）", " ".join(args)) from exc
    except OSError as exc:
        raise GalleryError(GIT_UNAVAILABLE, "Git 无法启动", str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise GalleryError(code, f"Git 操作失败: {' '.join(args[:2])}", detail)
    return (result.stdout or "").strip()


def ls_remote(url: str, ref: str | None = None, *, timeout: int = GIT_LS_REMOTE_TIMEOUT) -> dict[str, str]:
    args = ["ls-remote", "--refs", url]
    if ref:
        args.append(ref)
    output = _run(args, timeout=timeout)
    result: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2:
            result[parts[1]] = parts[0]
    return result


def init_checkout(dest: Path, url: str, ref: str = "HEAD", *, code: str = SOURCE_REFRESH_FAILED) -> str:
    """初始化空仓库并拉取单个 ref，返回 commit SHA。"""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").is_dir():
        _run(["init", "-q", str(dest)], code=code)
        _run(["remote", "add", "origin", url], cwd=dest, code=code)
    else:
        _run(["remote", "set-url", "origin", url], cwd=dest, code=code)
    _run(["fetch", "--depth", "1", "--force", "origin", ref], cwd=dest, code=code)
    _run(["checkout", "--detach", "--force", "FETCH_HEAD"], cwd=dest, code=code)
    return rev_parse(dest)


def clone(url: str, dest: Path, ref: str | None = None, *, allow_local: bool = False) -> str:
    """浅拉取插件/源仓库到 ``dest``，返回 HEAD commit。

    用 ``init + fetch <ref> + checkout`` 而不是 ``git clone --branch``：后者
    无法直接检出裸 commit SHA，而源 entry 安装时校验的正是 commit。
    """
    validate_url(url, allow_local=allow_local)
    return init_checkout(Path(dest), url, ref or "HEAD")


def refresh(url: str, dest: Path, *, allow_local: bool = False) -> str:
    validate_url(url, allow_local=allow_local)
    return init_checkout(Path(dest), url, "HEAD")


def rev_parse(dest: Path, ref: str = "HEAD") -> str:
    return _run(["rev-parse", ref], cwd=Path(dest), code=SOURCE_REFRESH_FAILED)


def head(dest: Path) -> str:
    return rev_parse(dest, "HEAD")


def is_clean(dest: Path) -> bool:
    output = _run(["status", "--porcelain"], cwd=Path(dest), code=SOURCE_REFRESH_FAILED)
    return not output


__all__ = [
    "clone",
    "git_available",
    "head",
    "init_checkout",
    "is_clean",
    "ls_remote",
    "redact_url",
    "refresh",
    "rev_parse",
    "validate_url",
]
