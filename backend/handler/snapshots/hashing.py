"""A save unit's identity hash: its content hash without its clock members."""

import asyncio
import hashlib
import io
import zipfile
import zlib
from pathlib import Path

from handler.filesystem.assets_handler import (
    ArchiveTooLarge,
    open_zip_archive,
    zip_identity_hash,
)
from logger.logger import log


def _identity(content: bytes) -> str:
    try:
        with open_zip_archive(io.BytesIO(content)) as zf:
            if zf is not None:
                return zip_identity_hash(zf)
    except (
        zipfile.BadZipFile,
        ArchiveTooLarge,
        EOFError,
        OSError,
        RuntimeError,
        zlib.error,
    ) as exc:
        log.debug(f"Hashing the save unit as one file: {exc}")
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


async def identity_hash(content: bytes) -> str:
    """The unit's content hash without its clock members, by sigil's rule."""
    return await asyncio.to_thread(_identity, content)


async def identity_hash_of_file(path: Path) -> str:
    return await identity_hash(await asyncio.to_thread(path.read_bytes))
