"""插件开发规范检查（``sllkgui plugin lint``）。

检查项对应方案 §4.4：日志/遥测接入、禁止 print/自建文件日志、禁止动态执行与
``sys.path`` 修改、四语言齐全、图标存在、错误码/权限声明基础校验。输出可直接
JSON 序列化，供源仓库 CI 使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .manifest import GalleryError, load_manifest

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
    "tests",
    "examples",
    "docs",
    "packaging",
    "scripts",
}
_PY_SUFFIXES = {".py"}

_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("PRINT", re.compile(r"(?<![\w.])print\s*\("), "禁止 print()，请使用 ctx.log / ctx.logger"),
    ("LOGGING_BASIC", re.compile(r"logging\.basicConfig\s*\("), "禁止 logging.basicConfig()"),
    ("FILE_HANDLER", re.compile(r"\b(FileHandler|RotatingFileHandler|TimedRotatingFileHandler)\s*\("), "禁止自建文件日志 handler"),
    ("SYS_PATH", re.compile(r"\bsys\.path\s*\.(insert|append|extend)\s*\("), "禁止修改 sys.path"),
    ("EVAL", re.compile(r"(?<![\w.])eval\s*\("), "禁止 eval()"),
    ("EXEC", re.compile(r"(?<![\w.])exec\s*\("), "禁止 exec()"),
    ("SYS_EXIT", re.compile(r"\bsys\.exit\s*\("), "禁止 sys.exit()"),
    ("QAPP", re.compile(r"\bQApplication\s*\("), "禁止创建 QApplication"),
    ("QMAINWINDOW", re.compile(r"\bQMainWindow\s*\("), "禁止创建 QMainWindow"),
    ("SUBPROCESS", re.compile(r"\b(subprocess|os\.system|os\.popen)\b"), "使用子进程需要声明 subprocess 权限"),
    ("REQUESTS", re.compile(r"\b(requests|httpx|urllib\.request|urlopen)\b"), "网络访问需要声明 network 权限"),
)

#: 允许出现在注释/字符串里的误报噪声：lint 只做静态扫描，不追求 100% 精确
_ALLOW_MARKER = "plugin-lint: ignore"


@dataclass
class LintIssue:
    level: str
    code: str
    message: str
    file: str = ""
    line: int = 0


@dataclass
class LintReport:
    plugin_id: str = ""
    version: str = ""
    errors: list[LintIssue] = field(default_factory=list)
    warnings: list[LintIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plugin_id": self.plugin_id,
            "version": self.version,
            "errors": [item.__dict__ for item in self.errors],
            "warnings": [item.__dict__ for item in self.warnings],
        }


def _iter_python(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        result.append(path)
    return sorted(result)


def _scan_file(path: Path, root: Path, permission_values: set[str], report: LintReport) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        report.warnings.append(LintIssue("warning", "READ_FAILED", f"无法读取: {exc}", str(path)))
        return
    relative = path.relative_to(root).as_posix()
    if any(_ALLOW_MARKER + "-file" in line for line in lines[:5]):
        return
    for number, line in enumerate(lines, start=1):
        if _ALLOW_MARKER in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for code, pattern, message in _PATTERNS:
            if not pattern.search(line):
                continue
            if code == "SUBPROCESS" and "subprocess" in permission_values:
                continue
            if code == "REQUESTS" and "network" in permission_values:
                continue
            report.warnings.append(LintIssue("warning", code, message, relative, number))


def _check_language(root: Path, report: LintReport) -> None:
    folder = root / "resource" / "lang"
    expected = ("zh_cn", "zh_tw", "en_us", "ja_jp")
    tables: dict[str, set[str]] = {}
    for locale in expected:
        path = folder / f"{locale}.yml"
        if not path.is_file():
            report.errors.append(
                LintIssue("error", "I18N_MISSING", f"缺少语言文件 resource/lang/{locale}.yml", "resource/lang")
            )
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            report.errors.append(LintIssue("error", "I18N_INVALID", f"{locale}.yml 解析失败: {exc}"))
            continue
        tables[locale] = set(_flatten_keys(raw))
    if not tables:
        return
    baseline_locale = "en_us" if "en_us" in tables else next(iter(tables))
    baseline = tables[baseline_locale]
    for locale, keys in tables.items():
        missing = baseline - keys
        if missing:
            preview = ", ".join(sorted(missing)[:5])
            report.errors.append(
                LintIssue(
                    "error",
                    "I18N_KEYS",
                    f"{locale}.yml 缺少 {len(missing)} 个键（相对 {baseline_locale}）: {preview}",
                )
            )


def _flatten_keys(data: Any, prefix: str = "") -> list[str]:
    result: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            result.extend(_flatten_keys(value, f"{prefix}.{key}" if prefix else str(key)))
    else:
        result.append(prefix)
    return result


def _check_manifest(root: Path, report: LintReport) -> None:
    try:
        manifest = load_manifest(root)
    except GalleryError as exc:
        report.errors.append(LintIssue("error", exc.code, exc.message))
        return
    report.plugin_id = manifest.plugin_id
    report.version = manifest.version
    for surface in manifest.surfaces:
        if not surface.icon:
            report.warnings.append(
                LintIssue("warning", "ICON_MISSING", f"Surface {surface.surface_id} 未声明图标")
            )
            continue
        icon = root / surface.icon
        if icon.suffix.lower() != ".svg":
            report.warnings.append(
                LintIssue("warning", "ICON_FORMAT", f"图标建议使用 SVG: {surface.icon}")
            )
        if not icon.is_file():
            report.errors.append(LintIssue("error", "ICON_NOT_FOUND", f"图标不存在: {surface.icon}"))


def _check_telemetry(root: Path, report: LintReport) -> None:
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in _iter_python(root))
    for token, code, message in (
        ("ctx.log(", "TELEMETRY_LOG", "未发现 ctx.log()：插件必须接入基座日志"),
        ("ctx.event(", "TELEMETRY_EVENT", "未发现 ctx.event()：插件必须接入基座遥测"),
        ("ctx.timing(", "TELEMETRY_TIMING", "未发现 ctx.timing()：耗时操作必须使用基座计时"),
    ):
        if token not in text:
            report.errors.append(LintIssue("error", code, message))


def lint_plugin(path: Path) -> LintReport:
    root = Path(path).resolve()
    if root.is_file():
        root = root.parent
    report = LintReport()
    if not root.is_dir():
        report.errors.append(LintIssue("error", "PATH_NOT_FOUND", f"目录不存在: {root}"))
        return report
    _check_manifest(root, report)
    try:
        manifest = load_manifest(root)
        permissions = {item.value for item in manifest.permissions}
    except GalleryError:
        permissions = set()
    for file in _iter_python(root):
        _scan_file(file, root, permissions, report)
    _check_language(root, report)
    _check_telemetry(root, report)
    return report


__all__ = ["LintIssue", "LintReport", "lint_plugin"]
