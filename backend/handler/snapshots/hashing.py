"""A save unit's identity hash. Sigil computes it on platforms it has a rule
for; elsewhere it is the content hash without the unit's clock members."""

import asyncio
import hashlib
import io
import zipfile
import zlib
from pathlib import Path

from adapters.services.sigil import SIGIL_RESTORE_PLATFORM_SLUGS, sigil_binding
from handler.filesystem.assets_handler import (
    ArchiveTooLarge,
    open_zip_archive,
    zip_identity_hash,
)
from logger.logger import log


def _identity(content: bytes, platform_slug: str | None, features: int | None) -> str:
    binding = sigil_binding()
    sigil_platform = SIGIL_RESTORE_PLATFORM_SLUGS.get(platform_slug or "")
    # A binding older than `unit_identity` falls back to the content hash.
    unit_identity = getattr(binding, "unit_identity", None)
    if unit_identity is not None and sigil_platform is not None:
        try:
            return str(unit_identity(sigil_platform, features or 0, content))
        except binding.SigilError:
            pass
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


async def identity_hash(
    content: bytes, *, platform_slug: str | None, features: int | None
) -> str:
    """The unit's identity hash from sigil for the game's platform and cart
    `features`, or the content hash without clock members if sigil has no rule."""
    return await asyncio.to_thread(_identity, content, platform_slug, features)


async def identity_hash_of_file(
    path: Path, *, platform_slug: str | None, features: int | None
) -> str:
    return await identity_hash(
        await asyncio.to_thread(path.read_bytes),
        platform_slug=platform_slug,
        features=features,
    )
