"""A save unit's identity hash, computed by sigil when the binding is present.

Sigil hashes a unit unpacked on disk, so the bytes go to a temporary folder
first. Without the binding, `zip_identity_hash` applies the same rule.
"""

import asyncio
import hashlib
import io
import tempfile
import zipfile
from pathlib import Path

from adapters.services.sigil import SigilService, SigilUnitMember
from handler.filesystem.assets_handler import (
    UnsafeArchive,
    check_zip,
    is_clock_member,
    zip_identity_hash,
)
from logger.logger import log

_sigil = SigilService()


def _sigil_identity(content: bytes) -> str | None:
    if not SigilService.is_enabled():
        return None
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        archived = zipfile.is_zipfile(io.BytesIO(content))
        if archived:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = check_zip(zf)
                for name in names:
                    zf.extract(name, root)
        else:
            names = ["unit"]
            (root / "unit").write_bytes(content)
        members = [SigilUnitMember(name, is_clock_member(name)) for name in names]
        hashed = _sigil.unit_hashes(root, members, archived)
    return hashed[1] if hashed else None


def _identity(content: bytes) -> str:
    try:
        sigil_hash = _sigil_identity(content)
    except (zipfile.BadZipFile, UnsafeArchive, OSError) as exc:
        log.debug(f"Sigil could not unpack the save unit: {exc}")
        sigil_hash = None
    if sigil_hash is not None:
        return sigil_hash
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
