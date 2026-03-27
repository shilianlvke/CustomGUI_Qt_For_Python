"""模块说明。"""

from pathlib import Path

import pytest

from AppCore.SYS.module.telemetry_module import read_recent_events, record_event, track_timing


def test_record_event_writes_event_and_metric(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试用例：test_record_event_writes_event_and_metric。

    职责:
    - 验证目标行为符合预期。
    """
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))

    record_event("test.event", category="test", payload={"ok": True})

    event_file = tmp_path / "events.jsonl"
    metric_file = tmp_path / "metrics.json"

    if not (event_file.exists()):
        pytest.fail("Assertion failed")
    if not (metric_file.exists()):
        pytest.fail("Assertion failed")

    events = read_recent_events(limit=1)
    if events[0]["name"] != "test.event":
        pytest.fail("Assertion failed")
    if events[0]["category"] != "test":
        pytest.fail("Assertion failed")


def test_track_timing_records_duration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试用例：test_track_timing_records_duration。"""
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))

    with track_timing("perf.example", category="perf"):
        _ = sum(range(1000))

    events = read_recent_events(limit=5)
    perf_events = [event for event in events if event["name"] == "perf.example"]

    if not (perf_events):
        pytest.fail("Assertion failed")
    if "duration_ms" not in perf_events[-1]["payload"]:
        pytest.fail("Assertion failed")
    if not (perf_events[-1]["payload"]["duration_ms"] >= 0):
        pytest.fail("Assertion failed")
