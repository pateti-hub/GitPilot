from pathlib import Path

import pytest

from gitpilot.repo_loader import read_file, repo_id_from_url


def test_parse_plain_https_url():
    assert repo_id_from_url("https://github.com/psf/requests") == "psf/requests"


def test_parse_url_with_git_suffix():
    assert repo_id_from_url("https://github.com/psf/requests.git") == "psf/requests"


def test_parse_url_with_trailing_slash():
    assert repo_id_from_url("https://github.com/psf/requests/") == "psf/requests"


def test_reject_non_github_url():
    with pytest.raises(ValueError):
        repo_id_from_url("https://example.com/not/a-repo")


def test_read_file_blocks_path_traversal(tmp_path: Path):
    (tmp_path / "ok.py").write_text("x = 1")
    assert read_file(tmp_path, "ok.py") == "x = 1"
    with pytest.raises(ValueError):
        read_file(tmp_path, "../../etc/passwd")
