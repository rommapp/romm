"""A save unit's identity hash: its content hash without its clock members."""

import asyncio
import hashlib
import io
import zipfile
from pathlib import Path

from handler.filesystem.assets_handler import UnsafeArchive, zip_identity_hash
from logger.logger import log


def _identity(content: bytes) -> str:
    try:
        if zipfile.is_zipfile(io.BytesIO(content)):
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                return zip_identity_hash(zf)
    except (zipfile.BadZipFile, UnsafeArchive, OSError) as exc:
        log.debug(f"Hashing the save unit as one file: {exc}")
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


async def identity_hash(content: bytes) -> str:
    """The unit's content hash without its clock members, by sigil's rule."""
    return await asyncio.to_thread(_identity, content)


async def identity_hash_of_file(path: Path) -> str:
    return await identity_hash(await asyncio.to_thread(path.read_bytes))
