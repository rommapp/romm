import re
import subprocess
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from __version__ import __version__

# Embedded straight into a YouTube URL, so anything outside this must be dropped.
YOUTUBE_ID_RE: Final = re.compile(r"[A-Za-z0-9_-]{11}")

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent.parent


def get_version() -> str:
    """Returns current version tag"""
    if __version__ != "<version>":
        return __version__

    return "development"


@lru_cache(maxsize=1)
def get_git_branch() -> str | None:
    """Current git branch for a dev build's display, or None outside a checkout (cached for the process's life)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
            shell=False,  # trunk-ignore(bandit/B603): git binary is fixed, args are hardcoded
        )
    except (OSError, subprocess.SubprocessError):
        return None

    branch = result.stdout.strip()
    return branch if branch and branch != "HEAD" else None


def is_valid_uuid(uuid_str: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(uuid_str, version=4)
        return True
    except ValueError:
        return False


def int_or_none(value: Any) -> int | None:
    """An int, or None when it is not one (``int()`` raises past 4300 digits)."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def valid_youtube_id(value: Any) -> str | None:
    """A video id, or None when it is not one."""
    text = str(value or "")
    return text if YOUTUBE_ID_RE.fullmatch(text) else None
