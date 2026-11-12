from __future__ import annotations

from pathlib import Path

import pytest
from gallery_helpers import init_repo, write_plugin

from sllkgui.gallery import git_backend
from sllkgui.gallery.errors import GalleryError


def test_validate_url_rules():
    assert git_backend.validate_url("https://gitee.com/a/b.git") == "https://gitee.com/a/b.git"
    assert git_backend.validate_url("git@example.com:a/b.git")
    with pytest.raises(GalleryError):
        git_backend.validate_url("http://example.com/a.git")
    with pytest.raises(GalleryError):
        git_backend.validate_url("ext::sh -c echo")
    with pytest.raises(GalleryError):
        git_backend.validate_url("file:///tmp/repo")
    assert git_backend.validate_url("file:///tmp/repo", allow_local=True)


def test_redact_url_removes_credentials():
    assert git_backend.redact_url("https://user:token@example.com/a.git") == "https://example.com/a.git"


def test_local_clone_and_rev_parse(tmp_path: Path):
    repo = write_plugin(tmp_path / "plugin")
    commit = init_repo(repo)
    dest = tmp_path / "checkout"
    head = git_backend.clone(repo.as_uri(), dest, ref="v1.0.0", allow_local=True)
    assert head == commit
    assert (dest / "sllkgui-plugin.yml").is_file()
    assert git_backend.rev_parse(dest) == commit
    assert git_backend.is_clean(dest)
