from __version__ import __version__


def get_version() -> str:
    """Returns current version tag"""
    if __version__ != "<version>":
        return __version__

    return "development"
