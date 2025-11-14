import uuid

from __version__ import __version__


def get_version() -> str:
    """Returns current version tag"""
    if __version__ != "<version>":
        return __version__

    return "development"


def is_valid_uuid(uuid_str: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(uuid_str, version=4)
        return True
    except ValueError:
        return False
