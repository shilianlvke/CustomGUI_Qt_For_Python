from AppCore.SYS.module.telemetry_module import read_recent_events, record_event, track_timing


def test_record_event_writes_event_and_metric(tmp_path, monkeypatch):
    """测试用例：test_record_event_writes_event_and_metric。

    职责:
    - 验证目标行为符合预期。
    """
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))

    record_event("test.event", category="test", payload={"ok": True})

    event_file = tmp_path / "events.jsonl"
    metric_file = tmp_path / "metrics.json"

    assert event_file.exists()
    assert metric_file.exists()

    events = read_recent_events(limit=1)
    assert events[0]["name"] == "test.event"
    assert events[0]["category"] == "test"


def test_track_timing_records_duration(tmp_path, monkeypatch):
    "测试用例：test_track_timing_records_duration。"
    monkeypatch.setenv("CUSTOMGUI_DIAGNOSTICS_DIR", str(tmp_path))

    with track_timing("perf.example", category="perf"):
        _ = sum(range(1000))

    events = read_recent_events(limit=5)
    perf_events = [event for event in events if event["name"] == "perf.example"]

    assert perf_events
    assert "duration_ms" in perf_events[-1]["payload"]
    assert perf_events[-1]["payload"]["duration_ms"] >= 0

