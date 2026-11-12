from __future__ import annotations

import json
from pathlib import Path

from gallery_helpers import init_repo, write_plugin, write_source

from sllkgui import __version__, cli


def test_parser_gallery_and_run():
    parser = cli.build_parser()
    args = parser.parse_args(["gallery", "--surface", "a/b"])
    assert args.command == "gallery" and args.surface == "a/b"
    args = parser.parse_args(["run", "--plugin-dir", "x", "--plugin-dir", "y", "--safe-mode"])
    assert args.plugin_dir == ["x", "y"] and args.safe_mode is True


def test_plugin_lint_cli(tmp_path: Path, capsys):
    root = write_plugin(tmp_path / "hello")
    assert cli.main(["plugin", "lint", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["plugin_id"] == "com.example.hello"


def test_scaffold_then_lint(tmp_path: Path):
    target = tmp_path / "scaffold"
    assert cli.main(["scaffold", str(target), "--id", "com.example.scaffold", "--name", "Scaffold"]) == 0
    assert cli.main(["plugin", "lint", str(target)]) == 0


def test_plugin_list_json_empty(tmp_path: Path, capsys):
    assert cli.main(["plugin", "list", "--json", "--data-dir", str(tmp_path / "data")]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == []


def test_source_add_and_list(tmp_path: Path, capsys):
    source = write_source(tmp_path / "source")
    init_repo(source)
    data = tmp_path / "data"
    assert (
        cli.main(
            [
                "source",
                "add",
                source.as_uri(),
                "--id",
                "test",
                "--allow-local",
                "--yes",
                "--data-dir",
                str(data),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli.main(["source", "list", "--json", "--data-dir", str(data)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(item["id"] == "test" for item in payload)


def test_doctor_json(tmp_path: Path, capsys):
    assert cli.main(["doctor", "--json", "--data-dir", str(tmp_path / "data")]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == __version__
    assert "gallery_dir" in payload


def test_plugin_lifecycle_cli(tmp_path: Path, capsys):
    plugin = write_plugin(tmp_path / "plugin")
    commit = init_repo(plugin)
    from gallery_helpers import manifest_sha256, write_entry

    source = write_source(tmp_path / "source")
    write_entry(source, plugin, source_id="test", commit=commit, sha=manifest_sha256(plugin))
    init_repo(source)
    data = tmp_path / "data"

    assert cli.main(["source", "add", source.as_uri(), "--id", "test", "--allow-local", "--yes", "--data-dir", str(data)]) == 0
    assert cli.main(["source", "refresh", "test", "--allow-local", "--data-dir", str(data)]) == 0
    capsys.readouterr()
    assert cli.main(["source", "info", "test", "--json", "--allow-local", "--data-dir", str(data)]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "test"

    assert cli.main(
        ["plugin", "install", "com.example.hello", "--source", "test", "--yes", "--allow-local", "--data-dir", str(data)]
    ) == 0
    capsys.readouterr()
    assert cli.main(["plugin", "info", "com.example.hello", "--allow-local", "--data-dir", str(data)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["installed"]["version"] == "1.0.0"

    assert cli.main(["plugin", "verify", "--json", "--allow-local", "--data-dir", str(data)]) == 0
    assert cli.main(["plugin", "doctor", "--json", "--allow-local", "--data-dir", str(data)]) == 0
    assert cli.main(["plugin", "update", "--all", "--dry-run", "--json", "--allow-local", "--data-dir", str(data)]) == 0
    capsys.readouterr()
    assert cli.main(["plugin", "disable", "com.example.hello", "--allow-local", "--data-dir", str(data)]) == 0
    assert cli.main(["plugin", "enable", "com.example.hello", "--allow-local", "--data-dir", str(data)]) == 0
    capsys.readouterr()
    assert cli.main(
        ["plugin", "remove", "com.example.hello", "--yes", "--purge", "--allow-local", "--data-dir", str(data)]
    ) == 0
