from __future__ import annotations

import pytest

from sllkgui.gallery.errors import GalleryError
from sllkgui.gallery.manifest import DependencySpec
from sllkgui.gallery.resolver import Candidate, normalize_constraint, resolve, select_version


def _candidate(plugin_id: str, version: str, deps: tuple = (), yanked: bool = False) -> Candidate:
    return Candidate(plugin_id=plugin_id, version=version, source_id="test", dependencies=deps, yanked=yanked)


def test_normalize_caret_and_tilde():
    assert normalize_constraint("^1.2.3") == ">=1.2.3,<2.0.0"
    assert normalize_constraint("^0.2.3") == ">=0.2.3,<0.3.0"
    assert normalize_constraint("~1.2.3") == ">=1.2.3,<1.3.0"


def test_select_highest_stable_skips_yanked():
    candidates = [
        _candidate("a", "1.0.0"),
        _candidate("a", "1.2.0"),
        _candidate("a", "1.3.0", yanked=True),
        _candidate("a", "2.0.0b1"),
    ]
    assert select_version(candidates, ">=1.0.0,<2.0.0").version == "1.2.0"
    assert select_version(candidates, ">=1.0.0", include_prerelease=True).version == "2.0.0b1"


def test_resolve_topological_order():
    dep = DependencySpec("com.example.core", ">=1.0.0")
    index = {
        "com.example.app": [_candidate("com.example.app", "1.0.0", (dep,))],
        "com.example.core": [_candidate("com.example.core", "1.0.0"), _candidate("com.example.core", "1.1.0")],
    }
    ordered = resolve({"com.example.app": ""}, index)
    assert [item.plugin_id for item in ordered] == ["com.example.core", "com.example.app"]
    assert ordered[0].version == "1.1.0"


def test_resolve_missing_and_cycle():
    with pytest.raises(GalleryError) as exc:
        resolve({"com.example.app": ""}, {})
    assert exc.value.code == "PLUGIN_DEPENDENCY_MISSING"

    a = _candidate("a", "1.0.0", (DependencySpec("b", ""),))
    b = _candidate("b", "1.0.0", (DependencySpec("a", ""),))
    with pytest.raises(GalleryError) as exc:
        resolve({"a": ""}, {"a": [a], "b": [b]})
    assert exc.value.code == "PLUGIN_DEPENDENCY_CYCLE"


def test_resolve_conflict():
    a = _candidate("a", "1.0.0", (DependencySpec("c", ">=2.0.0"),))
    b = _candidate("b", "1.0.0", (DependencySpec("c", "<2.0.0"),))
    c1 = _candidate("c", "1.0.0")
    c2 = _candidate("c", "2.0.0")
    with pytest.raises(GalleryError) as exc:
        resolve({"a": "", "b": ""}, {"a": [a], "b": [b], "c": [c1, c2]})
    assert exc.value.code in {"PLUGIN_DEPENDENCY_CONFLICT", "PLUGIN_VERSION_NOT_FOUND"}
