import subprocess
from unittest.mock import patch

import pytest

from utils import _REPO_ROOT, get_git_branch


@pytest.fixture(autouse=True)
def _clear_branch_cache():
    get_git_branch.cache_clear()
    yield
    get_git_branch.cache_clear()


def test_get_git_branch_returns_current_branch():
    with patch("utils.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="feature/foo\n"
        )
        assert get_git_branch() == "feature/foo"


def test_get_git_branch_trusts_the_repo_root_as_a_safe_directory():
    """A host-owned .git bind-mounted into a root-run container is otherwise
    refused by git 2.35.2+ as having "dubious ownership"."""
    with patch("utils.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="main\n"
        )
        get_git_branch()
        args = mock_run.call_args.args[0]
        assert f"safe.directory={_REPO_ROOT}" in args


def test_get_git_branch_returns_none_when_git_unavailable():
    with patch("utils.subprocess.run", side_effect=FileNotFoundError):
        assert get_git_branch() is None


def test_get_git_branch_returns_none_on_detached_head():
    with patch("utils.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="HEAD\n"
        )
        assert get_git_branch() is None


def test_get_git_branch_returns_none_when_not_a_git_repo():
    with patch("utils.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, ["git"])
        assert get_git_branch() is None
