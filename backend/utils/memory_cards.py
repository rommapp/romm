"""Storage for whole memory card images. Shared by the streaming teardown that
evacuates a card off a container and by the upload route that takes one from
the user, so both agree on how a version is hashed, named and deduplicated."""

import hashlib
import io
import zipfile
from datetime import datetime, timezone

from handler.database import db_memory_card_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_memory_card_version
from logger.logger import log
from models.assets import MemoryCard
from models.user import User
from utils.filesystem import sanitize_filename

# The broker caps card transfers at the same figure. Raising one side alone
# just moves where the transfer fails.
MEMORY_CARD_MAX_BYTES = 256 * 1024 * 1024


def content_hash_of_bytes(content: bytes) -> str | None:
    """Compute the dedup hash of a card without writing it to disk. Mirrors
    fs_asset_handler.compute_content_hash exactly (zip-entry hash for zips,
    plain md5 otherwise, None on failure) so it matches stored content_hash
    values. Must stay in lockstep with that implementation.
    """
    try:
        buf = io.BytesIO(content)
        if zipfile.is_zipfile(buf):
            with zipfile.ZipFile(buf, "r") as zf:
                file_hashes = []
                for name in sorted(zf.namelist()):
                    if not name.endswith("/"):
                        entry = zf.read(name)
                        entry_hash = hashlib.md5(
                            entry, usedforsecurity=False
                        ).hexdigest()
                        file_hashes.append(f"{name}:{entry_hash}")
                combined = "\n".join(file_hashes)
                return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()
        return hashlib.md5(content, usedforsecurity=False).hexdigest()
    except Exception as exc:
        log.debug("could not hash memory card in memory, %s", exc)
        return None


async def store_memory_card_version(
    user: User,
    card: MemoryCard,
    emulator: str,
    content: bytes,
    deduplicate: bool = True,
) -> bool:
    """Store card content as a new MemoryCardVersion. Identical content is
    deduplicated by hash so repeated exits do not pile up copies. Either way the
    card's updated_at is bumped so it floats to the top of the next pick list.
    Returns True when a new version was actually stored.

    `deduplicate` is off for an upload, where the user is asking for exactly
    this content to become current: matching an older snapshot would leave that
    snapshot where it is and the newer one still at the head, so the card the
    next claim hydrates would not be the one that was just uploaded.
    """
    # Most exits leave the card unchanged, so check the hash in memory first
    # and skip the disk round-trip for a card that already has this content.
    content_hash = content_hash_of_bytes(content) if deduplicate else None
    if content_hash:
        existing = db_memory_card_handler.get_version_by_content_hash(
            card_id=card.id, content_hash=content_hash
        )
        if existing is not None:
            db_memory_card_handler.update_card(
                card.id, {"updated_at": datetime.now(timezone.utc)}
            )
            return False

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H-%M-%S")
    filename = sanitize_filename(f"{card.name} [{ts}].card.zip")
    cards_path = fs_asset_handler.build_memory_cards_file_path(
        user=user, emulator=emulator, card_id=card.id
    )
    await fs_asset_handler.write_file(file=content, path=cards_path, filename=filename)

    version = await scan_memory_card_version(
        file_name=filename, user=user, emulator=emulator, card_id=card.id
    )

    # Fallback dedup on the scanned hash, for when the in-memory hash could
    # not be computed. Keeps duplicates out even when the precheck misses.
    stored = True
    if deduplicate and version.content_hash:
        existing = db_memory_card_handler.get_version_by_content_hash(
            card_id=card.id, content_hash=version.content_hash
        )
        if existing is not None:
            try:
                await fs_asset_handler.remove_file(f"{cards_path}/{filename}")
            except FileNotFoundError:
                pass
            stored = False

    if stored:
        db_memory_card_handler.add_version(version)

    # Touch the card so "most recent" ordering reflects this session even when
    # the content was unchanged (updated_at has no onupdate on add_version).
    db_memory_card_handler.update_card(
        card.id, {"updated_at": datetime.now(timezone.utc)}
    )
    return stored
