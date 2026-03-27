"""模块说明。"""

from threading import Thread

import pytest

from AppCore import AppSettings, get_app_context, initialize_app_context


def test_lazy_context_view_access() -> None:
    """测试用例：test_lazy_context_view_access。

    职责:
    - 验证目标行为符合预期。
    """
    initialize_app_context(force_reload=True)

    if not (hasattr(AppSettings, "theme_name")):
        pytest.fail("Assertion failed")
    if not (isinstance(AppSettings.theme_name, str)):
        pytest.fail("Assertion failed")


def test_context_reload_returns_loaded_context() -> None:
    """测试用例：test_context_reload_returns_loaded_context。"""
    ctx = get_app_context(force_reload=True)

    if not (ctx.settings is not None):
        pytest.fail("Assertion failed")
    if not (ctx.themes is not None):
        pytest.fail("Assertion failed")
    if not (ctx.languages is not None):
        pytest.fail("Assertion failed")
    if not (ctx.others is not None):
        pytest.fail("Assertion failed")
    if hasattr(ctx, "menu"):
        pytest.fail("Assertion failed")


def test_get_app_context_thread_safe_initialization() -> None:
    """测试用例：test_get_app_context_thread_safe_initialization。"""
    initialize_app_context(force_reload=True)
    contexts = []

    def worker() -> None:
        """函数：worker。"""
        contexts.append(get_app_context())

    threads = [Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if not (contexts):
        pytest.fail("Assertion failed")
    first = contexts[0]
    if not (all(ctx is first for ctx in contexts)):
        pytest.fail("Assertion failed")
