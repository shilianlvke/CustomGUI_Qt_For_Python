"""回归测试：版本号同步与「脱离父级导致闪现」。

两个真实缺陷的守护：

1. **版本号不同步**——早期把版本号写进语言资源（``custom_ui.sys_version``），
   于是每次改版本都要同时改四个语言文件，实际没人记得，版权栏长期显示
   1.0.0。版本号必须来自 ``sllkgui.__version__`` 这一个来源。
2. **闪现小窗**——``QWidget.setParent(None)`` 会让可见控件变成顶层窗口，
   Qt 随后自动把它显示出来，用户看到一闪而过的小窗。凡是「把可见控件从
   布局里摘下来」的地方都必须先 ``hide()``。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget

import sllkgui
from sllkgui.appcore import AppLanguages, Language

_SRC = Path(__file__).resolve().parents[1] / "src" / "sllkgui"


# ----------------------------------------------------------------------
# 版本号：单一来源
# ----------------------------------------------------------------------
def test_credits_bar_shows_current_version(qapp):
    """版权栏显示的版本号必须等于当前包版本。"""
    from sllkgui.guicore.window.credits_bar.credits import CCredits

    Language.update(AppLanguages["zh_cn"].data)
    host = QWidget()
    credits = CCredits()
    credits.setParent(host)
    assert credits.version_label.text() == sllkgui.__version__
    assert credits.version_label.text() != "1.0.0"
    host.close()


def test_version_not_stored_in_language_resources():
    """版本号不该出现在语言资源里——它是构建事实，不是可翻译文案。"""
    offenders: list[str] = []
    for path in (_SRC / "_resources" / "sllkgui" / "languages").glob("*.yaml"):
        if "sys_version" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)
    assert not offenders, f"语言资源里仍有 sys_version: {offenders}"


def test_version_comes_from_single_source():
    """``_version.py`` 是版本号的唯一来源。"""
    text = (_SRC / "_version.py").read_text(encoding="utf-8")
    assert '__version__ = "' in text
    assert sllkgui.__version__ == sllkgui._version.__version__


def test_language_schema_does_not_require_sys_version():
    """schema 不该再要求语言包提供 sys_version。"""
    from sllkgui.appcore.sysx.config.schema import validate_language_data

    # 缺 sys_version 也应通过校验（版本号由 sllkgui.__version__ 提供）
    data = dict(AppLanguages["zh_cn"].data)
    custom_ui = dict(data.get("custom_ui") or {})
    custom_ui.pop("sys_version", None)
    data["custom_ui"] = custom_ui
    validate_language_data(data, "zh_cn")


def test_all_languages_share_the_same_keys():
    """四种语言包的顶层键必须一致。

    键漂移会让某个语言在运行时取不到值而回落到默认值——版本号当初就是
    这样在四个文件之间漂移成 1.0.0 的。这条测试防止同类问题复发。
    """
    import yaml

    lang_dir = _SRC / "_resources" / "sllkgui" / "languages"
    files = sorted(lang_dir.glob("*.yaml"))
    assert len(files) >= 4, f"语言文件不足: {[f.name for f in files]}"

    def keys_of(node: object) -> set[str]:
        if isinstance(node, dict):
            return set(node.keys())
        return set()

    reference_name = files[0].name
    reference = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    for path in files[1:]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert keys_of(data) == keys_of(reference), (
            f"{path.name} 的顶层键与 {reference_name} 不一致: {keys_of(data) ^ keys_of(reference)}"
        )
        for section in ("custom_ui", "PAGE", "UI"):
            assert keys_of(data.get(section)) == keys_of(reference.get(section)), (
                f"{path.name} 的 {section} 段键与 {reference_name} 不一致: "
                f"{keys_of(data.get(section)) ^ keys_of(reference.get(section))}"
            )


# ----------------------------------------------------------------------
# setParent(None) 的闪现防护
# ----------------------------------------------------------------------
def test_set_parent_none_detaches_widget_from_tree(qapp):
    """记录 Qt 的固有行为：控件 setParent(None) 后脱离对象树并成为顶层窗口。

    这条测试是下面所有防护的前提——如果哪天 Qt 改了行为，这些 ``hide()``
    可以一并去掉。
    """
    host = QWidget()
    host.resize(400, 300)
    box = QWidget(host)
    child = QWidget(box)
    from PySide6.QtWidgets import QVBoxLayout

    QVBoxLayout(box).addWidget(child)
    host.show()
    QApplication.processEvents()

    box.setParent(None)
    QApplication.processEvents()

    assert box.parentWidget() is None
    assert box.isWindow()
    host.close()


def test_side_nav_set_groups_does_not_flash_window(qapp):
    """切换栏目重建侧栏时，不得出现游离的顶层窗口。"""
    from sllkgui.guicore import CSideNav, CSideNavGroup, CSideNavItem

    nav = CSideNav(
        (
            CSideNavGroup(
                "插件",
                (
                    CSideNavItem("a", "A"),
                    CSideNavItem("b", "B"),
                    CSideNavItem("c", "C"),
                ),
            ),
        )
    )
    nav.resize(212, 200)
    nav.show()
    QApplication.processEvents()

    before = {id(w) for w in QApplication.topLevelWidgets()}
    nav.set_groups((CSideNavGroup("插件", (CSideNavItem("x", "X"),)),))
    QApplication.processEvents()

    extra = [w for w in QApplication.topLevelWidgets() if id(w) not in before and w.isVisible()]
    assert not extra, f"重建侧栏时出现了游离顶层窗口: {[w.geometry().getRect() for w in extra]}"
    nav.close()


def test_store_page_switch_mode_does_not_flash_window(qapp):
    """切到「已发现」栏目时不得闪现小窗（用户报告的实际路径）。"""
    from sllkgui.guis.pages.plugin_store.context import PageContext
    from sllkgui.guis.pages.plugin_store.page import StorePage

    host = QWidget()
    host.resize(1200, 700)
    ctx = PageContext(lambda: host)
    page = StorePage(ctx, host)
    host.show()
    QApplication.processEvents()

    before = {id(w) for w in QApplication.topLevelWidgets()}
    page.switch_mode("discover")
    QApplication.processEvents()

    extra = [w for w in QApplication.topLevelWidgets() if id(w) not in before and w.isVisible()]
    assert not extra, f"切换栏目时出现了游离顶层窗口: {[w.geometry().getRect() for w in extra]}"

    # 反复切换不应累积游离窗口
    for mode in ("installed", "sources", "discover", "installed"):
        page.switch_mode(mode)
        QApplication.processEvents()
    extra = [w for w in QApplication.topLevelWidgets() if id(w) not in before and w.isVisible()]
    assert not extra, f"反复切换后残留游离窗口: {[w.geometry().getRect() for w in extra]}"
    host.close()


@pytest.mark.parametrize(
    "relative",
    [
        "gallery/window.py",
        "guis/language_service.py",
        "guicore/custom_ui/layout/fluid.py",
        "guicore/custom_ui/media/galleria.py",
        "guicore/custom_ui/menu/stepper.py",
        "guicore/custom_ui/panels/form.py",
        "guicore/custom_ui/panels/settings.py",
        "guicore/custom_ui/panels/side_nav.py",
        "guicore/window/left_menu/menu.py",
        "guicore/window/settings_window/pages.py",
        "guicore/window/settings_window/window.py",
    ],
)
def test_every_set_parent_none_is_preceded_by_hide(relative: str):
    """所有「把可见控件摘出布局」的地方都必须先 hide()。

    这是静态扫描版的守护：新增代码若忘了加 hide()，这里立刻失败。
    """
    path = _SRC / relative
    lines = path.read_text(encoding="utf-8").splitlines()
    offenders: list[int] = []
    for index, line in enumerate(lines):
        code = line.split("#")[0]
        if "setParent(None)" not in code:
            continue
        window = [w.split("#")[0] for w in lines[max(0, index - 4) : index]]
        if not any("hide()" in w for w in window):
            offenders.append(index + 1)
    assert not offenders, f"{relative} 的第 {offenders} 行缺少 hide() 保护"
