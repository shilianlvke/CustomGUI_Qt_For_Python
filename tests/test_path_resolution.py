"""路径解析测试：config.paths（项目根锚定，独立于 cwd）与 PathFactory。

后半部分锁死「应用资产跟着插件走」的机制：应用不该把资源塞进项目根的
``resource/``，而应放在 ``apps/<app>/brand/sllkgui/...``，由基座自动纳入
解析链。每条断言都对应一个曾经的真实故障，见各测试的 docstring。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sllkgui
from sllkgui import package_root
from sllkgui.appcore import LANGUAGE_OPTIONS
from sllkgui.appcore.sysx.common.static_func import PathFinder
from sllkgui.appcore.sysx.config.paths import iter_file_layers, iter_files, project_root, resolve_path


def test_resolve_from_project_root():
    path = resolve_path("resource/sllkgui/settings")

    assert path.exists()
    assert path.is_dir()
    assert path.is_absolute()


def test_project_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SLLKGUI_ROOT_DIR", str(tmp_path))
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")

    assert project_root() == tmp_path.resolve()
    assert resolve_path("marker.txt") == (tmp_path / "marker.txt").resolve()


def test_iter_files_collects_sorted_yaml():
    files = iter_files("resource/sllkgui/themes", ".yaml")

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
# 应用品牌层（<app>/brand/sllkgui/...）与惰性语言发现
# ==========================================================================
def _write_language(directory: Path, name: str, body: str = "UI:\n  ui_Ok: OK\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.yaml"
    target.write_text(body, encoding="utf-8")
    return target


def _fresh(apps_dir: Path, resource_dirs=()):
    """在独立配置下重新解析（每次 invalidate，避免上一用例的缓存干扰）。"""
    sllkgui.configure(
        apps_dir=apps_dir,
        resource_dirs=list(resource_dirs),
        data_dir=apps_dir.parent / "data",
        force_reload=True,
    )
    LANGUAGE_OPTIONS.invalidate()

    from sllkgui.appcore.sysx.config.paths import resource_roots

    return resource_roots()


@pytest.fixture(autouse=True)
def _restore_base_config():
    """用完复原配置，避免污染同文件外的其他测试。

    注意必须用 ``force_reload=True``：本文件的 ``_fresh()`` 也是这么做的，
    上下文一旦被重建，再用普通 ``configure()`` 会抛
    ``ConfigAlreadyLoadedError``。
    """
    yield
    sllkgui.configure(
        apps_dir=package_root().parent.parent / "apps",
        resource_dirs=(),
        force_reload=True,
    )
    LANGUAGE_OPTIONS.invalidate()


# -- 布局解析 --------------------------------------------------------------
def test_app_brand_is_a_resource_root(tmp_path):
    """``<app>/brand``（其下直接是 ``sllkgui/``）必须被识别为资源根。"""
    app = tmp_path / "apps" / "demo"
    (app / "brand" / "sllkgui" / "languages").mkdir(parents=True)
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    roots = _fresh(tmp_path / "apps")
    target = (app / "brand").resolve()

    assert target in roots
    # 品牌层要排在基座包内之前，否则覆盖不生效
    assert roots.index(target) < len(roots) - 1


def test_bare_sllkgui_dir_is_not_a_resource_root(tmp_path):
    """只有 ``<app>/sllkgui`` 而没有 ``brand/`` 时不得当作资源根。

    一旦把 ``<app>/sllkgui`` 当根，调用方的 ``sllkgui/themes`` 会拼成
    ``sllkgui/sllkgui/themes``——多一层，什么都找不到。
    """
    app = tmp_path / "apps" / "bare"
    (app / "sllkgui" / "languages").mkdir(parents=True)
    (app / "config.yml").write_text("app_name: bare\n", encoding="utf-8")

    roots = _fresh(tmp_path / "apps")

    assert all("bare" not in str(root) for root in roots), roots


def test_root_with_nested_resource_sinks_one_level(tmp_path):
    """``<root>/resource/sllkgui/...`` 这类历史布局仍然可用（下沉一级）。"""
    root = tmp_path / "project"
    (root / "resource" / "sllkgui" / "languages").mkdir(parents=True)

    roots = _fresh(tmp_path / "apps", resource_dirs=[root])

    assert (root / "resource").resolve() in roots
    assert root.resolve() not in roots


def test_configured_dir_without_nested_resource_is_used_directly(tmp_path):
    """其下直接是 ``sllkgui/`` 的目录不再下沉。"""
    brand = tmp_path / "project" / "brand"
    (brand / "sllkgui" / "languages").mkdir(parents=True)

    roots = _fresh(tmp_path / "apps", resource_dirs=[brand])

    assert brand.resolve() in roots


def test_app_brand_has_priority_over_package(tmp_path):
    """品牌层优先于基座包内资源。"""
    app = tmp_path / "apps" / "demo"
    _write_language(app / "brand" / "sllkgui" / "languages", "zh_cn", "UI:\n  ui_Ok: 品牌\n")
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    _fresh(tmp_path / "apps")

    from sllkgui.appcore.sysx.config.paths import find_resource

    found = find_resource("resource/sllkgui/languages/zh_cn.yaml")
    assert found is not None
    # 命中的必须是品牌层那份，而不是基座包内的
    assert found == (app / "brand" / "sllkgui" / "languages" / "zh_cn.yaml")
    assert "品牌" in found.read_text(encoding="utf-8")


def test_no_duplicate_roots(tmp_path):
    """同一目录不得在资源根里出现两次（会导致重复扫描）。"""
    app = tmp_path / "apps" / "demo"
    (app / "brand" / "sllkgui").mkdir(parents=True)
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    roots = _fresh(tmp_path / "apps", resource_dirs=[app / "brand"])

    assert len(roots) == len(set(roots))


# -- 同名文件：分层 vs 只取一份 ---------------------------------------------
def _write_theme(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.yaml"
    target.write_text(body, encoding="utf-8")
    return target


def test_iter_file_layers_keeps_every_layer_low_to_high(tmp_path):
    """同名 YAML 必须每层都留着，且顺序是「基座 -> 品牌层」。

    配置装载要在这些层上顺序 ``deep_merge``：只留最高优先级那份，品牌层少写
    一个键就会把基座那层整份挤掉——这正是 ``AppSettings`` 新增必填字段后
    下游启动即崩的根因。
    """
    app = tmp_path / "apps" / "demo"
    brand_default = _write_theme(
        app / "brand" / "sllkgui" / "themes",
        "default",
        'custom_dark_one: "#010101"\n',
    )
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    _fresh(tmp_path / "apps")

    layers = iter_file_layers("resource/sllkgui/themes", ".yaml")

    paths = layers["default.yaml"]
    assert len(paths) == 2, paths  # 断言必须真的收满两层，不能是空扫描
    assert paths[-1] == brand_default.resolve()  # 末位是覆盖层
    assert paths[0].parent != brand_default.parent  # 首位来自基座包内
    assert "010101" in paths[-1].read_text(encoding="utf-8")


def test_iter_files_still_returns_one_file_per_name(tmp_path):
    """``iter_files()`` 保持「同名只给一份」：发现类调用不能被分层影响。"""
    app = tmp_path / "apps" / "demo"
    brand_default = _write_theme(
        app / "brand" / "sllkgui" / "themes",
        "default",
        'custom_dark_one: "#010101"\n',
    )
    (app / "config.yml").write_text("app_name: demo\n", encoding="utf-8")

    _fresh(tmp_path / "apps")

    files = iter_files("resource/sllkgui/themes", ".yaml")
    defaults = [path for path in files if path.stem == "default"]

    assert len(defaults) == 1
    assert defaults[0] == brand_default.resolve()
    # 其余主题（基座自带）仍然在，覆盖层只影响同名的那个
    assert {"bright", "dracula", "eye"} <= {path.stem for path in files}



# -- 惰性语言发现 ----------------------------------------------------------
def test_language_options_discovers_app_brand_languages(tmp_path):
    """应用品牌层里的语言文件能被 ``LANGUAGE_OPTIONS`` 自动发现。"""
    app = tmp_path / "apps" / "demo"
    languages = app / "brand" / "sllkgui" / "languages"
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

    用一个基座不自带、也不在品牌层里的语言名来验证（不能拿 ja_jp /
    zh_tw 试，它们现在已经是基座内置语言）。
    """
    (tmp_path / "apps").mkdir()
    _fresh(tmp_path / "apps")
    before = set(LANGUAGE_OPTIONS)
    assert "xx_overlay" not in before

    app = tmp_path / "apps" / "late"
    _write_language(app / "brand" / "sllkgui" / "languages", "xx_overlay")
    (app / "config.yml").write_text("app_name: late\n", encoding="utf-8")

    _fresh(tmp_path / "apps")
    after = set(LANGUAGE_OPTIONS)

    assert "xx_overlay" in after


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

    from sllkgui.appcore import Language

    original = Language.current()
    try:
        first = Language.cycle()
        second = Language.cycle()
        assert first in LANGUAGE_OPTIONS
        assert second in LANGUAGE_OPTIONS
        assert first != second
    finally:
        Language.apply(original)


