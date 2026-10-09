import asyncio
import hashlib
import io
import os
import re
import stat
import threading
import zipfile
from dataclasses import dataclass
from mimetypes import guess_type
from pathlib import Path
from typing import IO, TYPE_CHECKING, BinaryIO

import magic
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from config import ASSETS_BASE_PATH
from logger.logger import log
from models.assets import SaveShape
from models.user import User
from utils.media_types import IMAGE_EXT_BY_MIME_TYPE

from .base_handler import FSHandler

if TYPE_CHECKING:
    from models.assets import Save

# libmagic loads its database on construction (~few MB read from disk), so we
# share a single Magic instance across requests. The underlying magic_t handle
# is not thread-safe, so guard from_buffer with a lock. Endpoints that call
# this validator may execute in worker threads under sync routes.
_MIME_DETECTOR = magic.Magic(mime=True)
_MIME_DETECTOR_LOCK = threading.Lock()

# A zip entry's declared size is attacker-controlled, so entries are hashed in
# chunks against this ceiling rather than read whole. Sized well above any real
# memory card or save archive.
MAX_DECOMPRESSED_ENTRY_BYTES = 512 * 1024 * 1024
# What an uploaded save archive may expand to in all, and hold, by its own
# declaration; a lying entry still hits the per-entry ceiling while hashing.
MAX_ARCHIVE_EXPANDED_BYTES = 4 * 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 65536

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class UnsafeArchive(ValueError):
    """An uploaded archive a client restoring it could not unpack safely."""


def is_symlink_entry(info: zipfile.ZipInfo) -> bool:
    """Whether a zip entry is a Unix symlink, whose target an unpacker that
    follows it writes through on the next entry."""
    return stat.S_ISLNK(info.external_attr >> 16)


def leaves_save_folder(path: str) -> bool:
    """Whether a relative path a client named would land outside the save folder."""
    return (
        "\x00" in path
        or "\\" in path
        or path.startswith("/")
        or bool(_DRIVE_PREFIX.match(path))
        or ".." in path.split("/")
    )


def check_zip(zf: zipfile.ZipFile) -> list[str]:
    """The file entries of an uploaded archive, once every entry stays inside
    the save folder and the whole expands within the limits.

    Raises:
        UnsafeArchive: an entry escapes, or the archive is too large.
    """
    infos = zf.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise UnsafeArchive(
            f"the archive holds more than {MAX_ARCHIVE_ENTRIES} entries"
        )
    expanded = 0
    for info in infos:
        name = info.filename
        if leaves_save_folder(name) or is_symlink_entry(info):
            raise UnsafeArchive(f"entry {name!r} leaves the save folder")
        expanded += info.file_size
        if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
            raise UnsafeArchive("the archive expands past the size limit")
    return [info.filename for info in infos if not info.is_dir()]


RAW_UNIT_NAME = "unit"


@dataclass(frozen=True)
class UnpackedUnit:
    names: list[str]
    archived: bool


def unpack_save_unit(
    unit: bytes,
    root: Path,
    *,
    max_total_bytes: int | None = None,
    max_entry_bytes: int | None = None,
) -> UnpackedUnit:
    """Write a save unit's files under `root`: a zip's safe entries by name, else the raw unit.

    Raises:
        UnsafeArchive: `check_zip` refuses the zip, or its entries declare more
            than `max_total_bytes` in all.
    """
    if not zipfile.is_zipfile(io.BytesIO(unit)):
        (root / RAW_UNIT_NAME).write_bytes(unit)
        return UnpackedUnit([RAW_UNIT_NAME], archived=False)
    with zipfile.ZipFile(io.BytesIO(unit)) as zf:
        names = [
            name
            for name in check_zip(zf)
            if max_entry_bytes is None or zf.getinfo(name).file_size <= max_entry_bytes
        ]
        expanded = sum(zf.getinfo(name).file_size for name in names)
        if max_total_bytes is not None and expanded > max_total_bytes:
            raise UnsafeArchive(f"the unit expands past {max_total_bytes} bytes")
        for name in names:
            zf.extract(name, root)
    return UnpackedUnit(names, archived=True)


