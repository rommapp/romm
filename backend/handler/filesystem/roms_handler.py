import asyncio
import binascii
import bz2
import fnmatch
import hashlib
import os
import re
import tarfile
import threading
import zipfile
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Final, Literal, TypedDict

import magic
import zipfile_inflate64  # trunk-ignore(ruff/F401): Patches zipfile to support Enhanced Deflate
from anyio import Path as AnyioPath

from config import LIBRARY_BASE_PATH
from config.config_manager import (
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
)
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    RomAlreadyExistsException,
    RomsNotFoundException,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.logger import log
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from utils.archive_7zip import (
    SevenZipExtractError,
    iter_7z_archive_files,
    process_file_7z,
)
from utils.filesystem import COMPRESSED_FILE_EXTENSIONS, iter_files
from utils.hashing import crc32_to_hex

from .base_handler import (
    LANGUAGES_BY_SHORTCODE,
    LANGUAGES_NAME_KEYS,
    REGIONS_BY_SHORTCODE,
    REGIONS_NAME_KEYS,
    TAG_REGEX,
    FSHandler,
)

# Known compressed file MIME types
COMPRESSED_MIME_TYPES: Final = frozenset(
    (
        "application/x-7z-compressed",
        "application/x-bzip2",
        "application/x-gzip",
        "application/x-tar",
        "application/zip",
    )
)

# PICO-8 cartridges are often stored as PNG files
PICO8_CARTRIDGE_EXTENSION = ".p8.png"


# CHD (Compressed Hunks of Data) v5 format constants
# See: https://github.com/mamedev/mame/blob/master/src/lib/util/chd.h
CHD_SIGNATURE: Final = b"MComprHD"
CHD_SIGNATURE_LENGTH: Final = 8
CHD_MIN_HEADER_LENGTH: Final = 16  # Minimum to read signature and version
CHD_V5_HEADER_LENGTH: Final = 124  # Total v5 header size
CHD_VERSION_OFFSET: Final = 12  # Bytes offset for version field
CHD_VERSION_LENGTH: Final = 4  # Version is a uint32
CHD_V5_SHA1_OFFSET: Final = 84  # Combined raw+meta SHA1 offset in v5
CHD_V5_SHA1_LENGTH: Final = 20  # SHA1 is 20 bytes
CHD_V5_VERSION: Final = 5  # CHD v5 identifier
CHD_MIME_TYPE: Final = "application/x-mame-chd"

NON_HASHABLE_PLATFORMS = frozenset(
    (
        UPS.AMAZON_ALEXA,
        UPS.AMAZON_FIRE_TV,
        UPS.ANDROID,
        UPS.GEAR_VR,
        UPS.IOS,
        UPS.IPAD,
        UPS.LINUX,
        UPS.MAC,
        UPS.META_QUEST_2,
        UPS.META_QUEST_3,
        UPS.OCULUS_GO,
        UPS.OCULUS_QUEST,
        UPS.OCULUS_RIFT,
        UPS.PS3,
        UPS.PS4,
        UPS.PS5,
        UPS.PSVR,
        UPS.PSVR2,
        UPS.SERIES_X_S,
        UPS.SWITCH,
        UPS.SWITCH_2,
        UPS.WIIU,
        UPS.WIN,
        UPS.XBOX360,
        UPS.XBOXONE,
        UPS.SERIES_X_S,
    )
)

FILE_READ_CHUNK_SIZE = 1024 * 8
_MIME_DETECTOR = magic.Magic(mime=True)
_MIME_DETECTOR_LOCK = threading.Lock()


class FSRom(TypedDict):
    fs_name: str
    flat: bool
    nested: bool
    files: list[RomFile]
    crc_hash: str
    md5_hash: str
    sha1_hash: str
    ra_hash: str


class FileHash(TypedDict):
    crc_hash: str
    md5_hash: str
    sha1_hash: str
    chd_sha1_hash: str


