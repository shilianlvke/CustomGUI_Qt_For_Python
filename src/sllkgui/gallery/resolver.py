"""依赖解析：SemVer 约束、版本选择、冲突/环检测与拓扑排序。

首版只解析插件之间的 Git/SemVer 依赖，不做 Python 包解析（Python 依赖由
插件 ``vendor/`` 自包含）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .errors import (
    PLUGIN_DEPENDENCY_CONFLICT,
    PLUGIN_DEPENDENCY_CYCLE,
    PLUGIN_DEPENDENCY_MISSING,
    PLUGIN_VERSION_NOT_FOUND,
    GalleryError,
)
from .manifest import DependencySpec

_CARET_RE = re.compile(r"^\^(.+)$")
_TILDE_RE = re.compile(r"^~(.+)$")


@dataclass(frozen=True)
class Candidate:
    """某个插件某个版本的候选：由源索引或直接 URL 提供。"""

    plugin_id: str
    version: str
    source_id: str = ""
    dependencies: tuple[DependencySpec, ...] = ()
    yanked: bool = False
    payload: dict = field(default_factory=dict)


def normalize_constraint(text: str) -> str:
    """把 ``^1.2.3`` / ``~1.2.3`` 语法糖展开成 ``SpecifierSet`` 能懂的区间。"""
    value = str(text or "").strip()
    if not value:
        return ""
    caret = _CARET_RE.match(value)
    if caret:
        return _caret_constraint(caret.group(1).strip())
    tilde = _TILDE_RE.match(value)
    if tilde:
        return _tilde_constraint(tilde.group(1).strip())
    return value


def _parse_release(text: str) -> tuple[int, int, int]:
    version = Version(text)
    release = list(version.release) + [0, 0, 0]
    return release[0], release[1], release[2]


def _caret_constraint(text: str) -> str:
    major, minor, patch = _parse_release(text)
    if major > 0:
        upper = f"{major + 1}.0.0"
    elif minor > 0:
        upper = f"0.{minor + 1}.0"
    else:
        upper = f"0.0.{patch + 1}"
    return f">={text},<{upper}"


def _tilde_constraint(text: str) -> str:
    major, minor, _patch = _parse_release(text)
    return f">={text},<{major}.{minor + 1}.0"


def parse_specifier(text: str) -> SpecifierSet:
    normalized = normalize_constraint(text)
    if not normalized:
        return SpecifierSet("")
    try:
        return SpecifierSet(normalized)
    except InvalidSpecifier as exc:
        raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"非法版本约束: {text!r}", str(exc)) from exc


def _version(value: str) -> Version:
    try:
        return Version(value)
    except InvalidVersion as exc:
        raise GalleryError(PLUGIN_VERSION_NOT_FOUND, f"非法版本: {value!r}", str(exc)) from exc


def select_version(
    candidates: list[Candidate],
    constraint: str = "",
    *,
    include_prerelease: bool = False,
    allow_yanked: bool = False,
) -> Candidate | None:
    """选满足约束的最高稳定版；``constraint`` 为空表示不限制。"""
    specifier = parse_specifier(constraint)
    usable = [
        item
        for item in candidates
        if (allow_yanked or not item.yanked)
        and (include_prerelease or not _version(item.version).is_prerelease)
    ]
    if include_prerelease:
        usable = [item for item in candidates if allow_yanked or not item.yanked]
    matching = [
        item for item in usable if specifier.contains(_version(item.version), prereleases=include_prerelease)
    ]
    if not matching:
        return None
    return max(matching, key=lambda item: _version(item.version))


def resolve(
    roots: dict[str, str],
    index: dict[str, list[Candidate]],
    installed: dict[str, str] | None = None,
) -> list[Candidate]:
    """解析依赖图，返回**依赖在前**的安装顺序。

    ``roots``：``{plugin_id: constraint}``；``index``：可用版本；``installed``：
    已安装版本（满足约束时复用，不再安装）。
    """
    installed = installed or {}
    chosen: dict[str, Candidate] = {}
    constraints: dict[str, list[str]] = {}
    visiting: list[str] = []

    def choose(plugin_id: str, constraint: str) -> Candidate:
        constraints.setdefault(plugin_id, []).append(constraint)
        if plugin_id in visiting:
            chain = " -> ".join([*visiting, plugin_id])
            raise GalleryError(PLUGIN_DEPENDENCY_CYCLE, f"依赖环: {chain}", params={"chain": chain})
        candidate = chosen.get(plugin_id)
        if candidate is not None:
            if not _satisfies(candidate.version, constraint):
                raise GalleryError(
                    PLUGIN_DEPENDENCY_CONFLICT,
                    f"{plugin_id} 的版本约束无法同时满足: {constraints[plugin_id]}",
                    params={"plugin_id": plugin_id},
                )
            return candidate

        source = index.get(plugin_id) or []
        if not source:
            raise GalleryError(
                PLUGIN_DEPENDENCY_MISSING,
                f"缺少依赖: {plugin_id}",
                params={"plugin_id": plugin_id},
            )

        # 多约束取交集：逐个候选过滤，避免为 SpecifierSet 手写区间求交
        merged = constraint
        for previous in constraints[plugin_id]:
            if previous and merged and previous != merged:
                merged = f"{merged},{previous}"
            elif previous and not merged:
                merged = previous
        candidate = select_version(source, merged)
        if candidate is None:
            raise GalleryError(
                PLUGIN_DEPENDENCY_CONFLICT if len(constraints[plugin_id]) > 1 else PLUGIN_VERSION_NOT_FOUND,
                f"{plugin_id} 没有满足 {merged or '*'} 的版本",
                params={"plugin_id": plugin_id, "constraint": merged},
            )
        chosen[plugin_id] = candidate
        visiting.append(plugin_id)
        for dependency in candidate.dependencies:
            choose(dependency.plugin_id, dependency.version)
        visiting.pop()

        installed_version = installed.get(plugin_id)
        if installed_version and _satisfies(installed_version, constraint):
            # 已安装且满足约束：不加入安装顺序，但仍需按当前候选继续解析依赖
            pass
        return candidate

    for plugin_id, constraint in roots.items():
        choose(plugin_id, constraint)

    ordered: list[Candidate] = []
    done: set[str] = set()

    def visit(plugin_id: str) -> None:
        if plugin_id in done:
            return
        candidate = chosen.get(plugin_id)
        if candidate is None:
            return
        for dependency in candidate.dependencies:
            visit(dependency.plugin_id)
        done.add(plugin_id)
        installed_version = installed.get(plugin_id)
        if installed_version and installed_version == candidate.version:
            return
        ordered.append(candidate)

    for plugin_id in roots:
        visit(plugin_id)
    return ordered


def _satisfies(version: str, constraint: str) -> bool:
    if not constraint:
        return True
    try:
        return Version(version) in parse_specifier(constraint)
    except GalleryError:
        return False


__all__ = [
    "Candidate",
    "normalize_constraint",
    "parse_specifier",
    "resolve",
    "select_version",
]
