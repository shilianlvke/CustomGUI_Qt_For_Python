def test_manifest_exists():
    from pathlib import Path

    assert (Path(__file__).parents[1] / 'sllkgui-plugin.yml').is_file()
