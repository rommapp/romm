"""Restore the stdlib zipfile module before writing fixture ZIPs.

Mirrors the pattern from `backend/utils/zip_cache.py`: a third-party
package (`zipfile-inflate64`) in the import chain replaces
`zipfile._get_compressor` with an incompatible signature on
CPython 3.13.5, breaking `ZipFile.write()` / `ZipFile.writestr()`.
Reloading restores the original implementation.

Tests that build fixture ZIPs should call `reload_zipfile()` immediately
before opening the archive.
"""

import importlib
import zipfile


def reload_zipfile() -> None:
    """Restore stdlib zipfile internals overridden by zipfile-inflate64."""
    importlib.reload(zipfile)
