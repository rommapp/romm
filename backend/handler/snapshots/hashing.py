"""A save unit's identity hash, sigil's for a platform it has a rule for and
otherwise the content hash without the unit's clock members."""

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
    if binding is not None and sigil_platform is not None:
        try:
            identity: str = binding.unit_identity(
                sigil_platform, features or 0, content
            )
            return identity
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
    """The unit's identity as sigil gives it for the game's platform and cart
    `features`, or otherwise the content hash without the clock members."""
    return await asyncio.to_thread(_identity, content, platform_slug, features)


async def identity_hash_of_file(
    path: Path, *, platform_slug: str | None, features: int | None
) -> str:
    return await identity_hash(
        await asyncio.to_thread(path.read_bytes),
        platform_slug=platform_slug,
        features=features,
    )
