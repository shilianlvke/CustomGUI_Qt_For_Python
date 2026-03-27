from pathlib import Path

from AppCore.SYS.other.resource_locator import ResourceLocator
from AppCore.SYS.other.static_func import PathFinder


def test_resource_locator_resolves_from_project_root():
    """测试用例：test_resource_locator_resolves_from_project_root。

    职责:
    - 验证目标行为符合预期。
    """
    path = ResourceLocator.resolve("resource/CustomUI/settings")

    assert path.exists()
    assert path.is_dir()


def test_path_factory_is_independent_from_cwd(tmp_path, monkeypatch):
    "测试用例：test_path_factory_is_independent_from_cwd。"
    monkeypatch.chdir(tmp_path)

    icon = PathFinder.set_svg_icon("icon_setting")
    icon_path = Path(icon)

    assert icon_path.exists()
    assert "resource" in icon_path.as_posix()

