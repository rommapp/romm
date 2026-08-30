"""Storage for whole memory card images. Shared by the streaming teardown that
evacuates a card off a container and by the upload route that takes one from
the user, so both agree on how a version is hashed, named and deduplicated."""

import hashlib
import io
import ntpath
import re
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

from handler.database import db_memory_card_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import hash_zip_contents
from handler.scan_handler import scan_memory_card_version
from logger.logger import log
from models.assets import MemoryCard, MemoryCardVersion
from models.user import User
from utils.filesystem import sanitize_filename

# The broker caps card transfers at the same figure. Raising one side alone
# just moves where the transfer fails.
MEMORY_CARD_MAX_BYTES = 256 * 1024 * 1024


def content_hash_of_bytes(content: bytes) -> str | None:
    """Compute the dedup hash of a card without writing it to disk. Mirrors
    fs_asset_handler.compute_content_hash exactly (zip-entry hash for zips,
    plain md5 otherwise, None on failure) so it matches stored content_hash
    values.
    """
    try:
        buf = io.BytesIO(content)
        if zipfile.is_zipfile(buf):
            with zipfile.ZipFile(buf, "r") as zf:
                return hash_zip_contents(zf)
        return hashlib.md5(content, usedforsecurity=False).hexdigest()
    except Exception as exc:
        log.debug("could not hash memory card in memory, %s", exc)
        return None


class UnsafeCardArchive(ValueError):
    """A card archive the broker must not be asked to unpack."""


# The unix mode a zip entry carries in the top half of its external attributes,
# and the bits that mark it a symlink.
_ZIP_MODE_SHIFT = 16
_S_IFMT = 0o170000
_S_IFLNK = 0o120000

# What a card archive may add up to once unpacked, over the whole archive rather
# than per entry: a card set is several files and the container's disk pays for
# the total. The archive's own size says nothing about it, since a few hundred
# compressed megabytes of zeros expand to hundreds of gigabytes. Held to the
# transfer cap, which a real card of a few megabytes comes nowhere near.
_CARD_MAX_UNPACKED_BYTES = MEMORY_CARD_MAX_BYTES

# Enough that a card-sized entry is a handful of reads, small enough that the
# check never holds much more than this per entry.
_UNPACK_CHUNK_BYTES = 1024 * 1024


def _assert_entry_fits(zf: zipfile.ZipFile, entry: zipfile.ZipInfo, budget: int) -> int:
    """Decompress one entry against what is left of the archive's budget, and
    return what it consumed.

    Decompressed rather than trusting `file_size`: that header is whatever the
    uploader put there, and an unpacker writes what actually comes out.
    """
    read = 0
    with zf.open(entry, "r") as stream:
        while True:
            chunk = stream.read(_UNPACK_CHUNK_BYTES)
            if not chunk:
                return read
            read += len(chunk)
            if read > budget:
                raise UnsafeCardArchive(
                    f"unpacks to over {_CARD_MAX_UNPACKED_BYTES} bytes"
                )


def assert_card_archive_safe(content: bytes) -> None:
    """Refuse an archive the broker must not be asked to unpack: one whose
    entries would escape the directory they land in, or fill the disk they land
    on. RomM stores the zip whole, and this is the last point that can look at
    what is inside before a container unpacks it.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            budget = _CARD_MAX_UNPACKED_BYTES
            for entry in zf.infolist():
                name = entry.filename
                # Zip names are meant to be slash-separated, so a hand-written
                # entry can hide `..\..\evil` in what PurePosixPath reads as one
                # opaque part. Both separators are split before the parts are
                # judged.
                parts = re.split(r"[\\/]", name)
                if (
                    PurePosixPath(name).is_absolute()
                    or ntpath.isabs(name)
                    or ".." in parts
                ):
                    raise UnsafeCardArchive(f"unsafe path: {name}")
                # A symlink's own name is harmless; its target is not, and an
                # unpacker that follows it writes wherever the target points on
                # the next entry.
                mode = entry.external_attr >> _ZIP_MODE_SHIFT
                if mode & _S_IFMT == _S_IFLNK:
                    raise UnsafeCardArchive(f"symlink entry: {name}")
                if not name.endswith("/"):
                    budget -= _assert_entry_fits(zf, entry, budget)
    # Encrypted entries and unsupported compression raise on the read rather
    # than on the open, and an archive this cannot look inside is one the broker
    # must not be handed either.
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError):
        raise UnsafeCardArchive("not a readable zip archive") from None


# Names only ever collide when two snapshots land in the same millisecond, so
# the walk exists to break that tie, not to search.
_FILENAME_COLLISION_ATTEMPTS = 20


async def _free_version_filename(cards_path: str, card_name: str, ts: str) -> str:
    """A version filename no archive already occupies.

    `write_file` overwrites silently, so a name reused by a second snapshot
    would replace the first one's bytes on disk while its row lived on
    describing content that is no longer there.
    """
    for attempt in range(1, _FILENAME_COLLISION_ATTEMPTS + 1):
        suffix = "" if attempt == 1 else f" ({attempt})"
        filename = sanitize_filename(f"{card_name} [{ts}{suffix}].card.zip")
        if not await fs_asset_handler.file_exists(f"{cards_path}/{filename}"):
            return filename
    raise RuntimeError(f"could not find a free filename for card {card_name}")


async def _discard_version_file(cards_path: str, filename: str) -> None:
    """Drop an archive no version row will reference. Best effort: it is
    already unreachable, and raising here would mask the reason we are here."""
    try:
        await fs_asset_handler.remove_file(f"{cards_path}/{filename}")
    except OSError as exc:
        log.warning("could not remove unreferenced card archive %s, %s", filename, exc)


async def store_memory_card_version(
    user: User,
    card: MemoryCard,
    content: bytes,
    deduplicate: bool = True,
) -> MemoryCardVersion | None:
    """Store card content as a new MemoryCardVersion. Identical content is
    deduplicated by hash so repeated exits do not pile up copies. Either way the
    card's updated_at is bumped so it floats to the top of the next pick list.
    Returns the version that was written, or None when the content was already
    in the history.

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
            return None

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H-%M-%S-%f")[:-3]
    cards_path = fs_asset_handler.build_memory_cards_file_path(
        user=user, emulator=card.emulator, card_id=card.id
    )
    filename = await _free_version_filename(cards_path, card.name, ts)
    await fs_asset_handler.write_file(file=content, path=cards_path, filename=filename)

    try:
        version = await scan_memory_card_version(
            file_name=filename, user=user, emulator=card.emulator, card_id=card.id
        )

        # Fallback dedup on the scanned hash, for when the in-memory hash could
        # not be computed. Keeps duplicates out even when the precheck misses.
        stored: MemoryCardVersion | None = None
        if (
            deduplicate
            and version.content_hash
            and db_memory_card_handler.get_version_by_content_hash(
                card_id=card.id, content_hash=version.content_hash
            )
            is not None
        ):
            await _discard_version_file(cards_path, filename)
        else:
            stored = db_memory_card_handler.add_version(version)
    except Exception:
        # No row points at the archive yet, so leaving it behind strands bytes
        # that nothing can reach and no delete would ever clean up.
        await _discard_version_file(cards_path, filename)
        raise

    # Touch the card so "most recent" ordering reflects this session even when
    # the content was unchanged (updated_at has no onupdate on add_version).
    db_memory_card_handler.update_card(
        card.id, {"updated_at": datetime.now(timezone.utc)}
    )
    return stored
