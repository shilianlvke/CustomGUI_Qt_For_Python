"""背景模糊：设置声明、实时生效、边缘安全、持久化与启动恢复。"""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QColor, QImage

from sllkgui.appcore import KEY_BACKGROUND_BLUR, SettingsSession, ensure_core_pages, user_settings
from sllkgui.guicore.window.window.main_window import CWindow
from sllkgui.guis.windows.main_window.controller import SettingsController
from sllkgui.guis.windows.main_window.setup_main_window import SetupMainWindow


def _make_image(path, color: QColor, *, width: int = 240, height: int = 160) -> str:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(color)
    assert image.save(str(path))
    return str(path)


def _make_split_image(path, *, width: int = 240, height: int = 160) -> str:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))
    for x in range(width // 2):
        for y in range(height):
            image.setPixelColor(x, y, QColor("#000000"))
    assert image.save(str(path))
    return str(path)


def _isolate_user_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(user_settings, "data_root", lambda: tmp_path)
    user_settings.reset_user_settings_cache()
    ensure_core_pages()


def _blur_spec():
    from sllkgui.appcore.settings.base import build_core_pages

    for page in build_core_pages():
        for section in page.sections:
            for spec in section.items:
                if spec.key == "background_blur":
                    return spec
    raise AssertionError("外观设置页缺少 background_blur")


def test_background_blur_is_declared_as_continuous_slider(tmp_path, monkeypatch):
    _isolate_user_settings(tmp_path, monkeypatch)

    spec = _blur_spec()
    assert spec.default == user_settings.BACKGROUND_BLUR_DEFAULT == 0
    assert spec.minimum == 0
    assert spec.maximum == user_settings.BACKGROUND_BLUR_MAX == 60
    assert spec.control.value == "slider"
    assert spec.live_preview is True
    assert spec.suffix == "px"
    assert SettingsSession().value(KEY_BACKGROUND_BLUR) == 0


def test_blur_only_changes_background_layer_and_keeps_window_size(qapp, tmp_path):
    """模糊后仍是窗口尺寸的背景 pixmap；实色背景不会出现透明边或变色。"""
    window = CWindow()
    window.resize(240, 160)
    try:
        path = _make_image(tmp_path / "solid.png", QColor("#8822aa"))
        assert window.set_background_image(path, "stretch")
        assert window.set_background_blur(20) == 20

        surface = window._background_surface()
        assert surface is not None
        assert surface.size() == window.size()
        image = surface.toImage()
        center = image.pixelColor(119, 79)
        corner = image.pixelColor(0, 0)
        assert abs(center.red() - 0x88) <= 3
        assert abs(center.green() - 0x22) <= 3
        assert abs(center.blue() - 0xAA) <= 3
        # 补边 + 裁剪后边缘应基本不透明（Qt 高斯核尾部允许 1~2% 损耗）
        assert corner.alpha() >= 245
    finally:
        window.close()


def test_blur_softens_image_boundary_and_zero_keeps_sharp(qapp, tmp_path):
    window = CWindow()
    window.resize(240, 160)
    try:
        path = _make_split_image(tmp_path / "split.png")
        assert window.set_background_image(path, "stretch")
        sharp = window._background_surface().toImage()
        assert sharp.pixelColor(119, 80).name() == "#000000"
        assert sharp.pixelColor(120, 80).name() == "#ffffff"

        window.set_background_blur(12)
        blurred = window._background_surface().toImage()
        left = blurred.pixelColor(119, 80)
        right = blurred.pixelColor(120, 80)
        assert left.red() > 40, "边界内侧应混入亮色"
        assert right.red() < 220, "边界外侧应混入暗色"

        window.set_background_blur(0)
        assert window._background_surface().toImage().pixelColor(119, 80).name() == "#000000"
    finally:
        window.close()


def test_blur_switching_background_keeps_strength(qapp, tmp_path):
    """切换背景图不清空模糊设置：新图立即沿用当前强度。"""
    window = CWindow()
    window.resize(240, 160)
    try:
        first = _make_image(tmp_path / "first.png", QColor("#335577"))
        second = _make_split_image(tmp_path / "second.png")
        assert window.set_background_image(first, "fill")
        window.set_background_blur(30)

        assert window.set_background_image(second, "stretch")
        assert window.background_blur() == 30
        blurred = window._background_surface().toImage()
        assert blurred.pixelColor(119, 80).name() != "#000000"
    finally:
        window.close()


def test_blur_clamps_and_no_background_is_safe(qapp):
    window = CWindow()
    try:
        assert window.background_blur() == 0
        assert window.set_background_blur(999) == 60
        assert window.set_background_blur(-3) == 0
        assert window.set_background_blur("20") == 20
        assert window.set_background_blur(True) == 0
        # 没有背景图（纯色 / 透明窗口）：设置成功写入但不产生背景层
        assert window.set_background_blur(25) == 25
        assert window._background_surface() is None
        assert window.set_background_image("", "fill") is False
        assert window._background_surface() is None
    finally:
        window.close()


def test_blur_persists_and_restores_on_startup(qapp, tmp_path, monkeypatch):
    _isolate_user_settings(tmp_path, monkeypatch)
    path = _make_image(tmp_path / "bg.png", QColor("#224466"))

    assert user_settings.save_user_settings(background_blur=22)
    assert user_settings.load_user_settings()["background_blur"] == 22

    target = CWindow()
    try:
        window = SimpleNamespace(ui=SimpleNamespace(window=target))
        assert SetupMainWindow.restore_background(
            window,
            {"background_image": path, "background_fit": "fit", "background_blur": 22},
        )
        assert target.background_image() == path
        assert target.background_blur() == 22

        # 配置缺失 / 非法值：回落默认 0，不报错
        assert SetupMainWindow.restore_background(
            window, {"background_image": path, "background_fit": "fit", "background_blur": "bad"}
        )
        assert target.background_blur() == user_settings.BACKGROUND_BLUR_DEFAULT
        # 纯色背景（空路径）恢复返回 False 表示没有背景图，但模糊值仍被复位。
        assert not SetupMainWindow.restore_background(window, {"background_image": "", "background_fit": "fill"})
        assert target.background_blur() == 0
    finally:
        target.close()


def test_blur_preview_updates_runtime_background_layer():
    calls: list[int] = []
    controller = object.__new__(SettingsController)
    controller._window = SimpleNamespace(
        ui=SimpleNamespace(window=SimpleNamespace(set_background_blur=lambda value: calls.append(value)))
    )
    controller._logger = SimpleNamespace(debug=lambda *_args, **_kwargs: None)
    controller._settings_window = None
    controller._previewing_theme = False

    controller._preview_setting(KEY_BACKGROUND_BLUR, 18)
    controller._preview_setting(KEY_BACKGROUND_BLUR, 0)

    assert calls == [18, 0]
