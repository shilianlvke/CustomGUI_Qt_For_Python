"""路径解析测试：config.paths（项目根锚定，独立于 cwd）与 PathFactory。"""

from pathlib import Path

from AppCore.SYS.config.paths import iter_files, project_root, resolve_path
from AppCore.SYS.other.static_func import PathFinder


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
