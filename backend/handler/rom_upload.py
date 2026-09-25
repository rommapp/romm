"""One ingestion path for every file uploaded into a ROM's folder, whether the
bytes arrive in chunks or as a single multipart request."""

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from config import ROM_UPLOAD_ASSEMBLING_EXT
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.resources_handler import ALLOWED_MANUAL_EXTENSIONS
from handler.filesystem.roms_handler import category_for_path_parts
from handler.rom_conversion import promote_single_file_to_folder
from handler.rom_files import refresh_rom_files
from logger.logger import log
from models.rom import DocSource, Rom, RomFile, RomFileCategory
from utils.audio_tags import SOUNDTRACK_EXTENSIONS
from utils.media_types import ALLOWED_DOCUMENT_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS

# The folder each media route uploads into. The scanner maps these names back to
# the category, so a file landing here is registered the same way a scan would.
CATEGORY_UPLOAD_FOLDERS: dict[RomFileCategory, str] = {
    RomFileCategory.MANUAL: "manual",
    RomFileCategory.WALKTHROUGH: "walkthrough",
    RomFileCategory.SCREENSHOT: "screenshots",
    RomFileCategory.SOUNDTRACK: "soundtrack",
}


# What a folder the scanner maps to a media category may receive, so a file the
# tab could never show is refused before it lands.
CATEGORY_FILE_TYPES: dict[RomFileCategory, tuple[str, frozenset[str]]] = {
    RomFileCategory.MANUAL: ("manual", ALLOWED_MANUAL_EXTENSIONS),
    RomFileCategory.WALKTHROUGH: ("walkthrough", ALLOWED_DOCUMENT_EXTENSIONS),
    RomFileCategory.SCREENSHOT: ("image", ALLOWED_IMAGE_EXTENSIONS),
    RomFileCategory.SOUNDTRACK: ("audio", SOUNDTRACK_EXTENSIONS),
}


class UploadRejectedException(ValueError):
    """The upload names a file or folder the ROM's folder cannot take."""


class UploadConflictException(FileExistsError):
    """A file of that name is already in the ROM's folder."""


class UploadNotRegisteredException(Exception):
    """The file is on disk but the ROM's file rows could not be refreshed."""


@dataclass(frozen=True)
class UploadDestination:
    """Where an upload lands: the ROM it belongs to (none for a platform folder
    upload), the library-relative directory and the absolute file path."""

    rom: Rom | None
    rel_dir: str
    location: Path


def sanitize_upload_filename(filename: str) -> str:
    """A plain file name, or UploadRejectedException when it carries a path."""
    try:
        safe_filename = fs_rom_handler._sanitize_filename(filename)
    except ValueError as exc:
        raise UploadRejectedException(f"Invalid upload filename: {exc}") from exc
    if safe_filename != filename:
        raise UploadRejectedException(
            "Upload filename must be a plain file name, not a path"
        )
    return safe_filename


def parse_upload_folder(folder: str) -> str:
    """Normalize the target subfolder to a relative path made of plain names."""
    raw = folder.strip()
    if raw.startswith("/") or "\\" in raw:
        raise UploadRejectedException(
            "Upload folder must be a relative, forward-slashed path"
        )
    raw = raw.rstrip("/")
    if not raw:
        return ""
    segments = raw.split("/")
    for segment in segments:
        try:
            safe_segment = fs_rom_handler._sanitize_filename(segment)
        except ValueError as exc:
            raise UploadRejectedException(f"Invalid upload folder: {exc}") from exc
        if safe_segment != segment:
            raise UploadRejectedException(
                "Upload folder must be a relative path inside the game folder"
            )
    return "/".join(segments)


def assert_allowed_in_folder(folder: str, filename: str) -> None:
    """Refuse a file the category the folder maps to cannot hold."""
    category = category_for_path_parts(folder.lower().split("/"))
    if category is None or category not in CATEGORY_FILE_TYPES:
        return
    label, extensions = CATEGORY_FILE_TYPES[category]
    if os.path.splitext(filename)[1].lower() not in extensions:
        raise UploadRejectedException(
            f"Unsupported {label} file type. Allowed: {', '.join(sorted(extensions))}"
        )


