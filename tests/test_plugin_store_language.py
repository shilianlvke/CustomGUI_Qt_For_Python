"""插件管理页四语文案必须逐键对齐（避免切语言后露出裸 key）。"""

from __future__ import annotations

import pytest
import yaml

from sllkgui import package_root

LANGUAGES_DIR = package_root() / "_resources" / "sllkgui" / "languages"
LANGUAGES = ("zh_cn", "en_us", "zh_tw", "ja_jp")


def _flatten(node: dict, prefix: str = "") -> set[str]:
    result: set[str] = set()
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            result |= _flatten(value, path)
        else:
            result.add(path)
    return result


def _load(language: str) -> dict:
    path = LANGUAGES_DIR / f"{language}.yaml"
    assert path.is_file(), f"缺少语言文件 {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.fixture(scope="module")
def reference() -> set[str]:
    return _flatten(_load("zh_cn").get("plugin_store") or {}, "plugin_store")


@pytest.mark.parametrize("language", LANGUAGES)
def test_plugin_store_keys_match(language, reference):
    keys = _flatten(_load(language).get("plugin_store") or {}, "plugin_store")
    assert not (reference - keys), f"{language} 缺少键: {sorted(reference - keys)}"
    assert not (keys - reference), f"{language} 存在多余键: {sorted(keys - reference)}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_plugin_store_values_are_not_empty(language):
    data = _load(language).get("plugin_store") or {}

    def walk(node):
        for value in node.values():
            if isinstance(value, dict):
                yield from walk(value)
            else:
                yield value

    empties = [value for value in walk(data) if not str(value).strip()]
    assert not empties, f"{language} 存在空文案: {empties}"