def check_upload(stream: BinaryIO) -> list[str] | None:
    """`check_zip` for an upload that is an archive, or None for a raw file.
    Leaves the stream where it was."""
    position = stream.tell()
    try:
        if not zipfile.is_zipfile(stream):
            return None
        stream.seek(position)
        try:
            with zipfile.ZipFile(stream) as zf:
                return check_zip(zf)
        except zipfile.BadZipFile as exc:
            raise UnsafeArchive("the archive can't be read") from exc
    finally:
        stream.seek(position)


def save_shape_of(path: Path) -> SaveShape:
    """A stored save's shape: an archive holds several members, a raw file one."""
    return SaveShape.MULTI if zipfile.is_zipfile(path) else SaveShape.SINGLE


def check_upload_archive(upload: UploadFile | None, label: str) -> None:
    """422 for an uploaded archive `check_upload` refuses."""
    if upload is None:
        return
    try:
        check_upload(upload.file)
    except UnsafeArchive as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{label}: {exc}",
        ) from exc


def hash_zip_entry(zf: zipfile.ZipFile, name: str) -> str:
    """md5 of one zip entry, streamed so a compression bomb cannot exhaust memory."""
    hash_obj = hashlib.md5(usedforsecurity=False)
    read = 0
    with zf.open(name, "r") as entry:
        while chunk := entry.read(8192):
            read += len(chunk)
            if read > MAX_DECOMPRESSED_ENTRY_BYTES:
                raise ValueError(
                    f"zip entry {name} exceeds the decompressed size limit"
                )
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def _combined_hash(zf: zipfile.ZipFile, names: list[str]) -> str:
    combined = "\n".join(f"{name}:{hash_zip_entry(zf, name)}" for name in names)
    return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()


def _file_entries(zf: zipfile.ZipFile) -> list[str]:
    return [name for name in sorted(zf.namelist()) if not name.endswith("/")]


def hash_zip_contents(zf: zipfile.ZipFile) -> str:
    """md5 of a zip archive's contents, keyed by sorted entry name and each
    entry's own hash. Shared by disk-path and in-memory hashing so both agree
    on a card or save archive's dedup hash."""
    return _combined_hash(zf, _file_entries(zf))


def is_clock_member(name: str) -> bool:
    """Whether sigil gives an entry the RTC role: `{stem}.rtc` or `clock.rtc`."""
    return name.endswith(".rtc")


def zip_identity_hash(zf: zipfile.ZipFile) -> str:
    """Sigil's identity hash of a unit archive: its content hash without the
    clock members, or the one remaining member's own hash."""
    names = [name for name in _file_entries(zf) if not is_clock_member(name)]
    if len(names) == 1:
        return hash_zip_entry(zf, names[0])
    return _combined_hash(zf, names)


def hash_save_content(content: IO[bytes]) -> str | None:
    """Hash seekable save bytes like ``Save.content_hash``, leaving them at the start."""
    try:
        content.seek(0)
        if zipfile.is_zipfile(content):
            with zipfile.ZipFile(content, "r") as zf:
                return hash_zip_contents(zf)
        content.seek(0)
        hash_obj = hashlib.md5(usedforsecurity=False)
        while chunk := content.read(65536):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception as e:
        log.debug(f"Could not hash save content: {e}")
        return None
    finally:
        content.seek(0)


def hash_save_file(path: str | os.PathLike[str]) -> str | None:
    """Hash a save on disk like ``Save.content_hash``, or None if it cannot be read."""
    try:
        with open(path, "rb") as f:
            return hash_save_content(f)
    except OSError as e:
        log.debug(f"Could not hash save {path}: {e}")
        return None