def is_compressed_file(file_path: str) -> bool:
    try:
        with _MIME_DETECTOR_LOCK:
            file_type = _MIME_DETECTOR.from_file(file_path)
    except magic.MagicException:
        file_type = ""

    return file_type in COMPRESSED_MIME_TYPES or file_path.lower().endswith(
        tuple(COMPRESSED_FILE_EXTENSIONS)
    )


def read_basic_file(file_path: os.PathLike[str]) -> Iterator[bytes]:
    with open(file_path, "rb") as f:
        while chunk := f.read(FILE_READ_CHUNK_SIZE):
            yield chunk


def read_zip_file(file: str | os.PathLike[str] | IO[bytes]) -> Iterator[bytes]:
    try:
        with zipfile.ZipFile(file, "r") as z:
            # Find the biggest file in the archive
            largest_file = max(z.infolist(), key=lambda x: x.file_size)
            with z.open(largest_file, "r") as f:
                while chunk := f.read(FILE_READ_CHUNK_SIZE):
                    yield chunk
    except zipfile.BadZipFile:
        if isinstance(file, Path):
            for chunk in read_basic_file(file):
                yield chunk


def read_tar_file(
    file_path: Path, mode: Literal["r", "r:*", "r:", "r:gz", "r:bz2", "r:xz"] = "r"
) -> Iterator[bytes]:
    try:
        with tarfile.open(file_path, mode) as f:
            regular_files = [member for member in f.getmembers() if member.isfile()]

            # Find the largest file among regular files only
            largest_file = max(regular_files, key=lambda x: x.size)
            with f.extractfile(largest_file) as ef:  # type: ignore
                while chunk := ef.read(FILE_READ_CHUNK_SIZE):
                    yield chunk
    except tarfile.ReadError:
        for chunk in read_basic_file(file_path):
            yield chunk


def read_gz_file(file_path: Path) -> Iterator[bytes]:
    return read_tar_file(file_path, "r:gz")


def process_7z_file(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
) -> None:
    processed = process_file_7z(
        file_path=file_path,
        fn_hash_update=fn_hash_update,
    )
    if not processed:
        for chunk in read_basic_file(file_path):
            fn_hash_update(chunk)


def read_bz2_file(file_path: Path) -> Iterator[bytes]:
    try:
        with bz2.BZ2File(file_path, "rb") as f:
            while chunk := f.read(FILE_READ_CHUNK_SIZE):
                yield chunk
    except EOFError:
        for chunk in read_basic_file(file_path):
            yield chunk


ARCHIVE_EXTENSIONS: Final = frozenset({".zip", ".tar", ".7z"})


def _chunked(stream: IO[bytes]) -> Iterator[bytes]:
    """Yield FILE_READ_CHUNK_SIZE-sized reads from ``stream`` until EOF."""
    return iter(lambda: stream.read(FILE_READ_CHUNK_SIZE), b"")


def _is_excluded_archive_entry(name: str) -> bool:
    """Apply the hardcoded default exclusions to an internal archive path."""
    base = Path(name).name
    lower = base.lower()
    if any(lower.endswith("." + ext) for ext in DEFAULT_EXCLUDED_EXTENSIONS):
        return True
    return any(
        base == exc or fnmatch.fnmatch(base, exc) for exc in DEFAULT_EXCLUDED_FILES
    )


