"""语言包完整性测试：四种语言必须逐键对齐。

为什么需要这条测试
------------------
语言文件是「缺一个键就静默回落成 key 本身」的弱契约——不会报错，只会在
界面上露出 ``ui_Foo`` 这样的裸 key。新增一种语言时最容易漏译，所以用
测试把「键集合完全一致 + 无空串 + 无品牌残留」钉死。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from customgui import package_root
from customgui.appcore import LANGUAGE_OPTIONS

LANGUAGES_DIR = package_root() / "_resources" / "customui" / "languages"
REFERENCE = "zh_cn"
EXPECTED_LANGUAGES = ("zh_cn", "en_us", "zh_tw", "ja_jp")
SECTIONS = ("custom_ui", "UI", "TEXT", "Log")


def _load(name: str) -> dict:
    path = LANGUAGES_DIR / f"{name}.yaml"
    assert path.is_file(), f"缺少语言文件 {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.fixture(scope="module")
def reference() -> dict:
    return _load(REFERENCE)


@pytest.mark.parametrize("language", EXPECTED_LANGUAGES)
def test_language_file_exists(language):
    assert (LANGUAGES_DIR / f"{language}.yaml").is_file()


@pytest.mark.parametrize("language", EXPECTED_LANGUAGES)
@pytest.mark.parametrize("section", SECTIONS)
def test_key_sets_match_reference(reference, language, section):
    """每种语言的每一段都必须与 zh_cn 的键集合完全相同。"""
    expected = set(reference.get(section) or {})
    actual = set(_load(language).get(section) or {})
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"{language}.{section} 缺少键: {sorted(missing)}"
    assert not extra, f"{language}.{section} 存在多余键: {sorted(extra)}"


@pytest.mark.parametrize("language", EXPECTED_LANGUAGES)
def test_no_empty_values(language):
    data = _load(language)
    empties = [
        f"{section}.{key}"
        for section in SECTIONS
        for key, value in (data.get(section) or {}).items()
        if not str(value).strip()
    ]
    assert not empties, f"{language} 存在空译文: {empties}"


@pytest.mark.parametrize("language", EXPECTED_LANGUAGES)
def test_page_section_is_empty_mapping(language):
    """``PAGE`` 段由应用注入，基座侧必须保持空映射（不能是 None）。"""
    data = _load(language)
    assert data.get("PAGE") == {}


@pytest.mark.parametrize("language", ("zh_tw", "ja_jp"))
def test_overlay_languages_have_no_brand_fields(language):
    """反哺到基座的语言文件只允许基座字段，不得夹带应用品牌信息。"""
    data = _load(language)
    custom_ui = data.get("custom_ui") or {}
    assert custom_ui.get("sys_name") == "CustomGUI"
    assert custom_ui.get("sys_author") == "shilianlvke"
    assert custom_ui.get("sys_license") == "MulanPSL-2.0"
    # 不得出现应用名/应用专属文案
    blob = yaml.safe_dump(data, allow_unicode=True)
    for brand in ("PyCL2", "pycl2", "Minecraft", "启动器", "啟動器", "ランチャー"):
        assert brand not in blob, f"{language} 残留应用品牌字段: {brand}"


def test_overlay_languages_use_base_semantics():
    """``ui_Hide`` / ``ui_Show`` 必须是基座的「隐藏/显示」，不是应用的「收起菜单」。"""
    zh_tw = _load("zh_tw")["UI"]
    ja_jp = _load("ja_jp")["UI"]
    assert zh_tw["ui_Hide"] == "隱藏"
    assert zh_tw["ui_Show"] == "顯示"
    assert ja_jp["ui_Hide"] == "非表示"
    assert ja_jp["ui_Show"] == "表示"


def test_language_options_includes_all_shipped_languages():
    """基座自带的四种语言都必须能被 ``LANGUAGE_OPTIONS`` 发现。"""
    options = set(LANGUAGE_OPTIONS)
    for language in EXPECTED_LANGUAGES:
        assert language in options, f"LANGUAGE_OPTIONS 缺少 {language}"


def test_language_files_are_utf8_readable():
    for language in EXPECTED_LANGUAGES:
        path: Path = LANGUAGES_DIR / f"{language}.yaml"
        path.read_text(encoding="utf-8")