def resolve_upload_destination(
    rom: Rom, folder: str, filename: str, *, overwrite: bool = False
) -> tuple[str, Path]:
    """The library-relative directory and absolute file path of an upload into a
    ROM, kept inside the folder a lone file gets promoted into.

    Raises:
        UploadRejectedException: The destination is unusable, the folder's
            category cannot hold the file, or the scanner would never register it.
        UploadConflictException: A file of that name is already there (or will
            be, once promoted), unless `overwrite` allows replacing it.
    """
    assert_allowed_in_folder(folder, filename)
    if fs_rom_handler.is_excluded_multi_part(filename):
        raise UploadRejectedException(
            f"File {filename} would be ignored by the scanner"
        )

    root = (
        f"{rom.fs_path}/{rom.fs_name_no_ext}"
        if rom.has_simple_single_file
        else rom.full_path
    )
    rel_dir = f"{root}/{folder}" if folder else root
    try:
        root_location = fs_rom_handler.validate_path(root)
        location = fs_rom_handler.validate_path(f"{rel_dir}/{filename}")
    except ValueError as exc:
        raise UploadRejectedException(str(exc)) from exc
    if not location.is_relative_to(root_location):
        raise UploadRejectedException(
            "Upload destination must be inside the game folder"
        )

    promoted_over_itself = (
        rom.has_simple_single_file and not folder and filename == rom.fs_name
    )
    replaceable = overwrite and location.is_file()
    if promoted_over_itself or (location.exists() and not replaceable):
        raise UploadConflictException(
            f"File {filename} already exists in the game folder"
        )
    return rel_dir, location


async def prepare_upload_destination(
    rom: Rom, folder: str, filename: str, *, overwrite: bool = False
) -> UploadDestination:
    """Resolve where the file lands, promote a lone file into its folder and
    create the target directory.

    Raises the same as `resolve_upload_destination`, plus
    RomAlreadyExistsException when the promotion collides with a folder.
    """
    rel_dir, location = resolve_upload_destination(
        rom, folder, filename, overwrite=overwrite
    )
    if rom.has_simple_single_file:
        rom = await promote_single_file_to_folder(rom)
    await fs_rom_handler.make_directory(rel_dir)
    return UploadDestination(rom=rom, rel_dir=rel_dir, location=location)


def staging_path(location: Path) -> Path:
    """A private sibling of the destination, so the final move is a rename on
    the same filesystem."""
    return location.with_name(
        f".{location.name}.{uuid4().hex}.{ROM_UPLOAD_ASSEMBLING_EXT}"
    )


def claim_destination(location: Path) -> None:
    """Create the final path exclusively, so two uploads racing for the same
    name cannot overwrite each other's bytes."""
    try:
        os.close(os.open(location, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
    except FileExistsError as exc:
        raise UploadConflictException(f"File {location.name} already exists") from exc


def _move_into_place(location: Path, staged: Path, *, overwrite: bool) -> None:
    claimed = False
    try:
        if not overwrite:
            claim_destination(location)
            claimed = True
        staged.replace(location)
    except BaseException:
        staged.unlink(missing_ok=True)
        if claimed:
            # The claim is an empty placeholder the rename never replaced;
            # left behind, a scan would ingest it as a zero-byte ROM.
            location.unlink(missing_ok=True)
        raise


async def commit_upload(
    destination: UploadDestination, staged: Path, *, overwrite: bool = False
) -> RomFile | None:
    """Move the staged bytes into place and register the file on its ROM.

    The staged file is removed whatever the outcome.

    Returns:
        The registered file row, or None for a platform folder upload.
    Raises:
        UploadConflictException: The name got taken while the bytes arrived.
        UploadNotRegisteredException: The file is in place but the ROM's rows
            could not be refreshed.
    """
    _move_into_place(destination.location, staged, overwrite=overwrite)
    log.info(f"Upload complete: {destination.location}")

    rom = destination.rom
    if rom is None:
        return None
    try:
        await refresh_rom_files(rom)
    except Exception as exc:
        log.error(f"Error registering uploaded file for ROM {rom.id}", exc_info=exc)
        raise UploadNotRegisteredException(
            "File uploaded but not registered yet, run a quick scan"
        ) from exc

    rom_file = db_rom_handler.get_rom_file_by_path(
        rom_id=rom.id,
        file_path=destination.rel_dir,
        file_name=destination.location.name,
    )
    # A scan records no provenance; an upload is one, whichever route took it.
    if (
        rom_file
        and rom_file.category == RomFileCategory.WALKTHROUGH
        and rom_file.doc_meta is None
    ):
        db_rom_handler.upsert_doc_meta(
            rom_file_id=rom_file.id, rom_id=rom.id, values={"source": DocSource.UPLOAD}
        )
    return rom_file
