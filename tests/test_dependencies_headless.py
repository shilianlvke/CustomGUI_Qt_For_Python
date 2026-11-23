"""依赖提示的无 GUI（headless）行为：不读 stdin，仅通过终端 I/O 协议输出。"""

from __future__ import annotations

import io

import pytest

from sllkgui.gallery import dependencies as deps


class _RecordingIO(deps.TerminalIO):
    """记录写入内容的假终端，读取端返回空串模拟 EOF。"""

    def __init__(self) -> None:
        self.buffer = io.StringIO()
        self.read_count = 0

    def write(self, text: str) -> None:
        self.buffer.write(text)

    def readline(self) -> str:
        self.read_count += 1
        return ""


def test_prompt_missing_headless_returns_skip_without_reading_stdin(monkeypatch):
    """sys.stdin.isatty() 为 False 时直接 skip，绝不触碰 stdin 读取。"""
    monkeypatch.setattr(deps.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(deps, "_gui_available", lambda: False)
    io_double = _RecordingIO()

    result = deps._ask_choice(
        title="缺少插件依赖",
        plugin_id="demo.plugin",
        packages=["foo>=1"],
        index_url="",
        command="python -m pip install foo>=1",
        parent=None,
        interactive=True,
        io=io_double,
    )

    assert result == "skip"
    assert io_double.read_count == 0
    assert io_double.buffer.getvalue() == ""


def test_show_manual_headless_writes_command_to_stdout(monkeypatch, capsys):
    """无 GUI 时命令文本写入 sys.stdout（经 TerminalIO 默认实现）。"""
    monkeypatch.setattr(deps, "_gui_available", lambda: False)
    command = "python -m pip install foo>=1"

    deps._show_manual(title="手动安装依赖", command=command, parent=None)

    captured = capsys.readouterr()
    assert "请手动执行：" in captured.out
    assert command in captured.out


def test_show_manual_default_io_is_flushed(monkeypatch):
    """默认 TerminalIO 写入后立即 flush，保证提示与输入顺序。"""
    monkeypatch.setattr(deps, "_gui_available", lambda: False)
    written: list[str] = []
    flushed: list[bool] = []

    class _Stdout:
        def write(self, text: str) -> int:
            written.append(text)
            return len(text)

        def flush(self) -> None:
            flushed.append(True)

    monkeypatch.setattr(deps.sys, "stdout", _Stdout())

    deps._show_manual(title="手动安装依赖", command="uv pip install foo", parent=None)

    assert written == ["请手动执行：\n\nuv pip install foo\n"]
    assert flushed == [True]


def test_terminal_io_readline_uses_stdin(monkeypatch):
    """默认 TerminalIO 从 sys.stdin.readline() 读取一行。"""
    monkeypatch.setattr(deps.sys, "stdin", io.StringIO("1\n"))
    assert deps.TerminalIO().readline() == "1\n"


def test_prompt_missing_tty_uses_injected_io(monkeypatch):
    """TTY 下统一走注入的 I/O：问句写入、答案从 readline 读取。"""
    monkeypatch.setattr(deps.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(deps, "_gui_available", lambda: False)

    class _AnswerIO(_RecordingIO):
        def readline(self) -> str:
            self.read_count += 1
            return "1\n"

    io_double = _AnswerIO()
    result = deps._ask_choice(
        title="缺少插件依赖",
        plugin_id="demo.plugin",
        packages=["foo>=1"],
        index_url="",
        command="python -m pip install foo>=1",
        parent=None,
        interactive=True,
        io=io_double,
    )

    assert result == "auto"
    assert io_double.read_count == 1
    output = io_double.buffer.getvalue()
    assert "[1] 自动安装" in output
    assert output.endswith("> ")


def test_no_print_call_in_dependencies_source():
    """回归：本模块不再使用终端内置交互函数，避免与插件 lint 规则双标。"""
    from pathlib import Path

    source = Path(deps.__file__).read_text(encoding="utf-8")
    forbidden = ("pr" + "int(", "in" + "put(")
    assert not any(token in source for token in forbidden)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
