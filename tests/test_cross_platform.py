"""跨平台冒烟：非 Windows 环境下的降级路径必须可用。

基座的亚克力材质、托盘、快捷键修饰键都有 Windows 特化分支。CI 只跑
Linux runner，因此「非 Windows 会不会崩」必须在 CI 里被验证，而不是
等有人真在 Linux 上装一次才发现。

这些用例在任何平台都应通过：它们断言的是**降级行为**，而非 Windows
专属行为。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_acrylic_degrades_gracefully_off_windows():
    """非 Windows 上亚克力判定为不可用，但接口不得抛异常。"""
    from sllkgui.guicore import acrylic

    if sys.platform != "win32":
        assert acrylic.acrylic_supported() is False
        assert acrylic.acrylic_active() is False

    # 接口在任何平台都要给出合法数值
    assert 0 <= acrylic.acrylic_transparency() <= 100
    assert 0 <= acrylic.glass_strength() <= 100


def test_acrylic_transparency_is_complement_of_opacity():
    """透明度与不透明度互为补数，两个平台都必须成立。"""
    from sllkgui.guicore import acrylic

    _, opacity = acrylic.acrylic_options()
    assert acrylic.acrylic_transparency() == 100 - max(0, min(100, opacity))


def test_shortcut_modifiers_per_platform():
    """修饰键解析必须能显式指定平台，不依赖运行机器。"""
    from sllkgui.guicore.shortcuts import KeyBinding

    windows = KeyBinding.parse("Ctrl+Shift+A", platform="win32")
    darwin = KeyBinding.parse("Ctrl+Shift+A", platform="darwin")
    linux = KeyBinding.parse("Ctrl+Shift+A", platform="linux")

    # 三种平台都能解析出主键与修饰键
    for binding in (windows, darwin, linux):
        assert binding.key or binding.sequence


def test_shortcut_registry_accepts_explicit_platform():
    """快捷键注册表允许显式平台，便于在任意机器上复现另一平台的解析。"""
    from sllkgui.guicore.shortcuts import ShortcutRegistry

    registry = ShortcutRegistry(platform="win32")
    assert registry.platform == "win32"


def test_offscreen_platform_is_detected():
    """离屏渲染下必须判定为不支持亚克力（否则会拿到无效窗口句柄）。"""
    from sllkgui.guicore import acrylic

    if "offscreen" in os.environ.get("QT_QPA_PLATFORM", "").lower():
        assert acrylic.acrylic_supported() is False


@pytest.mark.parametrize("module", ["sllkgui.gallery.dependencies", "sllkgui.gallery.lint"])
def test_headless_modules_import_without_qt(module: str):
    """插件校验链不得拉起 Qt：源仓库 CI 用它做插件准入。

    必须在**子进程**里验证——当前 pytest 进程早已因其它用例加载了
    PySide6，进程内检查测不出「这次导入是否引入 Qt」。
    """
    import subprocess
    import sys as _sys

    code = (
        "import sys\n"
        f"import {module}\n"
        "assert not [k for k in sys.modules if k.startswith('PySide6')], "
        f"'{module} 拉起了 PySide6'\n"
    )
    result = subprocess.run(
        [_sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, f"{module} 不应拉起 PySide6：\n{result.stdout}\n{result.stderr}"
