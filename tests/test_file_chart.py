"""FileUpload / Chart 组件契约：文件增删与超限拒绝、六种图表构造与数据注入。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from customgui.guicore.custom_ui.chart.chart import CHART_TYPES, CChart
from customgui.guicore.custom_ui.upload.file_upload import CFileUpload


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ----------------------------------------------------------------------
# FileUpload
# ----------------------------------------------------------------------
def test_file_upload_add_and_remove(tmp_path, qapp):
    upload = CFileUpload(mode="advanced")
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("hello", encoding="utf-8")
    second.write_text("world", encoding="utf-8")

    selected = []
    upload.filesSelected.connect(lambda paths: selected.append(list(paths)))

    upload.add_files([str(first), str(second)])
    assert upload.files() == [str(first), str(second)]
    assert len(upload._rows) == 2
    assert selected[-1] == [str(first), str(second)]

    row = upload._rows[next(iter(upload._rows))]
    row._remove_button.click()
    assert upload.files() == [str(second)]
    assert len(upload._rows) == 1

    upload.clear_files()
    assert upload.files() == []
    assert upload._rows == {}


def test_file_upload_rejects_oversized_file(tmp_path, qapp):
    upload = CFileUpload(mode="advanced", max_file_size=8)
    small = tmp_path / "small.txt"
    large = tmp_path / "large.txt"
    small.write_bytes(b"1234")
    large.write_bytes(b"123456789")

    rejected = []
    upload.fileRejected.connect(lambda path, reason: rejected.append((path, reason)))

    upload.add_files([str(small)])
    assert upload.files() == [str(small)]

    upload.add_files([str(large)])
    assert upload.files() == [str(small)]
    assert rejected
    assert rejected[-1][0] == str(large)
    assert "大小" in rejected[-1][1]


def test_file_upload_accept_filter_and_custom_upload(tmp_path, qapp):
    upload = CFileUpload(mode="basic", accept=".txt", custom_upload=False)
    text_file = tmp_path / "note.txt"
    binary_file = tmp_path / "note.bin"
    text_file.write_text("ok", encoding="utf-8")
    binary_file.write_bytes(b"ok")

    rejected = []
    upload.fileRejected.connect(lambda path, reason: rejected.append((path, reason)))
    upload.add_files([str(text_file), str(binary_file)])

    assert upload.files() == [str(text_file)]
    assert rejected and "类型" in rejected[-1][1]

    started = []
    upload.uploadStarted.connect(lambda: started.append(True))
    upload.start_upload()
    assert started == []
    assert not upload.is_uploading()
    assert "未执行上传" in upload.status_text()

    upload.set_progress(30)
    assert upload.progress() == 30
    assert upload.status_text() != ""


def test_file_upload_progress_demo(tmp_path, qapp):
    upload = CFileUpload(mode="advanced", custom_upload=True)
    sample = tmp_path / "sample.txt"
    sample.write_text("data", encoding="utf-8")
    upload.add_files([str(sample)])

    started = []
    finished = []
    progress = []
    upload.uploadStarted.connect(lambda: started.append(True))
    upload.uploadFinished.connect(lambda paths: finished.append(list(paths)))
    upload.uploadProgress.connect(progress.append)

    upload.set_progress(15)
    assert progress[-1] == 15

    upload.start_upload()
    assert started == [True]
    while upload.progress() < 100:
        upload._on_upload_tick()

    assert upload.progress() == 100
    assert finished[-1] == [str(sample)]
    assert not upload.is_uploading()


# ----------------------------------------------------------------------
# Chart
# ----------------------------------------------------------------------
@pytest.mark.parametrize("chart_type", CHART_TYPES)
def test_chart_constructs_and_accepts_data(chart_type, qapp):
    chart = CChart(chart_type=chart_type, title="Quarterly")
    data = [
        {"name": "2024", "values": [10, 20, 30], "labels": ["Q1", "Q2", "Q3"]},
        {"name": "2025", "values": [15, 25, 35], "labels": ["Q1", "Q2", "Q3"]},
    ]
    chart.set_data(data)

    assert chart.chart_type() == chart_type
    assert chart.title() == "Quarterly"
    assert chart.series_data() == data
    assert chart.chart() is not None
    assert len(chart.chart().series()) >= 1

    if chart_type in ("pie", "doughnut"):
        assert len(chart.chart().axes()) == 0
    else:
        assert len(chart.chart().axes()) == 2


def test_chart_type_switch_and_point_clicked(qapp):
    chart = CChart(chart_type="line", title="Revenue")
    clicks = []
    chart.pointClicked.connect(lambda name, value: clicks.append((name, value)))
    chart.set_data([{"name": "Sales", "values": [1, 2, 3], "labels": ["A", "B", "C"]}])

    line = chart.chart().series()[0]
    line.clicked.emit(QPointF(0.5, 2.0))
    assert clicks == [("Sales", 2.0)]

    chart.set_chart_type("pie")
    assert chart.chart_type() == "pie"
    assert len(chart.chart().series()) == 1

    chart.set_chart_type("polar")
    assert chart.chart_type() == "polar"
    assert len(chart.chart().axes()) == 2

    chart.set_title("Updated")
    assert chart.title() == "Updated"
    chart.refresh_theme()
    assert chart.chart() is not None
