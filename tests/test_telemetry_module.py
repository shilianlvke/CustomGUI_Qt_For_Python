import sllkgui.appcore.sysx.modules.telemetry_module as telemetry
from sllkgui.appcore.sysx.modules.telemetry_module import read_recent_events, record_event, track_timing


def test_record_event_writes_event_and_metric(tmp_path, monkeypatch):
    monkeypatch.setenv("SLLKGUI_DIAGNOSTICS_DIR", str(tmp_path))

    record_event("test.event", category="test", payload={"ok": True})

    event_file = tmp_path / "events.jsonl"
    metric_file = tmp_path / "metrics.json"

    assert event_file.exists()
    assert metric_file.exists()

    events = read_recent_events(limit=1)
    assert events[0]["name"] == "test.event"
    assert events[0]["category"] == "test"


def test_track_timing_records_duration(tmp_path, monkeypatch):
    monkeypatch.setenv("SLLKGUI_DIAGNOSTICS_DIR", str(tmp_path))

    with track_timing("perf.example", category="perf"):
        _ = sum(range(1000))

    events = read_recent_events(limit=5)
    perf_events = [event for event in events if event["name"] == "perf.example"]

    assert perf_events
    assert "duration_ms" in perf_events[-1]["payload"]
    assert perf_events[-1]["payload"]["duration_ms"] >= 0


def test_events_file_rotates(tmp_path, monkeypatch):
    """FIX-08: events.jsonl 达到阈值轮转为 .1，只保留 1 份备份且不影响读取。"""
    # FIX-08: 调低阈值触发轮转，验证备份数量与新事件可读。
    monkeypatch.setenv("SLLKGUI_DIAGNOSTICS_DIR", str(tmp_path))
    monkeypatch.setattr(telemetry, "MAX_EVENT_FILE_BYTES", 200)

    for index in range(6):
        record_event(f"test.rotate.{index}", payload={"n": index})

    assert (tmp_path / "events.jsonl").is_file(), "active event file must exist"
    assert (tmp_path / "events.jsonl.1").is_file(), "one backup must be kept"
    assert not (tmp_path / "events.jsonl.2").exists(), "only one backup is allowed"
    assert "test.rotate.5" in [e["name"] for e in read_recent_events(limit=20)], (
        "recent read must survive rotation"
    )


def test_record_event_swallows_serialization_errors(tmp_path, monkeypatch):
    """FIX-08: json.dumps 遇到不可序列化 payload 抛 TypeError 也不影响主流程。"""
    # FIX-08: 真实触发 TypeError，验证尽力而为语义与后续写入不受影响。
    monkeypatch.setenv("SLLKGUI_DIAGNOSTICS_DIR", str(tmp_path))

    record_event("test.unserializable", payload={"bad": object()})  # 不向上抛
    record_event("test.after_failure")

    names = [e["name"] for e in read_recent_events(limit=5)]
    assert "test.after_failure" in names, "later events must still be writable"
