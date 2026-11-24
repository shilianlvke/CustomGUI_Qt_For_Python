"""Mihoutao mascot engine core.

Faithful port of temp/mihoutao.html vanilla JS engine: superellipse geometry,
eye morphing, eight decoration layers, spring physics, 39-state machine.
All numbers come from spec.json (same source as the prototype).
Rendering builds the same SVG DOM consumed by QSvgRenderer.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

_SPEC_PATH = Path(__file__).with_name("spec.json")
SPEC: dict[str, Any] = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
EYES = SPEC["eyes"]
SHAPES = SPEC["shapes"]
PALETTE = SPEC["palette"]
STATES = SPEC["states"]
GROUPS = SPEC["groups"]
EYE_KEYS = SPEC["eyeKeys"]
EYE_ORDER = list(EYES)

#: 原型 viewBox：本体 + 阴影的外接框
BASE_VIEW_BOX = (-1.36, -1.34, 2.72, 2.70)
#: 装饰层最大外延：radar/pulse 环取 1.18*K，orbit 卫星 1.3，sparkle 与 zZ 更远
DECO_EXTENT = 1.86


def canvas_scale() -> float:
    """窗口边长相对「本体边长」的倍率。

    外扩 viewBox 后，若窗口尺寸不变，本体就会按比例缩小。乘以该倍率可让本体
    维持 ``size`` 指定的像素大小，多出来的部分正好用作装饰层留白。
    """
    x, y, w, h = BASE_VIEW_BOX
    pad_x = DECO_EXTENT - w / 2
    return (w + pad_x * 2) / w


def view_box() -> str:
    """渲染窗口：在原型 viewBox 基础上外扩，承接 overflow: visible 的装饰层。

    原型 CSS 对 ``.disk svg`` 声明 ``overflow: visible``，因此 radar 扫描环、
    pulse 脉冲、orbit 卫星、sparkle 星芒与 zZ 会画到 viewBox 之外而**不被裁切**。
    Qt 的 QSvgRenderer 默认按 viewBox 裁切，这里用更大的 viewBox 等效还原该行为，
    避免装饰层被切掉一截。
    """
    x, y, w, h = BASE_VIEW_BOX
    pad_x = DECO_EXTENT - w / 2
    pad_y = DECO_EXTENT - h / 2
    return f"{x - pad_x:.4f} {y - pad_y:.4f} {w + pad_x * 2:.4f} {h + pad_y * 2:.4f}"


SKIN = "#5E3A1C"
CORE = "#F8FDF1"
EYE_COLOR = "#22301C"
SEED = "#2C3A22"
SKIN_W = 0.105


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def super_poly(rx: float, ry: float, exp: float, n: int = 64) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    power = 2.0 / exp
    for i in range(n + 1):
        angle = (i / n) * math.tau
        c, s = math.cos(angle), math.sin(angle)
        pts.append((math.copysign(abs(c) ** power, c) * rx, math.copysign(abs(s) ** power, s) * ry))
    return pts


def poly_to_path(pts: list[tuple[float, float]]) -> str:
    d = f"M{pts[0][0]:.4f} {pts[0][1]:.4f}"
    for x, y in pts[1:]:
        d += f"L{x:.4f} {y:.4f}"
    return d + "Z"


def shape_path(shape: dict[str, Any]) -> str:
    return poly_to_path(super_poly(shape["rx"], shape["ry"], shape["exp"], 64))


def eye_points(p: dict[str, float], hw: float, hh: float, sign: int) -> list[tuple[float, float]]:
    n = 20
    e = max(1.2, p["exp"])
    top: list[tuple[float, float]] = []
    bot: list[tuple[float, float]] = []
    for i in range(n + 1):
        x = -1 + 2 * i / n
        base = max(0.0, 1 - abs(x) ** e) ** (1 / e)
        top.append((x * hw * p["w"], p["cy"] * hh - p["top"] * hh * base))
        bot.append((x * hw * p["w"], p["cy"] * hh + p["bot"] * hh * base))
    pts = top + list(reversed(bot))
    a = math.radians(p["tilt"] * sign)
    if not a:
        return pts
    ca, sa = math.cos(a), math.sin(a)
    return [(x * ca - y * sa, x * sa + y * ca) for x, y in pts]


def star_path(cx: float, cy: float, outer: float, inner: float, points: int = 4) -> str:
    d = ""
    for i in range(points * 2):
        r = inner if i % 2 else outer
        a = (i / (points * 2)) * math.tau - math.pi / 2
        d += f"{'L' if i else 'M'}{cx + math.cos(a) * r:.4f} {cy + math.sin(a) * r:.4f}"
    return d + "Z"


def arc_path(r: float, from_deg: float, sweep_deg: float) -> str:
    a0 = math.radians(from_deg)
    a1 = math.radians(from_deg + sweep_deg)
    x0, y0 = math.cos(a0) * r, math.sin(a0) * r
    x1, y1 = math.cos(a1) * r, math.sin(a1) * r
    large = 1 if abs(sweep_deg) > 180 else 0
    direction = 1 if sweep_deg >= 0 else 0
    return f"M{x0:.4f} {y0:.4f}A{r} {r} 0 {large} {direction} {x1:.4f} {y1:.4f}"


class Spring:
    __slots__ = ("x", "v", "t", "k", "d")

    def __init__(self, x: float, k: float, d: float) -> None:
        self.x = x
        self.v = 0.0
        self.t = x
        self.k = k
        self.d = d

    def step(self, dt: float) -> None:
        if not dt > 0:
            return
        n = max(1, math.ceil(dt / (1 / 240)))
        h = dt / n
        for _ in range(n):
            a = -self.k * (self.x - self.t) - self.d * self.v
            self.v += a * h
            self.x += self.v * h


class MihoutaoEngine:
    def __init__(self, *, shape: str = "blob", color: str = "green", mode: str = "onboarding") -> None:
        self.shape_name = shape if shape in SHAPES else next(iter(SHAPES))
        self.color_id = color if color in PALETTE else "green"
        self.mode = mode
        self.state = "idle"
        self.follow_pointer = False
        self.gaze_target: tuple[float, float] | None = None
        self.emphasis = False
        self.mood_n = 0

        self.spin = Spring(0, 82, 13)
        self.tilt = Spring(0, 150, 16)
        self.squash = Spring(1, 320, 26)
        self.stretch = Spring(1, 320, 26)
        self.bob = Spring(0, 120, 18)
        self.blink = Spring(1, 540, 30)
        self.gaze_x = Spring(0, 130, 20)
        self.gaze_y = Spring(0, 130, 20)
        self.eye_t = Spring(1, 260, 22)
        self.shape_t = Spring(1, 210, 22)

        self.eye_from = dict(EYES["round"])
        self.eye_to = dict(EYES["round"])
        self.eye_from_idx = 0
        self.eye_to_idx = 0
        self.shape_from = dict(SHAPES[self.shape_name])
        self.shape_now = dict(SHAPES[self.shape_name])

        self.t = 0.0
        self.state_at = 0.0
        self.shake_at = -1e9
        self.eye_idx = 0
        self.eye_next_at = random.uniform(1200, 2400)
        self.blink_at = 3200.0
        self.blinking = False
        self.blink_stop = 0.0
        self.double_blink = False
        self.hop_at = -1.0
        self.deco_kind = "none"
        self.deco_scale = 1.32
        self.parts: list[dict[str, Any]] = []
        self.trick_at = 3000.0
        self.saccade_at = 1200.0
        self.saccade = [0.0, 0.0]
        self.shadow_id = "shadow-mihoutao"
        #: 主题强调色覆盖：仅作用于未显式声明 ring 的状态，保留原型语义
        self.accent_color: str | None = None

        self.set_color(self.color_id)
        self.set_state("curious")

    def current_eye(self) -> dict[str, float]:
        t = clamp(self.eye_t.x, 0, 1)
        return {k: lerp(self.eye_from[k], self.eye_to[k], t) for k in EYE_KEYS}

    def morph(self, name: str) -> None:
        if name not in EYES:
            name = "round"
        self.eye_from = self.current_eye()
        self.eye_from_idx = self.eye_to_idx
        self.eye_to = dict(EYES[name])
        self.eye_to_idx = EYE_ORDER.index(name)
        self.eye_t.x = 0.0
        self.eye_t.v = 0.0
        self.eye_t.t = 1.0

    def set_state(self, name: str) -> None:
        if name not in STATES:
            return
        self.state = name
        self.state_at = self.t
        self.eye_idx = 0
        cfg = STATES[name]
        self.eye_next_at = self.t + random.uniform(cfg["hold"][0], cfg["hold"][1])
        self.morph(cfg["eyes"][0])
        self.tilt.t = cfg.get("tilt", 0)
        self.set_deco(cfg.get("deco", "none"))
        if cfg.get("hop"):
            self.hop_once()
        if cfg.get("stretch"):
            self.stretch.x = 0.86
            self.stretch.v = 0.0
            self.squash.x = 1.12
            self.squash.v = 0.0
        if cfg.get("shake"):
            self.shake_at = self.t
        self.trick_at = self.t + random.uniform(2200, 4200)
        self.mood_n += 1

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "onboarding":
            self.mood_n = 0
            self.set_state("idle")

    def set_shape(self, name: str) -> None:
        if name not in SHAPES:
            return
        self.shape_from = dict(self.shape_now)
        self.shape_name = name
        self.shape_t.x = 0.0
        self.shape_t.v = 0.0
        self.shape_t.t = 1.0

    def set_color(self, color_id: str) -> None:
        if color_id not in PALETTE:
            return
        self.color_id = color_id
        if self.deco_kind != "none":
            self.set_deco(self.deco_kind, force=True)

    def set_deco_scale(self, value: float) -> None:
        self.deco_scale = clamp(value, 0.55, 1.5)
        self.set_deco(self.deco_kind, force=True)

    def set_deco(self, kind: str, force: bool = False) -> None:
        if not force and kind == self.deco_kind:
            return
        self.deco_kind = kind
        if not kind or kind == "none":
            return
        if kind == "sparkle":
            k = self.deco_scale
            spots = [(0, -1.17), (-1.09, -0.65), (1.09, -0.56), (0.92, 0.56), (-0.94, 0.61)]
            self.sparkle_spots = [(x * k, y * k) for x, y in spots]

    def set_accent_color(self, color: str | None) -> None:
        """设置主题强调色；传 None 恢复原型默认（影响描边与徽标底色）。"""
        self.accent_color = color or None

    def set_follow_pointer(self, value: bool) -> None:
        self.follow_pointer = bool(value)
        if not value:
            self.gaze_target = None

    def set_emphasis(self, value: bool) -> None:
        self.emphasis = bool(value)

    def spin_once(self, turns: float = 1) -> None:
        self.spin.t += 360 * turns

    def hop_once(self) -> None:
        self.hop_at = self.t
        self.squash.x = 0.80
        self.squash.v = 0.0
        self.stretch.x = 1.14
        self.stretch.v = 0.0
        self.bob.x = 0.22
        self.bob.v = 0.0

    def burst_once(self) -> None:
        light = PALETTE[self.color_id]["light"]
        for _ in range(22):
            a = random.uniform(0, math.tau)
            sp = random.uniform(1.1, 3.0)
            self.parts.append(
                {
                    "x": math.cos(a) * 0.62,
                    "y": math.sin(a) * 0.62,
                    "vx": math.cos(a) * sp,
                    "vy": math.sin(a) * sp - 0.8,
                    "r": random.uniform(0.05, 0.10),
                    "life": 0.0,
                    "max": random.uniform(700, 1000),
                    "color": light,
                    "born": self.t,
                }
            )

    def update(self, dt: float) -> None:
        # 与原型 _tick 一致：单帧 dt 上限 50ms，防止弹簧在长间隔后发散。
        dt_sec = min(0.05, dt) if dt > 0 else 0.0
        self.t += dt_sec * 1000
        cfg = STATES[self.state]
        t = self.t

        if t >= self.eye_next_at:
            self.eye_idx = (self.eye_idx + 1) % len(cfg["eyes"])
            self.morph(cfg["eyes"][self.eye_idx])
            self.eye_next_at = t + random.uniform(cfg["hold"][0], cfg["hold"][1])

        if self.mode == "onboarding" and t - self.state_at > 1200:
            moods = SPEC["onboarding"]
            n = self.mood_n
            self.set_state("idle" if n % 2 == 0 else moods[((n - 1) // 2) % len(moods)])
            self.state_at = t

        if cfg.get("blink") and not self.blinking and t >= self.blink_at:
            self.blinking = True
            self.blink_stop = t + 110
            self.blink.x = 0.06
            self.blink.v = 0.0
            self.double_blink = random.random() < 0.35
        if self.blinking and t >= self.blink_stop:
            self.blinking = False
            self.blink.t = 1.0
            if self.double_blink:
                self.double_blink = False
                self.blink_at = t + 180
            elif cfg.get("blink"):
                self.blink_at = t + random.uniform(cfg["blink"][0], cfg["blink"][1])

        period = cfg["period"] / 1000
        self.bob.t = -cfg["bob"] * (0.5 + 0.5 * math.sin(math.tau * (t / 1000) / period))

        if self.hop_at >= 0 and t - self.hop_at > 70:
            self.squash.t = 1.0
            self.stretch.t = 1.0
            self.hop_at = -1.0

        if self.gaze_target is not None:
            self.gaze_x.t = self.gaze_target[0]
            self.gaze_y.t = self.gaze_target[1]
        else:
            if t >= self.saccade_at:
                self.saccade = [random.uniform(-1, 1) * 0.055, random.uniform(-1, 1) * 0.04]
                self.saccade_at = t + random.uniform(900, 2200)
            self.gaze_x.t = self.saccade[0]
            self.gaze_y.t = self.saccade[1]

        for spring in (
            self.spin,
            self.tilt,
            self.squash,
            self.stretch,
            self.bob,
            self.blink,
            self.gaze_x,
            self.gaze_y,
            self.eye_t,
            self.shape_t,
        ):
            spring.step(dt_sec)

        if self.shape_t.x < 0.999:
            k = clamp(self.shape_t.x, 0, 1)
            for key in ("rx", "ry", "exp", "rot", "core"):
                self.shape_now[key] = lerp(self.shape_from[key], SHAPES[self.shape_name][key], k)

        if cfg.get("trick") == "wiggle" and t >= self.trick_at:
            self.tilt.x += random.uniform(-6, 6)
            self.trick_at = t + random.uniform(2200, 4200)

        alive = []
        for part in self.parts:
            part["life"] = t - part["born"]
            part["vy"] += 2.4 * dt_sec
            part["x"] += part["vx"] * dt_sec
            part["y"] += part["vy"] * dt_sec
            if part["life"] < part["max"]:
                alive.append(part)
        self.parts = alive

    def render_svg(self) -> str:
        t = self.t
        cfg = STATES[self.state]
        sx = clamp(self.squash.x, 0.6, 1.45)
        sy = (1 / math.sqrt(sx)) * clamp(self.stretch.x, 0.72, 1.32)
        ang = self.spin.x + self.tilt.x + self.shape_now["rot"]
        shake_x = 0.0
        if cfg.get("shake") and t - self.shake_at < 720:
            k = 1 - (t - self.shake_at) / 720
            shake_x = math.sin(t / 26) * 0.05 * k
            ang += math.sin(t / 30) * 2.4 * k
        if self.emphasis:
            ang += math.sin(t / 900) * 1.6
        mover_transform = (
            f"translate({shake_x:.4f} {self.bob.x:.4f}) rotate({ang:.3f}) "
            f"translate(0 {self.shape_now['ry'] * (1 - sy):.4f}) scale({sx:.4f} {sy:.4f})"
        )
        shadow_rx = self.shape_now["rx"] * 1.16 * (0.88 + 0.12 * sx)
        shadow_opacity = 0.9 - 0.4 * (sy - 1) - min(0.4, abs(self.bob.x) * 2)
        face_d = shape_path(self.shape_now)
        body_d = shape_path(
            {
                "rx": self.shape_now["rx"] * 1.03,
                "ry": self.shape_now["ry"] * 1.02,
                "exp": self.shape_now["exp"],
            }
        )
        cs = self.shape_now["core"]
        seed_sway = math.sin(t / 2100) * 0.9
        seed_elems = []
        for i in range(18):
            base = (i / 18) * 360 + 15
            seed_elems.append(
                f'<g transform="rotate({base + seed_sway:.3f}) translate(0 -0.615)">'
                '<ellipse cx="0" cy="0" rx="0.023" ry="0.072"/></g>'
            )
        p = self.current_eye()
        bk = clamp(self.blink.x, 0.05, 1)
        hw = 0.16
        hh = 0.215 * bk
        gx = clamp(self.gaze_x.x, -0.06, 0.06)
        gy = clamp(self.gaze_y.x, -0.05, 0.05)
        dx = 0.225
        dy = -0.045

        def eye_path(sign: int) -> str:
            pts = eye_points(p, hw, hh, sign)
            d = ""
            for i, (x, y) in enumerate(pts):
                d += f"{'L' if i else 'M'}{x + sign * dx + gx:.4f} {y + gy + dy:.4f}"
            return d + "Z"

        ring = cfg.get("ring") or self.accent_color or SKIN
        k = self.deco_scale
        deco_back = self._render_deco_back(t, k)
        deco_front = self._render_deco_front(t, k)
        parts_svg = self._render_parts()
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + view_box() + '">'
            '<defs><radialGradient id="' + self.shadow_id + '">'
            '<stop offset="0%" stop-color="#000" stop-opacity="0.18"/>'
            '<stop offset="70%" stop-color="#000" stop-opacity="0.07"/>'
            '<stop offset="100%" stop-color="#000" stop-opacity="0"/>'
            "</radialGradient></defs>"
            f'<ellipse cx="0" cy="1.06" rx="{shadow_rx:.4f}" ry="0.17" fill="url(#{self.shadow_id})" opacity="{shadow_opacity:.3f}"/>'
            f"<g>{deco_back}</g>"
            f'<g transform="{mover_transform}">'
            f'<path d="{body_d}" fill="{SKIN}" stroke="{SKIN}" stroke-width="0.10" stroke-linejoin="round"/>'
            f'<path d="{face_d}" fill="{PALETTE[self.color_id]["light"]}" stroke="{ring}" stroke-width="{SKIN_W}" stroke-linejoin="round"/>'
            f'<g fill="{SEED}">{"".join(seed_elems)}</g>'
            f'<ellipse cx="0" cy="0.02" rx="{0.505 * cs:.4f}" ry="{0.515 * cs:.4f}" fill="{CORE}"/>'
            f'<g fill="{EYE_COLOR}"><path d="{eye_path(-1)}"/><path d="{eye_path(1)}"/></g>'
            "</g>"
            f"<g>{deco_front}</g>"
            f"<g>{parts_svg}</g>"
            "</svg>"
        )

    def _render_deco_back(self, t: float, k: float) -> str:
        kind = self.deco_kind
        ink = SKIN
        if kind == "radar":
            sweep_deg = (t / 1100) * 360
            return (
                f'<circle cx="0" cy="0" r="{1.06 * k:.4f}" fill="none" stroke="{ink}" stroke-width="0.018" opacity="0.45"/>'
                f'<circle cx="0" cy="0" r="{1.18 * k:.4f}" fill="none" stroke="{ink}" stroke-width="0.018" opacity="0.26"/>'
                f'<g transform="rotate({sweep_deg:.2f})">'
                f'<path d="{arc_path(1.18 * k, -52, 52)}L0 0Z" fill="{ink}" opacity="0.26"/>'
                f'<path d="M0 0L{1.18 * k:.4f} 0" stroke="{ink}" stroke-width="0.028" stroke-linecap="round" opacity="0.9"/>'
                "</g>"
            )
        if kind == "pulse":
            k1 = (t % 1500) / 1500
            k2 = ((t + 750) % 1500) / 1500
            return (
                f'<circle cx="0" cy="0" r="{(1.0 + k1 * 0.20) * k:.4f}" fill="none" stroke="{ink}" stroke-width="0.028" opacity="{(1 - k1) * 0.68:.3f}"/>'
                f'<circle cx="0" cy="0" r="{(1.0 + k2 * 0.20) * k:.4f}" fill="none" stroke="{ink}" stroke-width="0.028" opacity="{(1 - k2) * 0.68:.3f}"/>'
            )
        return ""

    def _render_deco_front(self, t: float, k: float) -> str:
        kind = self.deco_kind
        ink = SKIN
        cfg = STATES[self.state]
        ring = cfg.get("ring") or self.accent_color or "#B24A3C"
        fade = clamp((t - self.state_at) / 260, 0, 1)
        if kind == "dots":
            a0 = (t / 900) * math.tau
            out = ""
            for i in range(3):
                a = a0 + i * math.tau / 3
                r = 0.06 + 0.022 * math.sin(t / 260 + i)
                opacity = 0.65 + 0.35 * math.sin(t / 260 + i)
                out += f'<circle cx="{math.cos(a) * 1.10 * k:.4f}" cy="{math.sin(a) * 1.10 * k:.4f}" r="{r:.4f}" opacity="{opacity:.3f}"/>'
            return f'<g fill="{ink}">{out}</g>'
        if kind == "progress":
            f = (t % 2400) / 2400
            return (
                f'<circle cx="0" cy="0" r="{1.12 * k:.4f}" fill="none" stroke="{ink}" stroke-width="0.05" opacity="0.30"/>'
                f'<path d="{arc_path(1.12 * k, -90, 359.9 * f)}" fill="none" stroke="{ink}" stroke-width="0.05" stroke-linecap="round"/>'
            )
        if kind == "orbit":
            a = (t / 700) * math.tau
            out = ""
            for offset, radius, opacity in ((0, 0.085, 1.0), (-0.22, 0.06, 0.42), (-0.44, 0.05, 0.2)):
                out += f'<circle cx="{math.cos(a + offset) * 1.3:.4f}" cy="{math.sin(a + offset) * 1.3:.4f}" r="{radius}" fill="{ink}" opacity="{opacity}"/>'
            return out
        if kind == "badge":
            s = (1 + 0.1 * math.sin(t / 220)) * fade
            tx = 0.86 * k
            ty = -0.98 * k
            return f'<g transform="translate({tx:.3f} {ty:.3f}) scale({s:.3f})"><circle cx="0" cy="0" r="0.19" fill="{ring}"/><circle cx="0" cy="0" r="0.062" fill="#1a1916"/></g>'
        if kind == "sparkle":
            out = ""
            for i, (x, y) in enumerate(self.sparkle_spots):
                kk = 0.55 + 0.45 * math.sin(t / 300 + i * 1.3)
                opacity = 0.3 + 0.7 * kk
                scale = 0.7 + 0.4 * kk
                d = star_path(0, 0, 0.115, 0.034, 4)
                out += f'<path d="{d}" transform="translate({x} {y}) scale({scale:.3f})" opacity="{opacity:.3f}"/>'
            return f'<g fill="{ink}">{out}</g>'
        if kind == "zzz":
            out = ""
            for i in range(3):
                kk = ((t + i * 800) % 2400) / 2400
                x = (0.56 + kk * 0.41) * k
                y = -0.9 - kk * 0.66
                opacity = math.sin(math.pi * kk) * 0.95
                size = 0.22 + kk * 0.16
                out += f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size:.3f}" font-family="Segoe UI, sans-serif" text-anchor="middle" fill="{ink}" opacity="{opacity:.3f}">z</text>'
            return out
        return ""

    def _render_parts(self) -> str:
        out = ""
        for part in self.parts:
            kk = max(0.0, 1 - part["life"] / part["max"])
            out += f'<circle cx="{part["x"]:.3f}" cy="{part["y"]:.3f}" r="{part["r"] * (0.4 + 0.6 * kk):.3f}" fill="{part["color"]}" opacity="{kk * 0.95:.2f}" stroke="#ffffff" stroke-width="0.014" stroke-opacity="{kk * 0.55:.2f}"/>'
        return out

    def snapshot(self) -> dict[str, Any]:
        cfg = STATES[self.state]
        return {
            "state": self.state,
            "eyeFrom": self.eye_from_idx,
            "eyeTo": self.eye_to_idx,
            "spin": self.spin.x,
            "squash": self.squash.x,
            "overlay": cfg.get("deco") if cfg.get("deco") != "none" else "—",
            "shape": self.shape_now.get("label", SHAPES[self.shape_name]["label"]),
        }