def _iter_zip_entries(
    file_path: Path,
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            members = sorted(
                (e for e in z.infolist() if not e.is_dir()),
                key=lambda e: e.filename,
            )
            for entry in members:
                with z.open(entry, "r") as f:
                    yield entry.filename, entry.file_size, _chunked(f)
    except zipfile.BadZipFile:
        return


def _iter_tar_entries(
    file_path: Path,
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    try:
        with tarfile.open(file_path, "r") as tf:
            members = sorted(
                (m for m in tf.getmembers() if m.isfile()),
                key=lambda m: m.name,
            )
            for member in members:
                ef = tf.extractfile(member)
                if ef is None:
                    continue
                yield member.name, member.size, _chunked(ef)
    except tarfile.ReadError:
        return


_ARCHIVE_SOURCES: Final = {
    ".zip": _iter_zip_entries,
    ".tar": _iter_tar_entries,
    ".7z": iter_7z_archive_files,
}


def _iter_archive_entries(
    file_path: Path, ext: str
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield (name, size, chunk_iter) for every eligible archive entry, in ASCII name order.

    Eligibility is determined by the hardcoded default exclusions; user-configured
    EXCLUDED_MULTI_PARTS filters are intentionally ignored, as archives are assumed
    to be curated ROM sets where every file is relevant. The consumer must fully
    drain each chunk_iter before requesting the next entry.
    """
    source = _ARCHIVE_SOURCES.get(ext)
    if source is None:
        return
    for name, size, chunks in source(file_path):
        if _is_excluded_archive_entry(name):
            continue
        yield name, size, chunks


def is_chd_file(file_path: Path) -> bool:
    """Return True if the file is a CHD by extension or libmagic-detected MIME type."""
    if file_path.suffix.lower() == ".chd":
        return True

    try:
        with _MIME_DETECTOR_LOCK:
            return _MIME_DETECTOR.from_file(file_path) == CHD_MIME_TYPE
    except (OSError, magic.MagicException):
        return False


def extract_chd_hash(file_path: Path) -> str:
    """
    Extract the embedded SHA1 hash from a CHD (Compressed Hunks of Data) v5 file header.

    Only CHD v5 files are supported, matching MAMERedump's database.

    CHD v5 files store the combined raw+meta SHA1 hash in the header.
    This hash is what ROM databases use for CHD identification, since it includes
    metadata like CD track layouts which are essential for proper disc image
    identification.

    For reference, check out "chd.h" in the MAME source tree.

    ---------------------------------- Why? ----------------------------------
    CHDMAN does not produce nor guarantee stable, byte-for-byte identical
    outputs for a given disc image. (Including HD images.)

    For this reason, the CHD format embeds the original source data hash in
    its header, allowing different CHD files to be verified as equivalent
    even when their compressed representations differ.
    --------------------------------------------------------------------------

    Args:
        file_path: Path to the CHD file

    Returns:
        The embedded SHA1 hash as a hex string for a valid CHD v5 file, or an
        empty string if the file is invalid, uses an unsupported CHD version,
        is truncated, or cannot be read due to an I/O error.
    """
    try:
        with open(file_path, "rb") as f:
            # Read the v5 header and extract the embedded SHA1
            header = f.read(CHD_V5_HEADER_LENGTH)

            # Check for "MComprHD" signature
            if (
                len(header) < CHD_MIN_HEADER_LENGTH
                or header[:CHD_SIGNATURE_LENGTH] != CHD_SIGNATURE
            ):
                return ""

            # Extract and verify version (big-endian uint32)
            version_end = CHD_VERSION_OFFSET + CHD_VERSION_LENGTH
            version = int.from_bytes(header[CHD_VERSION_OFFSET:version_end], "big")

            # Only support v5 CHD files
            if version != CHD_V5_VERSION:
                return ""

            # Extract combined raw+meta SHA1 from v5 header
            sha1_end = CHD_V5_SHA1_OFFSET + CHD_V5_SHA1_LENGTH
            if len(header) < sha1_end:
                return ""
            sha1_bytes = header[CHD_V5_SHA1_OFFSET:sha1_end]
            return sha1_bytes.hex()
    except OSError:
        return ""


def category_matches(category: str, path_parts: list[str]):
    return category in path_parts or f"{category}s" in path_parts


DEFAULT_CRC_C = 0
DEFAULT_MD5_H_DIGEST = hashlib.md5(usedforsecurity=False).digest()
DEFAULT_SHA1_H_DIGEST = hashlib.sha1(usedforsecurity=False).digest()

VERSION_TAG_REGEX = re.compile(r"^(?:version|ver|v)[\s_-]?(.*)", re.I)
REGION_TAG_REGEX = re.compile(r"^reg[\s|-](.*)$", re.I)
REVISION_TAG_REGEX = re.compile(r"^rev[\s|-](.*)$", re.I)


@dataclass(frozen=True)
class ParsedTags:
    version: str
    revision: str
    regions: list[str]
    languages: list[str]
    other_tags: list[str]


@dataclass(frozen=True)
class ParsedRomFiles:
    rom_files: list[RomFile]
    crc_hash: str
    md5_hash: str
    sha1_hash: str
    ra_hash: str


class FSRomsHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LIBRARY_BASE_PATH)

    def get_roms_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()
        return (
            f"{fs_slug}/{cnfg.ROMS_FOLDER_NAME}"
            if cnfg.has_structure_path_b
            else f"{cnfg.ROMS_FOLDER_NAME}/{fs_slug}"
        )

    def parse_tags(self, fs_name: str) -> ParsedTags:
        tags = [
            chunk.strip()
            for tag in (m[0] or m[1] for m in TAG_REGEX.findall(fs_name))
            for chunk in tag.split(",")
        ]

        regions, languages, other_tags = [], [], []
        version = revision = ""

        for raw_tag in tags:
            lower_tag = raw_tag.lower()

            # Region by code
            if raw_tag in REGIONS_BY_SHORTCODE.keys():
                regions.append(REGIONS_BY_SHORTCODE[raw_tag])
                continue
            if lower_tag in REGIONS_NAME_KEYS:
                regions.append(raw_tag)
                continue

            # Language by code
            if raw_tag in LANGUAGES_BY_SHORTCODE.keys():
                languages.append(LANGUAGES_BY_SHORTCODE[raw_tag])
                continue
            if lower_tag in LANGUAGES_NAME_KEYS:
                languages.append(raw_tag)
                continue

            # Version
            version_match = VERSION_TAG_REGEX.match(raw_tag)
            if version_match:
                version = version_match[1]
                continue

            # Region prefix
            region_match = REGION_TAG_REGEX.match(raw_tag)
            if region_match:
                key = region_match[1].lower()
                regions.append(REGIONS_BY_SHORTCODE.get(key, region_match[1]))
                continue

            # Revision prefix
            revision_match = REVISION_TAG_REGEX.match(raw_tag)
            if revision_match:
                revision = revision_match[1]
                continue

            # Anything else
            other_tags.append(raw_tag)

        return ParsedTags(
            version=version,
            regions=regions,
            languages=languages,
            revision=revision,
            other_tags=other_tags,
        )

    def exclude_multi_roms(self, roms: list[str]) -> list[str]:
        excluded_names = cm.get_config().EXCLUDED_MULTI_FILES
        normalized_patterns = [
            excluded_name.lower().strip() for excluded_name in excluded_names
        ]

        kept_roms: list[str] = []
        for rom in roms:
            normalized_rom_name = rom.strip().lower()
            if normalized_rom_name in normalized_patterns:
                continue

            if any(
                fnmatch.fnmatch(normalized_rom_name, pattern)
                for pattern in normalized_patterns
            ):
                continue

            kept_roms.append(rom)

        return kept_roms

    def _build_rom_file(
        self,
        rom: Rom,
        rom_path: Path,
        file_name: str,
        file_hash: FileHash,
        file_size_bytes: int | None = None,
        last_modified: float | None = None,
    ) -> RomFile:
        abs_file_path = Path(self.base_path, rom_path, file_name)

        path_parts_lower = list(map(str.lower, rom_path.parts))
        matching_category = next(
            (
                category
                for category in RomFileCategory
                if category_matches(category.value, path_parts_lower)
            ),
            None,
        )

        return RomFile(
            rom=rom,
            rom_id=rom.id,
            file_name=file_name,
            file_path=str(rom_path),
            file_size_bytes=(
                file_size_bytes
                if file_size_bytes is not None
                else os.stat(abs_file_path).st_size
            ),
            last_modified=(
                last_modified
                if last_modified is not None
                else os.path.getmtime(abs_file_path)
            ),
            category=matching_category,
            crc_hash=file_hash["crc_hash"],
            md5_hash=file_hash["md5_hash"],
            sha1_hash=file_hash["sha1_hash"],
            chd_sha1_hash=file_hash["chd_sha1_hash"],
        )

    def _hash_archive_entries(
        self,
        rom: Rom,
        archive_path: Path,
        rom_path: Path,
        rom_crc_c: int,
        rom_md5_h: Any,
        rom_sha1_h: Any,
    ) -> tuple[list[RomFile], int, Any, Any] | None:
        """Build a RomFile per eligible internal archive entry, folding bytes into composite hashes.

        Returns ``None`` when the archive is empty, malformed, all-excluded, or fails
        mid-extraction — the caller should then fall back to single-file hashing of the
        archive itself. Composite accumulators are returned as fresh copies so the caller
        can swap them in atomically; failed runs leave the originals untouched.
        """
        archive_mtime = archive_path.stat().st_mtime
        archive_ext = archive_path.suffix.lower()
        # Work on copies so a partial failure leaves the caller's accumulators clean.
        rom_md5_h = rom_md5_h.copy()
        rom_sha1_h = rom_sha1_h.copy()
        files: list[RomFile] = []
        try:
            for name, size, chunks in _iter_archive_entries(archive_path, archive_ext):
                crc_c = 0
                md5_h = hashlib.md5(usedforsecurity=False)
                sha1_h = hashlib.sha1(usedforsecurity=False)
                for chunk in chunks:
                    crc_c = binascii.crc32(chunk, crc_c)
                    md5_h.update(chunk)
                    sha1_h.update(chunk)
                    rom_crc_c = binascii.crc32(chunk, rom_crc_c)
                    rom_md5_h.update(chunk)
                    rom_sha1_h.update(chunk)
                files.append(
                    self._build_rom_file(
                        rom=rom,
                        rom_path=rom_path,
                        file_name=name,
                        file_hash=FileHash(
                            crc_hash=(
                                crc32_to_hex(crc_c) if crc_c != DEFAULT_CRC_C else ""
                            ),
                            md5_hash=(
                                md5_h.hexdigest()
                                if md5_h.digest() != DEFAULT_MD5_H_DIGEST
                                else ""
                            ),
                            sha1_hash=(
                                sha1_h.hexdigest()
                                if sha1_h.digest() != DEFAULT_SHA1_H_DIGEST
                                else ""
                            ),
                            chd_sha1_hash="",
                        ),
                        file_size_bytes=size,
                        last_modified=archive_mtime,
                    )
                )
        except SevenZipExtractError as e:
            log.error(f"Aborting per-file hashing of {archive_path}: {e}")
            return None
        return (files, rom_crc_c, rom_md5_h, rom_sha1_h) if files else None

    async def get_rom_files(
        self, rom: Rom, calculate_hashes: bool = True
    ) -> ParsedRomFiles:
        from adapters.services.rahasher import RAHasherService
        from handler.metadata import meta_ra_handler

        rel_roms_path = self.get_roms_fs_structure(
            rom.platform.fs_slug
        )  # Relative path to roms
        abs_fs_path = self.validate_path(rel_roms_path)  # Absolute path to roms
        rom_files: list[RomFile] = []

        # Skip hashing games for platforms that don't have a hash database or when hashes are disabled
        hashable_platform = (
            rom.platform_slug not in NON_HASHABLE_PLATFORMS and calculate_hashes
        )

        cnfg = cm.get_config()
        excluded_file_names = cnfg.EXCLUDED_MULTI_PARTS_FILES
        excluded_file_exts = cnfg.EXCLUDED_MULTI_PARTS_EXT

        rom_crc_c = 0
        rom_md5_h = hashlib.md5(usedforsecurity=False) if calculate_hashes else None
        rom_sha1_h = hashlib.sha1(usedforsecurity=False) if calculate_hashes else None
        rom_ra_h = ""

        rom_dir = Path(abs_fs_path, rom.fs_name)
        rom_ext = rom_dir.suffix.lower()
        # Check if rom is a multi-part rom
        if await AnyioPath(f"{abs_fs_path}/{rom.fs_name}").is_dir():
            # Calculate the RA hash if the platform has a slug that matches a known RA slug
            if calculate_hashes:
                ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
                if ra_platform and ra_platform["ra_id"]:
                    # RAHasher can't process CHD files via the /* wildcard and instead expects
                    # track files (bin/cue/etc.). For CHD-only folders, find the largest
                    # CHD and pass it directly, matching single-file CHD behaviour.
                    chd_file = await asyncio.to_thread(
                        lambda: max(
                            (f for f in rom_dir.iterdir() if is_chd_file(f)),
                            key=lambda f: f.stat().st_size,
                            default=None,
                        )
                    )
                    ra_path = (
                        str(chd_file)
                        if chd_file and chd_file.is_file()
                        else f"{abs_fs_path}/{rom.fs_name}/*"
                    )
                    rom_ra_h = await RAHasherService().calculate_hash(
                        ra_platform,
                        ra_path,
                    )

            for f_path, file_name in iter_files(
                f"{abs_fs_path}/{rom.fs_name}", recursive=True
            ):
                # Check if file is excluded by extension.
                f_rom_dir = Path(f_path, rom.fs_name)
                file_name_lower = file_name.lower()
                if any(
                    file_name_lower.endswith("." + ext) for ext in excluded_file_exts
                ):
                    continue

                # Check if the file name matches a pattern in the excluded list.
                if any(
                    file_name == exc_name or fnmatch.fnmatch(file_name, exc_name)
                    for exc_name in excluded_file_names
                ):
                    continue

                # Check if this is a top-level file (not in a subdirectory)
                is_top_level = f_path.samefile(Path(abs_fs_path, rom.fs_name))

                if hashable_platform:
                    try:
                        if is_top_level:
                            # Include this file in the main ROM hash calculation
                            crc_c, rom_crc_c, md5_h, rom_md5_h, sha1_h, rom_sha1_h = (
                                await asyncio.to_thread(
                                    self._calculate_rom_hashes,
                                    Path(f_path, file_name),
                                    rom_crc_c,
                                    rom_md5_h,
                                    rom_sha1_h,
                                )
                            )
                        else:
                            # Calculate individual file hash only
                            crc_c, _, md5_h, _, sha1_h, _ = await asyncio.to_thread(
                                self._calculate_rom_hashes,
                                Path(f_path, file_name),
                                0,
                                hashlib.md5(usedforsecurity=False),
                                hashlib.sha1(usedforsecurity=False),
                            )
                    except zlib.error:
                        crc_c = 0
                        md5_h = hashlib.md5(usedforsecurity=False)
                        sha1_h = hashlib.sha1(usedforsecurity=False)

                    file_hash = FileHash(
                        crc_hash=crc32_to_hex(crc_c) if crc_c != DEFAULT_CRC_C else "",
                        md5_hash=(
                            md5_h.hexdigest()
                            if md5_h.digest() != DEFAULT_MD5_H_DIGEST
                            else ""
                        ),
                        sha1_hash=(
                            sha1_h.hexdigest()
                            if sha1_h.digest() != DEFAULT_SHA1_H_DIGEST
                            else ""
                        ),
                        chd_sha1_hash=(
                            extract_chd_hash(f_rom_dir)
                            if is_chd_file(f_rom_dir)
                            else ""
                        ),
                    )
                else:
                    file_hash = FileHash(
                        crc_hash="",
                        md5_hash="",
                        sha1_hash="",
                        chd_sha1_hash="",
                    )

                rom_files.append(
                    self._build_rom_file(
                        rom=rom,
                        rom_path=f_path.relative_to(self.base_path),
                        file_name=file_name,
                        file_hash=file_hash,
                    )
                )
        elif hashable_platform and rom_ext in ARCHIVE_EXTENSIONS and (
            archive_result := await asyncio.to_thread(
                self._hash_archive_entries,
                rom, rom_dir, Path(rel_roms_path),
                rom_crc_c, rom_md5_h, rom_sha1_h,
            )
        ) is not None:
            archive_files, rom_crc_c, rom_md5_h, rom_sha1_h = archive_result
            rom_files.extend(archive_files)
        elif hashable_platform:
            try:
                crc_c, rom_crc_c, md5_h, rom_md5_h, sha1_h, rom_sha1_h = (
                    await asyncio.to_thread(
                        self._calculate_rom_hashes,
                        Path(abs_fs_path, rom.fs_name),
                        rom_crc_c,
                        rom_md5_h,
                        rom_sha1_h,
                    )
                )
            except zlib.error:
                crc_c = 0
                md5_h = hashlib.md5(usedforsecurity=False)
                sha1_h = hashlib.sha1(usedforsecurity=False)

            # Calculate the RA hash if the platform has a slug that matches a known RA slug
            if calculate_hashes:
                ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
                if ra_platform and ra_platform["ra_id"]:
                    rom_ra_h = await RAHasherService().calculate_hash(
                        ra_platform,
                        f"{abs_fs_path}/{rom.fs_name}",
                    )

            file_hash = FileHash(
                crc_hash=crc32_to_hex(crc_c) if crc_c != DEFAULT_CRC_C else "",
                md5_hash=(
                    md5_h.hexdigest() if md5_h.digest() != DEFAULT_MD5_H_DIGEST else ""
                ),
                sha1_hash=(
                    sha1_h.hexdigest()
                    if sha1_h.digest() != DEFAULT_SHA1_H_DIGEST
                    else ""
                ),
                chd_sha1_hash=(
                    extract_chd_hash(rom_dir) if is_chd_file(rom_dir) else ""
                ),
            )
            rom_files.append(
                self._build_rom_file(
                    rom=rom,
                    rom_path=Path(rel_roms_path),
                    file_name=rom.fs_name,
                    file_hash=file_hash,
                )
            )
        else:
            file_hash = FileHash(
                crc_hash="",
                md5_hash="",
                sha1_hash="",
                chd_sha1_hash="",
            )
            rom_files.append(
                self._build_rom_file(
                    rom=rom,
                    rom_path=Path(rel_roms_path),
                    file_name=rom.fs_name,
                    file_hash=file_hash,
                )
            )

        return ParsedRomFiles(
            rom_files=rom_files,
            crc_hash=crc32_to_hex(rom_crc_c) if rom_crc_c != DEFAULT_CRC_C else "",
            md5_hash=(
                rom_md5_h.hexdigest()
                if rom_md5_h and rom_md5_h.digest() != DEFAULT_MD5_H_DIGEST
                else ""
            ),
            sha1_hash=(
                rom_sha1_h.hexdigest()
                if rom_sha1_h and rom_sha1_h.digest() != DEFAULT_SHA1_H_DIGEST
                else ""
            ),
            ra_hash=rom_ra_h,
        )

    def _calculate_rom_hashes(
        self,
        file_path: Path,
        rom_crc_c: int,
        rom_md5_h: Any,
        rom_sha1_h: Any,
    ) -> tuple[int, int, Any, Any, Any, Any]:
        extension = Path(file_path).suffix.lower()
        try:
            try:
                with _MIME_DETECTOR_LOCK:
                    file_type = _MIME_DETECTOR.from_file(file_path)
            except magic.MagicException:
                file_type = ""

            crc_c = 0
            md5_h = hashlib.md5(usedforsecurity=False)
            sha1_h = hashlib.sha1(usedforsecurity=False)

            def update_hashes(chunk: bytes | bytearray):
                md5_h.update(chunk)
                rom_md5_h.update(chunk)

                sha1_h.update(chunk)
                rom_sha1_h.update(chunk)

                nonlocal crc_c
                crc_c = binascii.crc32(chunk, crc_c)
                nonlocal rom_crc_c
                rom_crc_c = binascii.crc32(chunk, rom_crc_c)

            if extension == ".zip" or file_type == "application/zip":
                for chunk in read_zip_file(file_path):
                    update_hashes(chunk)

            elif extension == ".tar" or file_type == "application/x-tar":
                for chunk in read_tar_file(file_path):
                    update_hashes(chunk)

            elif extension == ".gz" or file_type == "application/x-gzip":
                for chunk in read_gz_file(file_path):
                    update_hashes(chunk)

            elif extension == ".7z" or file_type == "application/x-7z-compressed":
                process_7z_file(
                    file_path=file_path,
                    fn_hash_update=update_hashes,
                )

            elif extension == ".bz2" or file_type == "application/x-bzip2":
                for chunk in read_bz2_file(file_path):
                    update_hashes(chunk)

            else:
                for chunk in read_basic_file(file_path):
                    update_hashes(chunk)

            return crc_c, rom_crc_c, md5_h, rom_md5_h, sha1_h, rom_sha1_h
        except (FileNotFoundError, PermissionError):
            return (
                0,
                rom_crc_c,
                hashlib.md5(usedforsecurity=False),
                rom_md5_h,
                hashlib.sha1(usedforsecurity=False),
                rom_sha1_h,
            )

    async def count_roms(self, platform: Platform) -> int:
        """Return the number of filesystem roms for a platform without
        materializing FSRom objects.
        """
        try:
            rel_roms_path = self.get_roms_fs_structure(platform.fs_slug)
            fs_single_roms = await self.list_files(path=rel_roms_path)
            fs_multi_roms = await self.list_directories(path=rel_roms_path)
        except FileNotFoundError as e:
            raise RomsNotFoundException(platform=platform.fs_slug) from e

        return len(self.exclude_single_files(fs_single_roms)) + len(
            self.exclude_multi_roms(fs_multi_roms)
        )

    async def get_roms(self, platform: Platform) -> list[FSRom]:
        """Gets all filesystem roms for a platform

        Args:
            platform: platform where roms belong
        Returns:
            list with all the filesystem roms for a platform
        """
        try:
            rel_roms_path = self.get_roms_fs_structure(
                platform.fs_slug
            )  # Relative path to roms

            fs_single_roms = await self.list_files(path=rel_roms_path)
            fs_multi_roms = await self.list_directories(path=rel_roms_path)
        except FileNotFoundError as e:
            raise RomsNotFoundException(platform=platform.fs_slug) from e

        fs_roms: list[dict] = [
            {"fs_name": rom, "flat": True, "nested": False}
            for rom in self.exclude_single_files(fs_single_roms)
        ] + [
            {"fs_name": rom, "flat": False, "nested": True}
            for rom in self.exclude_multi_roms(fs_multi_roms)
        ]

        return sorted(
            [
                FSRom(
                    fs_name=rom["fs_name"],
                    flat=rom["flat"],
                    nested=rom["nested"],
                    files=[],
                    crc_hash="",
                    md5_hash="",
                    sha1_hash="",
                    ra_hash="",
                )
                for rom in fs_roms
            ],
            key=lambda rom: rom["fs_name"],
        )

    async def rename_fs_rom(self, old_name: str, new_name: str, fs_path: str) -> None:
        if new_name != old_name:
            file_path = f"{fs_path}/{new_name}"
            if await self.file_exists(file_path=file_path):
                raise RomAlreadyExistsException(new_name)

            await self.move_file_or_folder(
                f"{fs_path}/{old_name}", f"{fs_path}/{new_name}"
            )

    def get_pico8_cover_url(
        self, platform_slug: str, fs_name: str, fs_path: str
    ) -> str | None:
        """Return a ``file://`` URL for a PICO-8 cartridge label, or ``None``.

        PICO-8 ``.p8.png`` files are valid PNG images whose visual content *is*
        the cartridge label/cover art.  When such a ROM is found we can use the
        file itself as the cover instead of fetching one from an external source.
        """
        if platform_slug == UPS.PICO and fs_name.lower().endswith(
            PICO8_CARTRIDGE_EXTENSION
        ):
            self.validate_path(f"{fs_path}/{fs_name}")
            return f"file://{fs_path}/{fs_name}"
        return None
