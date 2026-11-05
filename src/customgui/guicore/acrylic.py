"""Windows 亚克力（Acrylic）背景材质（Fluent Design）。

窗口的圆角、阴影与配色仍由 Qt 自绘；本模块只负责把 Windows 的系统级
背景材质挂到**顶层窗口**的 HWND 上，让桌面内容先经过模糊与色调合成
再透出窗口，形成 Fluent Design 的亚克力质感。

平台策略（任何一步失败都只影响观感，不影响窗口创建与业务逻辑）::

    Windows 11 22H2+   ACCENT_ENABLE_ACRYLICBLURBEHIND + 系统圆角 + 深色边框
    Windows 10/更早    不支持；样式表自动回落到不透明主题底色
    非 Windows         不支持；同上

样式表侧由 :func:`customgui.guicore.styles` 依据 :func:`acrylic_active`
决定玻璃层的不透明度，二者必须一起判断，否则会出现「半透明但没有模糊」
的脏画面。
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from functools import lru_cache

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from customgui.appcore import AppSettings, ColorPalette, Logger, get_design_tokens

# ----------------------------------------------------------------------
# Win32 常量与结构体
# ----------------------------------------------------------------------
_WCA_ACCENT_POLICY = 19
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_BLURBEHIND = 3
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

#: DWMWA_WINDOW_CORNER_PREFERENCE = 33（Windows 11 起）
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_ROUND = 2
#: DWMWA_USE_IMMERSIVE_DARK_MODE（20H1 起为 20，更早版本用 19）
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY = 19

#: 未配置或配置不可用时的兜底色调不透明度（0-100）
_DEFAULT_OPACITY = 60
#: 未配置或配置不可用时的兜底玻璃层强度（0 表示沿用配置值）
_DEFAULT_GLASS_STRENGTH = 0
#: 窗口底色允许的最小不透明度。
#: Windows 分层窗口（WA_TranslucentBackground）按像素 Alpha 做命中测试，
#: Alpha 为 0 的区域会把鼠标事件直接透到桌面。即使把亚克力强度拉满，
#: 主窗口也必须保留一层极淡的底色，保证整个窗口仍可点击/拖动。
MIN_WINDOW_GLASS_ALPHA = 0.03

#: 运行期覆盖值：``None`` 表示沿用配置文件里的 acrylic.opacity
_ACRYLIC_TRANSPARENCY: int | None = None
#: 运行期玻璃层强度：0 沿用配置值，100 时表面层完全透明
_GLASS_STRENGTH = _DEFAULT_GLASS_STRENGTH

#: 亚克力降级诊断只记录一次，避免每帧重复刷日志
_LOGGED_KEYS: set[str] = set()


def _log_once(key: str, message: str) -> None:
    """失败路径只记一次 debug 日志；观感问题不应淹没在日志里。"""
    if key in _LOGGED_KEYS:
        return
    _LOGGED_KEYS.add(key)
    Logger.debug(message)


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


if sys.platform == "win32":  # pragma: no cover - 仅在 Windows 上执行
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
else:  # pragma: no cover - 其它平台没有这些 DLL
    _user32 = None
    _dwmapi = None

# ----------------------------------------------------------------------
# 配置与能力判断
# ----------------------------------------------------------------------
def acrylic_options() -> tuple[bool, int]:
    """返回 ``(enabled, opacity)``；配置不可用时按「关闭」处理。"""
    try:
        cfg = AppSettings.acrylic
        return bool(cfg.enabled), int(cfg.opacity)
    except Exception:  # 配置上下文尚未就绪（组件可能在 AppSettings 之前构造）
        return False, _DEFAULT_OPACITY


@lru_cache(maxsize=1)
def _platform_supports_acrylic() -> bool:
    """当前环境是否支持系统级亚克力（Windows 11 22H2+ 且非离屏渲染）。"""
    if sys.platform != "win32" or _user32 is None or _dwmapi is None:
        return False
    # 测试 / CI 的 offscreen 平台没有真实窗口，调用 Win32 只会得到无效句柄
    if "offscreen" in os.environ.get("QT_QPA_PLATFORM", "").lower():
        return False
    try:
        if QApplication.platformName().lower() == "offscreen":
            return False
    except Exception:
        pass
    try:
        return int(sys.getwindowsversion().build) >= 22000
    except Exception as exc:
        _log_once("platform_build", f"亚克力平台版本探测失败：{exc}")
        return False


def acrylic_supported() -> bool:
    """当前窗口环境是否支持原生亚克力材质（与配置开关无关）。"""
    return _platform_supports_acrylic()


def acrylic_active() -> bool:
    """是否应当启用玻璃样式。

    三个条件必须同时成立：配置开启、平台支持、使用无边框标题栏。最后一条
    很关键——原生标题栏窗口没有 ``WA_TranslucentBackground``，半透明样式会
    糊在窗口自身的实色底上，看上去只会更脏。
    """
    enabled, _ = acrylic_options()
    if not enabled or not acrylic_supported():
        return False
    try:
        return bool(AppSettings.custom_title_bar)
    except Exception:
        return False


def acrylic_opacity() -> int:
    """亚克力色调不透明度（0-100，越大越接近实色）。"""
    if _ACRYLIC_TRANSPARENCY is not None:
        return 100 - _ACRYLIC_TRANSPARENCY
    _, opacity = acrylic_options()
    return max(0, min(100, opacity))


def acrylic_transparency() -> int:
    """亚克力透明度（0-100，越大桌面内容透出越明显）。

    未设置运行期覆盖时由 ``acrylic.opacity`` 反推，保证配置默认值与滑块
    初始值一致；运行期覆盖只影响本次会话，持久化由用户配置层负责。
    """
    if _ACRYLIC_TRANSPARENCY is not None:
        return _ACRYLIC_TRANSPARENCY
    _, opacity = acrylic_options()
    return 100 - max(0, min(100, opacity))


def set_acrylic_transparency(value: int | None) -> int:
    """设置运行期亚克力透明度；``None`` 表示恢复配置默认值。"""
    global _ACRYLIC_TRANSPARENCY
    if value is None:
        _ACRYLIC_TRANSPARENCY = None
    else:
        _ACRYLIC_TRANSPARENCY = max(0, min(100, int(value)))
    return acrylic_transparency()


def glass_strength() -> int:
    """玻璃层强度（0-100）：降低表面不透明度以透出更多亚克力材质。

    0 表示完全沿用配置值；数值越大，窗口/侧栏/面板/卡片越透明，模糊材质
    越明显。浮层菜单与工具提示不参与缩放，保证可读性。
    """
    return _GLASS_STRENGTH


def set_glass_strength(value: int | None) -> int:
    """设置运行期玻璃层强度；``None`` 表示恢复配置默认值（0）。"""
    global _GLASS_STRENGTH
    _GLASS_STRENGTH = _DEFAULT_GLASS_STRENGTH if value is None else max(0, min(100, int(value)))
    return _GLASS_STRENGTH


def glass_alpha(alpha: float, minimum: float = 0.0) -> float:
    """把配置里的玻璃层不透明度按当前强度缩放（0-1）。

    强度越高，表面层越透明，从而露出更多系统级模糊材质。``minimum``
    用于给**主窗口底色**兜底，避免 Alpha 归零后窗口变成鼠标穿透区域。
    """
    value = max(0.0, min(1.0, float(alpha))) * (1.0 - _GLASS_STRENGTH / 100.0)
    return max(max(0.0, min(1.0, float(minimum))), value)


def reset_appearance_overrides() -> None:
    """清除运行期外观覆盖（配置重载或测试使用）。"""
    global _ACRYLIC_TRANSPARENCY, _GLASS_STRENGTH
    _ACRYLIC_TRANSPARENCY = None
    _GLASS_STRENGTH = _DEFAULT_GLASS_STRENGTH


def glass_tint(value: str, alpha: float) -> QColor:
    """自绘控件用的玻璃色，返回带透明度的 :class:`QColor`。

    用于按钮/选中块这类在 ``paintEvent`` 里直接画背景的组件——样式表管不到
    它们，必须和 ``Styles`` 使用同一套半透明写法，否则会在玻璃窗口上留下
    一块块不透明的实色。

    返回 ``QColor`` 而不是 ``rgba(...)`` 字符串：``QColor`` 只认 ``#AARRGGBB``
    与颜色名，不解析 QSS 的 ``rgba()`` 写法，传字符串会得到无效色（黑色）。
    非玻璃模式返回原始颜色且不改变 Alpha，保持旧有不透明外观。
    """
    color = QColor(value)
    if acrylic_active() and color.isValid():
        color.setAlpha(max(0, min(255, round(255 * max(0.0, min(1.0, alpha))))))
    return color


def glass_surface(value: str | QColor, alpha: float, minimum: float = 0.0) -> QColor:
    """浮层/菜单类表面的玻璃色：同时响应「亚克力质感强度」。

    ``glass_tint`` 用于按钮、描边等固定层级，不随强度滑块变化；菜单、下拉弹层、
    对话框这类**覆盖在其它内容之上的表面**需要跟随强度，同时用 ``minimum``
    保留足够的不透明度，避免底层正文透出干扰阅读。
    """
    color = QColor(value)
    if acrylic_active() and color.isValid():
        color.setAlpha(max(0, min(255, round(255 * glass_alpha(alpha, minimum=minimum)))))
    return color


# ----------------------------------------------------------------------
# 对外接口
# ----------------------------------------------------------------------
def apply_acrylic(widget: QWidget | None) -> bool:
    """给 ``widget`` 所在的顶层窗口挂上亚克力材质，成功返回 True。

    调用时机：窗口已显示（``showEvent`` 之后）或主题切换后重新着色。
    该调用约 0.15ms 且幂等，可以安全地重复执行。
    """
    if not acrylic_supported() or widget is None:
        return False
    hwnd = _top_level_hwnd(widget)
    if not hwnd:
        return False

    try:
        # 调用本身约 0.15ms 且幂等（见模块说明），不做缓存：HWND 会被系统复用，
        # 按句柄缓存会把「新窗口」误判成「已应用」而漏挂材质。
        applied = _set_accent(hwnd, _ACCENT_ENABLE_ACRYLICBLURBEHIND, acrylic_tint(acrylic_opacity()))
        if applied:
            _set_corner_preference(hwnd)
            _set_dark_titlebar(hwnd, _theme_is_dark())
        return applied
    except Exception as exc:
        _log_once("apply", f"亚克力材质应用失败：{exc}")
        return False


def remove_acrylic(widget: QWidget | None) -> None:
    """移除亚克力材质（恢复系统默认背景）。"""
    if widget is None or _user32 is None:
        return
    hwnd = _top_level_hwnd(widget)
    if not hwnd:
        return
    try:
        _set_accent(hwnd, _ACCENT_DISABLED, 0)
    except Exception as exc:
        _log_once("remove", f"亚克力材质移除失败：{exc}")


def acrylic_tint(opacity: int | None = None) -> int:
    """当前主题的亚克力色调（0xAABBGGRR 格式，Alpha 为不透明度）。"""
    alpha = max(0, min(100, acrylic_opacity() if opacity is None else int(opacity)))
    color = QColor(get_design_tokens().colors.surface_app)
    color.setAlpha(round(255 * alpha / 100))
    return _to_abgr(color)


# ----------------------------------------------------------------------
# Win32 实现
# ----------------------------------------------------------------------
def _top_level_hwnd(widget: QWidget) -> int:
    """取顶层窗口的 HWND（子控件会先回溯到 ``window()``）。"""
    try:
        window = widget.window()
    except Exception:
        return 0
    if window is None:
        return 0
    try:
        handle = window.windowHandle()
        if handle is not None:
            return int(handle.winId())
    except Exception:
        pass
    try:
        return int(window.winId())
    except Exception:
        return 0


def _to_abgr(color: QColor) -> int:
    """Qt 的 ARGB 转 Win32 ACCENT_POLICY 需要的 ABGR。"""
    return (color.alpha() << 24) | (color.blue() << 16) | (color.green() << 8) | color.red()


def _set_accent(hwnd: int, state: int, gradient_color: int) -> bool:
    """调用 Undocumented ``SetWindowCompositionAttribute`` 设置窗口背景。"""
    setter = getattr(_user32, "SetWindowCompositionAttribute", None)
    if setter is None:  # 极旧的系统没有导出该函数
        return False
    policy = _AccentPolicy(int(state), 2 if state else 0, int(gradient_color), 0)
    data = _WindowCompositionAttributeData(
        _WCA_ACCENT_POLICY,
        ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p),
        ctypes.sizeof(policy),
    )
    result = setter(wintypes.HWND(hwnd), ctypes.byref(data))
    return bool(result)


def _set_corner_preference(hwnd: int) -> None:
    """Windows 11：让窗口外轮廓跟随系统圆角。

    亚克力会铺满整个 HWND（包括 Qt 留给窗口阴影的透明边距），不裁圆角就会
    在四角露出方形模糊块，圆角边框也就失去意义。
    """
    try:
        value = ctypes.c_int(_DWMWCP_ROUND)
        _dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            _DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception as exc:
        _log_once("corner", f"窗口圆角设置失败：{exc}")


def _set_dark_titlebar(hwnd: int, dark: bool) -> None:
    """把系统绘制的边框（阴影 / 焦点边）切到与主题一致的深浅。"""
    value = ctypes.c_int(1 if dark else 0)
    for attribute in (_DWMWA_USE_IMMERSIVE_DARK_MODE, _DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY):
        try:
            result = _dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                attribute,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if result == 0:
                return
        except Exception as exc:
            _log_once("titlebar", f"深色标题栏设置失败：{exc}")
            continue


def _theme_is_dark() -> bool:
    try:
        return QColor(ColorPalette.custom_bg_one).lightness() < 128
    except Exception:
        return True


__all__ = [
    "apply_acrylic",
    "remove_acrylic",
    "acrylic_active",
    "acrylic_opacity",
    "acrylic_options",
    "acrylic_supported",
    "acrylic_tint",
    "acrylic_transparency",
    "glass_alpha",
    "glass_strength",
    "glass_surface",
    "glass_tint",
    "MIN_WINDOW_GLASS_ALPHA",
    "reset_appearance_overrides",
    "set_acrylic_transparency",
    "set_glass_strength",
]