# -- FIX-06: configure() 契约 ------------------------------------------------
def test_configure_after_context_loaded_raises_on_first_call(tmp_path):
    """FIX-06: 上下文已加载后，reset_config() 之后的首次 configure() 也必须抛错。"""
    # FIX-06: 旧实现只在 _CONFIGURED 为真时检查；reset_config() 清掉该标志后首次调用静默失效。
    from sllkgui.appcore import get_app_context

    try:
        get_app_context(force_reload=True)
        sllkgui.reset_config()
        with pytest.raises(sllkgui.ConfigAlreadyLoadedError):
            sllkgui.configure(apps_dir=tmp_path)
    finally:
        # 复原全局配置：清掉临时字段并用 force_reload 重建上下文（与 autouse fixture 一致）。
        sllkgui.reset_config()
        sllkgui.configure(env_fallback=True, force_reload=True)


def test_env_fallback_false_disables_env_paths(tmp_path, monkeypatch):
    """FIX-06: env_fallback=False 时 apps/诊断目录都不得读 SLLKGUI_* 环境变量。"""
    # FIX-06: 环境变量兜底只由 env_fallback 控制，apps_root/遥测不得绕过它直读。
    env_apps = tmp_path / "env_apps"
    env_diag = tmp_path / "env_diagnostics"
    monkeypatch.setenv("SLLKGUI_APPS_DIR", str(env_apps))
    monkeypatch.setenv("SLLKGUI_DIAGNOSTICS_DIR", str(env_diag))

    try:
        sllkgui.reset_config()
        sllkgui.configure(env_fallback=False, force_reload=True)

        from sllkgui.appcore.sysx.config.paths import apps_root

        assert sllkgui.current_config().resolved_apps_dir() is None, (
            "resolved_apps_dir must ignore SLLKGUI_APPS_DIR when env_fallback is False"
        )
        assert apps_root() != env_apps.resolve(), (
            "apps_root must ignore SLLKGUI_APPS_DIR when env_fallback is False"
        )
        assert sllkgui.current_config().resolved_diagnostics_dir() != env_diag.resolve(), (
            "resolved_diagnostics_dir must ignore SLLKGUI_DIAGNOSTICS_DIR when env_fallback is False"
        )
    finally:
        sllkgui.reset_config()
        sllkgui.configure(env_fallback=True, force_reload=True)


