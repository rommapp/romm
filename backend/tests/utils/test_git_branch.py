import subprocess
from unittest.mock import patch

from utils import get_git_branch


def test_get_git_branch_returns_current_branch():
    get_git_branch.cache_clear()
    try:
        with patch("utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="feature/foo\n"
            )
            assert get_git_branch() == "feature/foo"
    finally:
        get_git_branch.cache_clear()


def test_get_git_branch_returns_none_when_git_unavailable():
    get_git_branch.cache_clear()
    try:
        with patch("utils.subprocess.run", side_effect=FileNotFoundError):
            assert get_git_branch() is None
    finally:
        get_git_branch.cache_clear()


def test_get_git_branch_returns_none_on_detached_head():
    get_git_branch.cache_clear()
    try:
        with patch("utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="HEAD\n"
            )
            assert get_git_branch() is None
    finally:
        get_git_branch.cache_clear()


def test_get_git_branch_returns_none_when_not_a_git_repo():
    get_git_branch.cache_clear()
    try:
        with patch("utils.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(128, ["git"])
            assert get_git_branch() is None
    finally:
        get_git_branch.cache_clear()
