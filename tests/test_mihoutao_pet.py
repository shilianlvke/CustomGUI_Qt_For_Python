"""猕猴桃桌面宠物：引擎同源、偏好持久化与基座原生集成。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from sllkgui.gallery.runtime import GalleryRuntime
from sllkgui.guicore.pet.controller import DEFAULTS, load_preferences, save_preferences
from sllkgui.guicore.pet.engine.core import (
    EYES,
    GROUPS,
    PALETTE,
    SHAPES,
    SPEC,
    STATES,
    MihoutaoEngine,
    arc_path,
    canvas_scale,
    eye_points,
    shape_path,
    star_path,
    super_poly,
)

#: 原型 mihoutao.html 的 JS 引擎实际输出（node 采样），用于差分比对
_GOLDEN = Path(__file__).with_name("fixtures_mihoutao_geometry.json")


def test_spec_matches_prototype_counts():
    """规格表与原型 mihoutao.html 完全一致。"""
    assert len(SPEC["states"]) == 39
    assert len(SPEC["shapes"]) == 18
    assert len(SPEC["palette"]) == 11
    assert len(EYES) == 25
    assert sum(len(group["states"]) for group in GROUPS) == 39
    assert {name for group in GROUPS for name in group["states"]} == set(STATES)
    assert SPEC["onboarding"] == ["curious", "happy", "shy", "proud", "listening", "surprised", "playful"]
    assert EYES["round"] == {"top": 0.56, "bot": 0.56, "exp": 2.0, "cy": 0.0, "w": 1.0, "tilt": 0}
    assert SHAPES["blob"]["label"] == "圆果"
    assert PALETTE["green"]["light"] == "#BCE39B"


def test_geometry_is_identical_to_prototype():
    """差分校验：18 果形路径、眼型顶点、弧线、星芒与原型 JS 逐字符一致。"""
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    for name, expected in golden["shapes"].items():
        assert shape_path(SHAPES[name]) == expected, name
    for name, pts in golden["eyes"].items():
        got = [(round(x, 4), round(y, 4)) for x, y in eye_points(EYES[name], 0.16, 0.215, -1)]
        assert got == [(round(x, 4), round(y, 4)) for x, y in pts], name
    got_super = [(round(x, 4), round(y, 4)) for x, y in super_poly(1.0, 0.9, 2.4, 64)]
    assert got_super == [(round(x, 4), round(y, 4)) for x, y in golden["super"]]
    assert arc_path(1.12, -90, 180) == golden["arc"]
    assert star_path(0, 0, 0.115, 0.034, 4) == golden["star"]


def test_engine_renders_every_state_and_shape():
    engine = MihoutaoEngine()
    assert engine.state == "curious"
    svg = engine.render_svg()
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    # viewBox 在原型基础上外扩，承接 overflow: visible 的装饰层
    assert 'viewBox="-1.8600 -1.8500 3.7200 3.7200"' in svg
    assert canvas_scale() > 1.0
    assert svg.count("<ellipse") >= 18  # 18 颗放射籽 + 白心 + 阴影

    engine.spin_once()
    assert engine.spin.t == 360
    for _ in range(60):
        engine.update(1 / 60)
    assert engine.spin.x > 0

    engine.hop_once()
    assert engine.squash.x == 0.80
    engine.burst_once()
    assert len(engine.parts) == 22
    for _ in range(90):
        engine.update(1 / 60)
    assert engine.parts == []

    for shape in SHAPES:
        engine.set_shape(shape)
        for _ in range(30):
            engine.update(1 / 60)
        assert "path" in engine.render_svg()
    for color in PALETTE:
        engine.set_color(color)
        assert engine.color_id == color
    for name in STATES:
        engine.set_state(name)
        engine.update(0.016)
        assert engine.render_svg().endswith("</svg>")


def test_deco_layers_all_render():
    """8 类装饰层：每类都真的画出额外元素。"""
    engine = MihoutaoEngine()
    engine.set_deco("none", force=True)
    baseline = engine.render_svg()
    for kind in ("dots", "radar", "progress", "orbit", "badge", "pulse", "sparkle", "zzz"):
        engine.set_deco(kind, force=True)
        engine.update(0.016)
        assert engine.deco_kind == kind
        assert len(engine.render_svg()) > len(baseline), kind
    engine.set_deco_scale(1.5)
    assert engine.deco_scale == 1.5
    engine.set_deco_scale(9.0)
    assert engine.deco_scale == 1.5  # 与原型 clamp 一致


def test_dt_is_clamped_like_prototype_tick():
    engine = MihoutaoEngine()
    engine.update(5.0)  # 单帧上限 50ms，防止弹簧发散
    assert engine.t == pytest.approx(50.0, abs=1e-6)


def test_preferences_roundtrip_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("sllkgui.guicore.pet.controller.data_root", lambda: tmp_path)
    assert load_preferences() == DEFAULTS
    assert save_preferences({"shape": "gem", "color": "violet", "size": 300}) is True
    loaded = load_preferences()
    assert loaded["shape"] == "gem" and loaded["color"] == "violet" and loaded["size"] == 300
    # 非法值回落默认，不抛出
    assert save_preferences({"shape": "nope", "color": "nope", "size": 9999}) is True
    assert load_preferences()["shape"] == "blob"


def test_controller_start_and_shutdown(tmp_path, monkeypatch):
    monkeypatch.setattr("sllkgui.guicore.pet.controller.data_root", lambda: tmp_path)
    app = QApplication.instance() or QApplication([])
    assert app is not None
    from sllkgui.guicore.pet import MihoutaoPetController

    pet = MihoutaoPetController()
    pet.start()
    assert pet.engine is not None
    pet.spin()
    pet.set_shape("gem")
    pet.set_color("violet")
    assert pet.preferences["shape"] == "gem"
    pet.set_follow_pointer(False)
    assert pet.engine.follow_pointer is False
    pet.shutdown()  # 幂等
    pet.shutdown()


def test_pet_does_not_add_surfaces(tmp_path):
    """宠物是基座原生：不注册 Surface，空插件时 surface_count 仍为 0。"""
    runtime = GalleryRuntime("run", data_dir=tmp_path / "run-empty", plugin_dirs=[])
    try:
        runtime.bootstrap()
        assert runtime.records == []
        assert runtime.registry.surface_count() == 0
    finally:
        runtime.shutdown()