def test_configure_preserves_env_fallback_when_not_passed(tmp_path):
    """FIX-06: 后续 configure() 不传 env_fallback 时保留上次的 False，不被默认 True 覆盖。"""
    # FIX-06: env_fallback 改用 None 哨兵保留历史值，不再每次调用覆盖回 True。
    try:
        sllkgui.configure(env_fallback=False, force_reload=True)
        assert sllkgui.current_config().env_fallback is False, (
            "env_fallback=False must take effect on the first configure call"
        )

        sllkgui.configure(data_dir=tmp_path, force_reload=True)
        assert sllkgui.current_config().env_fallback is False, (
            "configure without env_fallback must preserve the previous False value"
        )
    finally:
        sllkgui.reset_config()
        sllkgui.configure(env_fallback=True, force_reload=True)


def test_resource_dirs_empty_tuple_clears_previous(tmp_path):
    """FIX-06: resource_dirs 传空元组要清空上一次配置的覆盖根。"""
    # FIX-06: 旧实现用 `if resource_dirs` 判断，空序列无法清空历史值。
    overlay = tmp_path / "overlay"
    (overlay / "resource" / "sllkgui" / "languages").mkdir(parents=True)

    try:
        sllkgui.configure(resource_dirs=[overlay], force_reload=True)

        from sllkgui.appcore.sysx.config.paths import resource_roots

        assert (overlay / "resource").resolve() in resource_roots(), (
            "precondition: the overlay root must be active before clearing"
        )

        sllkgui.configure(resource_dirs=(), force_reload=True)
        assert sllkgui.current_config().resource_dirs == (), (
            "an empty resource_dirs sequence must clear all configured overlays"
        )
        assert (overlay / "resource").resolve() not in resource_roots(), (
            "the cleared overlay must no longer appear in resource_roots()"
        )
    finally:
        sllkgui.reset_config()
        sllkgui.configure(env_fallback=True, force_reload=True)
