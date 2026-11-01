"""``appcore.tool.storage`` 的原子持久化契约测试。"""

from __future__ import annotations

import pytest

from customgui.appcore.tool import StoreError, read_json, read_text, write_json, write_text


def test_write_then_read_json_roundtrip(tmp_path):
    target = tmp_path / "data.json"
    write_json(target, {"a": 1, "b": [1, 2, 3], "c": "中文"})

    assert read_json(target) == {"a": 1, "b": [1, 2, 3], "c": "中文"}
    # 文件以 UTF-8 落盘且末尾换行
    raw = target.read_text(encoding="utf-8")
    assert raw.endswith("\n")


def test_read_json_missing_returns_default(tmp_path):
    assert read_json(tmp_path / "nope.json") is None
    assert read_json(tmp_path / "nope.json", default={"x": 1}) == {"x": 1}


def test_write_json_creates_backup(tmp_path):
    target = tmp_path / "data.json"
    write_json(target, {"v": 1})
    write_json(target, {"v": 2})

    backup = target.with_suffix(target.suffix + ".bak")
    assert backup.is_file()
    assert read_json(backup) == {"v": 1}


def test_write_json_backup_can_be_disabled(tmp_path):
    target = tmp_path / "data.json"
    write_json(target, {"v": 1})
    write_json(target, {"v": 2}, backup=False)

    assert not target.with_suffix(target.suffix + ".bak").is_file()


def test_corrupt_json_recovers_from_backup(tmp_path):
    target = tmp_path / "data.json"
    write_json(target, {"v": "v1"})
    write_json(target, {"v": "v2"})  # 第二次写入前把 v1 备份成 .bak
    # 模拟主文件损坏
    target.write_text("{ broken json", encoding="utf-8")

    # 恢复到的是「上一次的旧值」v1
    assert read_json(target) == {"v": "v1"}


def test_corrupt_json_without_backup_raises(tmp_path):
    target = tmp_path / "data.json"
    target.write_text("{ broken json", encoding="utf-8")

    with pytest.raises(StoreError):
        read_json(target)


def test_write_json_creates_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "data.json"
    write_json(target, {"ok": True})

    assert target.is_file()


def test_text_roundtrip(tmp_path):
    target = tmp_path / "note.txt"
    write_text(target, "第一行\n第二行")
    assert read_text(target) == "第一行\n第二行"


def test_read_text_missing_returns_default(tmp_path):
    assert read_text(tmp_path / "nope.txt") == ""
    assert read_text(tmp_path / "nope.txt", default="fallback") == "fallback"


def test_utf8_bom_is_stripped_on_read(tmp_path):
    """``utf-8-sig`` 编码读取：带 BOM 的文件也能正确解析。"""
    target = tmp_path / "bom.json"
    target.write_text('\ufeff{"a": 1}', encoding="utf-8")

    assert read_json(target) == {"a": 1}


def test_write_is_atomic_no_temp_leftover(tmp_path):
    """写完后同目录不应残留临时文件。"""
    target = tmp_path / "data.json"
    write_json(target, {"x": 1})

    leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert not leftovers