def validate_image_upload(upload: UploadFile, *, label: str = "Image") -> str:
    """Validate that an uploaded file is one of the safe image types.

    Sniffs the leading bytes with libmagic and returns the trusted extension
    matching the detected MIME type. Raises HTTPException(400) if the file
    is not a recognized image, or if MIME sniffing fails.
    Leaves the file cursor at 0.
    """
    upload.file.seek(0)
    header = upload.file.read(4096)
    upload.file.seek(0)

    try:
        with _MIME_DETECTOR_LOCK:
            detected_mime = _MIME_DETECTOR.from_buffer(header)
    except magic.MagicException as exc:
        log.error(f"libmagic failed to sniff uploaded {label.lower()}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not determine {label.lower()} file type",
        ) from exc

    safe_extension = IMAGE_EXT_BY_MIME_TYPE.get(detected_mime)
    if not safe_extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{label} must be a PNG, JPEG, WebP, or GIF image "
                f"(detected {detected_mime or 'unknown type'})"
            ),
        )

    return safe_extension


def build_asset_file_response(
    resolved_path: Path, filename: str | None = None
) -> FileResponse:
    """Serve an asset file. Trusted image types render inline; everything else
    is an opaque attachment, so a user-controlled file (e.g. HTML uploaded as an
    avatar) can't execute as stored XSS."""
    download_name = filename or resolved_path.name
    guessed_type, _ = guess_type(download_name)
    if guessed_type in IMAGE_EXT_BY_MIME_TYPE:
        return FileResponse(
            path=str(resolved_path),
            filename=download_name,
            media_type=guessed_type,
            content_disposition_type="inline",
        )

    return FileResponse(
        path=str(resolved_path),
        filename=download_name,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
    )


class FSAssetsHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=ASSETS_BASE_PATH)

    def user_folder_path(self, user: User) -> str:
        return os.path.join("users", user.fs_safe_folder_name)

    # /users/557365723a31/profile
    def build_avatar_path(self, user: User) -> str:
        return os.path.join(self.user_folder_path(user), "profile")

    def _build_asset_file_path(
        self,
        user: User,
        folder: str,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ) -> str:
        user_folder_path = self.user_folder_path(user)
        assets_path = os.path.join(
            user_folder_path, folder, platform_fs_slug, str(rom_id)
        )
        if emulator:
            assets_path = os.path.join(assets_path, emulator)
        return assets_path

    # /users/557365723a31/saves/n64/{rom.id}/mupen64plus/
    def build_saves_file_path(
        self,
        user: User,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ) -> str:
        return self._build_asset_file_path(
            user, "saves", platform_fs_slug, rom_id, emulator
        )

    # /users/557365723a31/states/n64/{rom.id}/mupen64plus
    def build_states_file_path(
        self,
        user: User,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ) -> str:
        return self._build_asset_file_path(
            user, "states", platform_fs_slug, rom_id, emulator
        )

    # /users/557365723a31/screenshots/{rom.id}/n64
    def build_screenshots_file_path(
        self,
        user: User,
        platform_fs_slug: str,
        rom_id: int,
        emulator: str | None = None,
    ) -> str:
        return self._build_asset_file_path(
            user, "screenshots", platform_fs_slug, rom_id, emulator
        )

    # /users/557365723a31/memory_cards/pcsx2/{card_id}
    def build_memory_cards_file_path(
        self, user: User, emulator: str, card_id: int
    ) -> str:
        # Not scoped by rom/platform: a memory card is per (user, emulator) and
        # holds every game's saves. Versions share the folder, distinguished by
        # their timestamped file names.
        return os.path.join(
            self.user_folder_path(user), "memory_cards", emulator, str(card_id)
        )

    async def _compute_zip_hash(self, zip_path: str) -> str:
        def digest() -> str:
            with zipfile.ZipFile(self.base_path / zip_path, "r") as zf:
                return hash_zip_contents(zf)

        # Off the loop, as _compute_file_hash is: a state archive runs to tens of MB.
        return await asyncio.to_thread(digest)

    async def compute_content_hash(self, file_path: str) -> str | None:
        try:
            full_path = self.base_path / file_path
            if zipfile.is_zipfile(full_path):
                return await self._compute_zip_hash(file_path)
            return await self._compute_file_hash(file_path)
        except Exception as e:
            log.debug(f"Failed to compute content hash for {file_path}: {e}")
            return None

    async def unrecorded_hash(self, save: "Save") -> str | None:
        """The file's hash for a slotted save never hashed, so its removal is still recorded."""
        if save.slot and not save.content_hash:
            return await self.compute_content_hash(save.full_path)
        return None
