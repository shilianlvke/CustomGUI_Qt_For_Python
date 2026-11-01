"""路径解析测试：config.paths（项目根锚定，独立于 cwd）与 PathFactory。

后半部分锁死「应用资产跟着插件走」的机制：应用不该把资源塞进项目根的
``resource/``，而应放在 ``apps/<app>/brand/customui/...``，由基座自动纳入
解析链。每条断言都对应一个曾经的真实故障，见各测试的 docstring。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import customgui
from customgui import package_root
from customgui.appcore import LANGUAGE_OPTIONS
from customgui.appcore.sysx.common.static_func import PathFinder
from customgui.appcore.sysx.config.paths import iter_files, project_root, resolve_path


def test_resolve_from_project_root():
    path = resolve_path("resource/customui/settings")

    assert path.exists()
    assert path.is_dir()
    assert path.is_absolute()


def test_project_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMGUI_ROOT_DIR", str(tmp_path))
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")

    assert project_root() == tmp_path.resolve()
    assert resolve_path("marker.txt") == (tmp_path / "marker.txt").resolve()


def test_iter_files_collects_sorted_yaml():
    files = iter_files("resource/customui/themes", ".yaml")

    names = [path.stem for path in files]
    assert "default" in names
    assert names == sorted(names)
    assert all(path.is_file() for path in files)


def test_path_factory_is_independent_from_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    icon = PathFinder.set_svg_icon("icon_setting")
    icon_path = Path(icon)

    assert icon_path.exists()
    assert "resource" in icon_path.as_posix()


# ==========================================================================
# 应用品牌层（<app>/brand/customui/...）与惰性语言发现
# ==========================================================================
def _write_language(directory: Path, name: str, body: str = "UI:\n  ui_Ok: OK\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.yaml"
    target.write_text(body, encoding="utf-8")
    return target


def _fresh(apps_dir: Path, resource_dirs=()):
    """在独立配置下重新解析（每次 invalidate，避免上一用例的缓存干扰）。"""
    customgui.configure(
        apps_dir=apps_dir,
        resource_dirs=list(resource_dirs),
        data_dir=apps_dir.parent / "data",
        force_reload=True,
    )
    LANGUAGE_OPTIONS.invalidate()

    from customgui.appcore.sysx.config.paths import resource_roots

    return resource_roots()


@pytest.fixture(autouse=True)
def _restore_base_config():
    """用完复原配置，避免污染同文件外的其他测试。"""
    yield
    customgui.configure(
        apps_dir=package_root().parent.parent / "apps",
        resource_dirs=(),
        force_reload=True,
    )
    LANGUAGE_OPTIONS.invalidate()


# -- 布局解析 --------------------------------------------------------------
def test_app_brand_is_a_resource_root(tmp_path):
    """``<app>/brand``（其下直接是 ``customui/``）必须被识别为资源根。"""
    app = tmp_path / "apps" / "demo"
    (app / "brand" / "customui" / "languages").mkdir(parents=True)
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    roots = _fresh(tmp_path / "apps")
    target = (app / "brand").resolve()

    assert target in roots
    # 品牌层要排在基座包内之前，否则覆盖不生效
    assert roots.index(target) < len(roots) - 1


def test_bare_customui_dir_is_not_a_resource_root(tmp_path):
    """只有 ``<app>/customui`` 而没有 ``brand/`` 时不得当作资源根。

    一旦把 ``<app>/customui`` 当根，调用方的 ``customui/themes`` 会拼成
    ``customui/customui/themes``——多一层，什么都找不到。
    """
    app = tmp_path / "apps" / "bare"
    (app / "customui" / "languages").mkdir(parents=True)
    (app / "config.yml").write_text("app_name: bare\n", encoding="utf-8")

    roots = _fresh(tmp_path / "apps")

    assert all("bare" not in str(root) for root in roots), roots


def test_root_with_nested_resource_sinks_one_level(tmp_path):
    """``<root>/resource/customui/...`` 这类历史布局仍然可用（下沉一级）。"""
    root = tmp_path / "project"
    (root / "resource" / "customui" / "languages").mkdir(parents=True)

    roots = _fresh(tmp_path / "apps", resource_dirs=[root])

    assert (root / "resource").resolve() in roots
    assert root.resolve() not in roots


def test_configured_dir_without_nested_resource_is_used_directly(tmp_path):
    """其下直接是 ``customui/`` 的目录不再下沉。"""
    brand = tmp_path / "project" / "brand"
    (brand / "customui" / "languages").mkdir(parents=True)

    roots = _fresh(tmp_path / "apps", resource_dirs=[brand])

    assert brand.resolve() in roots


def test_app_brand_has_priority_over_package(tmp_path):
    """品牌层优先于基座包内资源。"""
    app = tmp_path / "apps" / "demo"
    _write_language(app / "brand" / "customui" / "languages", "zh_cn", "UI:\n  ui_Ok: 品牌\n")
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    _fresh(tmp_path / "apps")

    from customgui.appcore.sysx.config.paths import find_resource

    found = find_resource("resource/customui/languages/zh_cn.yaml")
    assert found is not None
    # 命中的必须是品牌层那份，而不是基座包内的
    assert found == (app / "brand" / "customui" / "languages" / "zh_cn.yaml")
    assert "品牌" in found.read_text(encoding="utf-8")


def test_no_duplicate_roots(tmp_path):
    """同一目录不得在资源根里出现两次（会导致重复扫描）。"""
    app = tmp_path / "apps" / "demo"
    (app / "brand" / "customui").mkdir(parents=True)
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    roots = _fresh(tmp_path / "apps", resource_dirs=[app / "brand"])

    assert len(roots) == len(set(roots))


# -- 惰性语言发现 ----------------------------------------------------------
def test_language_options_discovers_app_brand_languages(tmp_path):
    """应用品牌层里的语言文件能被 ``LANGUAGE_OPTIONS`` 自动发现。"""
    app = tmp_path / "apps" / "demo"
    languages = app / "brand" / "customui" / "languages"
    _write_language(languages, "zh_tw")
    _write_language(languages, "ja_jp")
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    _fresh(tmp_path / "apps")

    assert "ja_jp" in LANGUAGE_OPTIONS
    assert "zh_tw" in LANGUAGE_OPTIONS


def test_language_options_is_lazy_not_import_time(tmp_path):
    """导入期不得锁死：``configure()`` 之后新增的语言必须可见。

    这正是「应用根目录被迫保留 ``resource/``」的历史根因——资源根在模块
    导入时还没配置，导入期求值等于把扫描结果焊死在基座包内。
    """
    (tmp_path / "apps").mkdir()
    _fresh(tmp_path / "apps")
    before = set(LANGUAGE_OPTIONS)

    app = tmp_path / "apps" / "late"
    _write_language(app / "brand" / "customui" / "languages", "ja_jp")
    (app / "config.yml").write_text("app_name: late\n", encoding="utf-8")

    _fresh(tmp_path / "apps")
    after = set(LANGUAGE_OPTIONS)

    assert "ja_jp" not in before
    assert "ja_jp" in after


def test_language_options_supports_list_semantics():
    """惰性视图要兼容调用方的序列用法（``cycle()`` 依赖 ``index``）。"""
    options = LANGUAGE_OPTIONS
    assert len(options) == len(list(options))
    assert tuple(options) == tuple(iter(options))
    assert options[0] == list(options)[0]
    assert options.index(options[0]) == 0
    assert "zh_cn" in options
    assert options.count("zh_cn") == 1
    assert repr(options).startswith("(")


def test_language_cycle_works(tmp_path):
    """``Language.cycle()`` 必须在惰性视图下正常工作。"""
    (tmp_path / "apps").mkdir()
    _fresh(tmp_path / "apps")

    from customgui.appcore import Language

    original = Language.current()
    try:
        first = Language.cycle()
        second = Language.cycle()
        assert first in LANGUAGE_OPTIONS
        assert second in LANGUAGE_OPTIONS
        assert first != second
    finally:
        Language.apply(original)
