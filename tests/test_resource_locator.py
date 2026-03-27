"""模块说明。"""

from pathlib import Path

import pytest

from AppCore.SYS.other.resource_locator import ResourceLocator
from AppCore.SYS.other.static_func import PathFinder


def test_resource_locator_resolves_from_project_root() -> None:
    """测试用例：test_resource_locator_resolves_from_project_root。

    职责:
    - 验证目标行为符合预期。
    """
    path = ResourceLocator.resolve("resource/CustomUI/settings")

    if not (path.exists()):
        pytest.fail("Assertion failed")
    if not (path.is_dir()):
        pytest.fail("Assertion failed")


def test_path_factory_is_independent_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试用例：test_path_factory_is_independent_from_cwd。"""
    monkeypatch.chdir(tmp_path)

    icon = PathFinder.set_svg_icon("icon_setting")
    icon_path = Path(icon)

    if not (icon_path.exists()):
        pytest.fail("Assertion failed")
    if "resource" not in icon_path.as_posix():
        pytest.fail("Assertion failed")
