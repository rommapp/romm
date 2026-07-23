import asyncio
import binascii
import fnmatch
import hashlib
import os
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from anyio import Path as AnyioPath

from adapters.services.sigil import (
    SIGIL_PLATFORM_SLUGS,
    SigilExtractionResult,
    SigilService,
)
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
from models.rom import Rom, RomFile, RomFileCategory, SaveUsage, TrackMeta
from utils.archives import (
    ArchiveReadError,
    detect_mime_type,
    extract_chd_hash,
    is_chd_file,
    process_7z_file,
    read_7z_archive_files,
    read_basic_file,
    read_bz2_file,
    read_gz_file,
    read_rar_archive_files,
    read_tar_archive_files,
    read_tar_file,
    read_zip_archive_files,
    read_zip_file,
)
from utils.filesystem import iter_files
from utils.hashing import crc32_to_hex

from .base_handler import (
    LANGUAGES_BY_SHORTCODE,
    LANGUAGES_NAME_KEYS,
    REGIONS_BY_SHORTCODE,
    REGIONS_NAME_KEYS,
    FSHandler,
)

# PICO-8 cartridges are often stored as PNG files
PICO8_CARTRIDGE_EXTENSION = ".p8.png"


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


class FSRom(TypedDict):
    fs_name: str
    flat: bool
    nested: bool
    files: list[RomFile]
    crc_hash: str
    md5_hash: str
    sha1_hash: str
    ra_hash: str
    title_id: NotRequired[str | None]
    save_id: NotRequired[str | None]
    save_usage: NotRequired[SaveUsage | None]


class FileHash(TypedDict):
    crc_hash: str
    md5_hash: str
    sha1_hash: str
    chd_sha1_hash: str


def category_matches(category: str, path_parts: list[str]):
    return category in path_parts or f"{category}s" in path_parts


DEFAULT_CRC_C = 0
DEFAULT_MD5_H_DIGEST = hashlib.md5(usedforsecurity=False).digest()
DEFAULT_SHA1_H_DIGEST = hashlib.sha1(usedforsecurity=False).digest()

ARCHIVE_READERS = {
    ".zip": read_zip_archive_files,
    ".tar": read_tar_archive_files,
    ".tar.gz": read_tar_archive_files,
    ".tgz": read_tar_archive_files,
    ".tar.bz2": read_tar_archive_files,
    ".tbz2": read_tar_archive_files,
    ".tar.xz": read_tar_archive_files,
    ".txz": read_tar_archive_files,
    ".7z": read_7z_archive_files,
    ".rar": read_rar_archive_files,
}


def _make_file_hash(
    crc_c: int, md5_h: Any, sha1_h: Any, chd_sha1_hash: str = ""
) -> FileHash:
    """Build a FileHash, blanking each field whose hasher state is still the default."""
    return FileHash(
        crc_hash=crc32_to_hex(crc_c) if crc_c != DEFAULT_CRC_C else "",
        md5_hash=md5_h.hexdigest() if md5_h.digest() != DEFAULT_MD5_H_DIGEST else "",
        sha1_hash=(
            sha1_h.hexdigest() if sha1_h.digest() != DEFAULT_SHA1_H_DIGEST else ""
        ),
        chd_sha1_hash=chd_sha1_hash,
    )


GENERIC_TAG_REGEX = re.compile(r"\(([^)]+)\)|\[([^]]+)\]")
VERSION_TAG_REGEX = re.compile(r"^(?:version|ver|v)(?:[\s._-](.*)|([.\d].*))", re.I)
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
    title_id: str | None = None
    save_id: str | None = None
    save_usage: SaveUsage | None = None
    # Set when a single-file rom's file was renamed on disk to embed its title
    # id, so the caller can reconcile Rom.fs_name. None for multi-part roms
    # (whose folder name is unchanged) or when no rename happened.
    renamed_rom_fs_name: str | None = None


# Maps sigil's Switch CNMT content type to the RomFile category. Authoritative
# over folder-derived categories when the binary parse succeeds.
SWITCH_CONTENT_TYPE_CATEGORIES: dict[str, RomFileCategory] = {
    "application": RomFileCategory.GAME,
    "patch": RomFileCategory.UPDATE,
    "addon": RomFileCategory.DLC,
}

# Platforms whose files may have their title id embedded in the filename.
EMBED_TITLE_ID_PLATFORM_SLUGS = frozenset((UPS.SWITCH, UPS.SWITCH_2))

# A 16-hex-digit title id in square brackets, e.g. [0100F4700B2E0000]. Used both
# to detect files that already carry an embedded id (idempotency) and to
# validate the id before embedding it.
SWITCH_TITLE_ID_BRACKET_REGEX = re.compile(r"\[[0-9A-Fa-f]{16}\]")
SWITCH_TITLE_ID_REGEX = re.compile(r"^[0-9A-Fa-f]{16}$")


def _embed_switch_title_id_in_name(
    abs_file_path: Path, title_id: str, title_version: int | None
) -> Path | None:
    """Rename a Switch ROM file to embed its title id and version as
    ` [TITLEID][vVERSION]` before the extension, preserving existing tags.

    Returns the new absolute path, or None when the file was left untouched:
    it already carries a 16-hex title-id bracket, the id is not a valid 16-hex
    value, or the target name already exists on disk. The os.rename is the only
    side effect.
    """
    name = abs_file_path.name

    if SWITCH_TITLE_ID_BRACKET_REGEX.search(name):
        log.debug(f"{name} already has an embedded title id, skipping rename")
        return None

    if not SWITCH_TITLE_ID_REGEX.match(title_id):
        log.debug(f"Title id {title_id!r} is not a 16-hex value, skipping rename")
        return None

    version = title_version if title_version is not None else 0
    new_name = (
        f"{abs_file_path.stem} [{title_id.upper()}][v{version}]{abs_file_path.suffix}"
    )
    new_path = abs_file_path.with_name(new_name)

    if new_path.exists():
        log.warning(
            f"Cannot embed title id: target {new_name} already exists, skipping rename"
        )
        return None

    os.rename(abs_file_path, new_path)
    log.info(f"Embedded Switch title id: renamed {name} to {new_name}")
    return new_path


def _parse_save_usage(usage: str) -> SaveUsage | None:
    try:
        return SaveUsage(usage)
    except ValueError:
        return None


def _is_switch_base_title_id(title_id: str) -> bool:
    """Base-game Switch title ids have their low 12 bits cleared and an even
    program-index nibble; update/DLC ids differ only in those positions."""
    if len(title_id) < 4 or not title_id.endswith("000"):
        return False
    try:
        return int(title_id[-4], 16) % 2 == 0
    except ValueError:
        return False


def _derive_switch_base_title_id(title_id: str) -> str | None:
    """Derive the base-game title id from an update/DLC id: clear the low 12
    bits and decrement the program-index nibble when it is odd."""
    if len(title_id) < 4:
        return None
    nibble_char = title_id[-4]
    try:
        nibble = int(nibble_char, 16)
    except ValueError:
        return None
    if nibble % 2 == 1:
        nibble -= 1
    formatted = format(nibble, "x" if nibble_char.islower() else "X")
    return f"{title_id[:-4]}{formatted}000"


def _rom_level_title_values(
    platform_slug: str,
    extractions: list[SigilExtractionResult],
) -> tuple[str | None, str | None, SaveUsage | None]:
    if not extractions:
        return None, None, None

    if platform_slug in (UPS.SWITCH, UPS.SWITCH_2):
        base = next(
            (e for e in extractions if _is_switch_base_title_id(e.title_id)), None
        )
        if base is not None:
            return base.title_id, base.save_id, _parse_save_usage(base.usage)

        derived = _derive_switch_base_title_id(extractions[0].title_id)
        if derived is None:
            return None, None, None
        # Switch saves are keyed by the base title id itself.
        return derived, derived, SaveUsage.FOLDER_EXACT

    first = extractions[0]
    return first.title_id, first.save_id, _parse_save_usage(first.usage)


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
            for tag in (m[0] or m[1] for m in GENERIC_TAG_REGEX.findall(fs_name))
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
                version = (version_match[1] or version_match[2] or "").strip()
                continue

            # Region prefix
            region_match = REGION_TAG_REGEX.match(raw_tag)
            if region_match:
                region = region_match[1]
                regions.append(REGIONS_BY_SHORTCODE.get(region, region))
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
        archive_members: list[dict[str, Any]] | None = None,
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

        track_meta = None
        if matching_category == RomFileCategory.SOUNDTRACK:
            from utils.audio_tags import (
                extract_audio_meta,
                is_allowed_audio_file,
                track_meta_columns,
            )

            if is_allowed_audio_file(file_name):
                meta = extract_audio_meta(str(abs_file_path))
                if meta:
                    track_meta = TrackMeta(rom_id=rom.id, **track_meta_columns(meta))

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
            track_meta=track_meta,
            crc_hash=file_hash["crc_hash"],
            md5_hash=file_hash["md5_hash"],
            sha1_hash=file_hash["sha1_hash"],
            chd_sha1_hash=file_hash["chd_sha1_hash"],
            archive_members=archive_members,
        )

    async def get_rom_files(
        self,
        rom: Rom,
        calculate_hashes: bool = True,
        extract_title_ids: bool = True,
        prod_keys_path: str | None = None,
        embed_title_ids: bool = False,
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

        # Title id extraction is independent of hashing support: it covers
        # non-hashable platforms like Switch.
        sigil_platform = extract_title_ids and rom.platform_slug in SIGIL_PLATFORM_SLUGS
        sigil_extractions: list[SigilExtractionResult] = []

        # Filename embedding is Switch-only, even though sigil covers more
        # platforms; other platforms never have their files renamed.
        embed_switch = (
            embed_title_ids and rom.platform_slug in EMBED_TITLE_ID_PLATFORM_SLUGS
        )
        renamed_rom_fs_name: str | None = None

        async def _extract_title_id(
            rom_file: RomFile, abs_file_path: Path, is_rom_level: bool = False
        ) -> None:
            nonlocal renamed_rom_fs_name
            extraction = await SigilService().extract_title_id(
                rom.platform_slug, str(abs_file_path), prod_keys_path
            )
            if extraction is None:
                return
            rom_file.title_id = extraction.title_id
            rom_file.save_id = extraction.save_id
            rom_file.title_version = extraction.version
            # For Switch, the binary CNMT content type is authoritative over the
            # folder-derived category. Leave the folder category when absent.
            if extraction.content_type is not None:
                category = SWITCH_CONTENT_TYPE_CATEGORIES.get(extraction.content_type)
                if category is not None:
                    rom_file.category = category
            sigil_extractions.append(extraction)

            if embed_switch and extraction.title_id:
                new_path = _embed_switch_title_id_in_name(
                    abs_file_path, extraction.title_id, extraction.version
                )
                if new_path is not None:
                    # The file stays in the same directory, so only file_name
                    # changes; file_path is unaffected.
                    rom_file.file_name = new_path.name
                    # A single-file rom's file name IS the Rom.fs_name, so the
                    # caller must reconcile it. Multi-part inner files don't
                    # change the rom folder name.
                    if is_rom_level:
                        renamed_rom_fs_name = new_path.name

        cnfg = cm.get_config()
        excluded_file_names = cnfg.EXCLUDED_MULTI_PARTS_FILES
        excluded_file_exts = cnfg.EXCLUDED_MULTI_PARTS_EXT

        rom_crc_c = 0
        rom_md5_h = hashlib.md5(usedforsecurity=False) if calculate_hashes else None
        rom_sha1_h = hashlib.sha1(usedforsecurity=False) if calculate_hashes else None
        rom_ra_h = ""

        rom_dir = Path(abs_fs_path, rom.fs_name)
        rom_ext = f".{rom.fs_extension.lower()}" if rom.fs_extension else ""

        # Check if rom is a multi-part rom
        if await AnyioPath(f"{abs_fs_path}/{rom.fs_name}").is_dir():
            # Calculate the RA hash if the platform has a slug that matches a known RA slug
            if calculate_hashes:
                ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
                if ra_platform and ra_platform["ra_id"]:
                    # RAHasher can't process CHD files via the /* wildcard and instead expects
                    # track files (bin/cue/etc.). For CHD-only folders, find the largest
                    # CHD and pass it directly, matching single-file CHD behaviour.

                    def _largest_chd_file() -> Path | None:
                        chds = [f for f in rom_dir.iterdir() if is_chd_file(f)]
                        sorted_chds = sorted(
                            chds, key=lambda f: f.stat().st_size, reverse=True
                        )
                        return sorted_chds[0] if sorted_chds else None

                    chd_file = await asyncio.to_thread(_largest_chd_file)
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

                    file_hash = _make_file_hash(
                        crc_c,
                        md5_h,
                        sha1_h,
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

                rom_file = self._build_rom_file(
                    rom=rom,
                    rom_path=f_path.relative_to(self.base_path),
                    file_name=file_name,
                    file_hash=file_hash,
                )
                # Extract from every file (base, updates, DLC in subfolders), not
                # just the top-level one: sigil returns None for unparseable files.
                if sigil_platform:
                    await _extract_title_id(rom_file, Path(f_path, file_name))
                rom_files.append(rom_file)
        elif hashable_platform and rom_ext in ARCHIVE_READERS:
            # Multi-file archive: compute a composite hash across all
            # internal entries (in ASCII path order) for hash-database
            # matching, while still emitting a single RomFile for the
            # archive file itself. Per-member hashes are stored on that
            # RomFile in `archive_members` so consumers can identify each
            # internal file without us inventing RomFile rows whose
            # full_path would point inside the archive and break downloads.
            assert rom_md5_h is not None and rom_sha1_h is not None

            def _hash_archive_entries(
                crc: int, md5_h: Any, sha1_h: Any
            ) -> tuple[list[dict[str, Any]], int, Any, Any]:
                # Accumulate into copies so an archive we can't read in full
                # leaves the caller's hashers untouched for the raw fallback.
                original_crc, md5_h, sha1_h = crc, md5_h.copy(), sha1_h.copy()
                members: list[dict[str, Any]] = []
                try:
                    for name, size, chunks in ARCHIVE_READERS[rom_ext](
                        rom_dir,
                        DEFAULT_EXCLUDED_FILES,
                        DEFAULT_EXCLUDED_EXTENSIONS,
                    ):
                        member_crc = 0
                        member_md5 = hashlib.md5(usedforsecurity=False)
                        member_sha1 = hashlib.sha1(usedforsecurity=False)
                        for chunk in chunks:
                            crc = binascii.crc32(chunk, crc)
                            md5_h.update(chunk)
                            sha1_h.update(chunk)
                            member_crc = binascii.crc32(chunk, member_crc)
                            member_md5.update(chunk)
                            member_sha1.update(chunk)
                        members.append(
                            {
                                "name": name,
                                "size": size,
                                "crc_hash": crc32_to_hex(member_crc),
                                "md5_hash": member_md5.hexdigest(),
                                "sha1_hash": member_sha1.hexdigest(),
                            }
                        )
                except ArchiveReadError as e:
                    log.error(f"Incomplete read of archive {rom_dir}: {e}")
                    return [], original_crc, None, None
                return members, crc, md5_h, sha1_h

            members, rom_crc_c, archive_md5_h, archive_sha1_h = await asyncio.to_thread(
                _hash_archive_entries, rom_crc_c, rom_md5_h, rom_sha1_h
            )

            if members:
                rom_md5_h, rom_sha1_h = archive_md5_h, archive_sha1_h
                if calculate_hashes:
                    ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
                    if ra_platform and ra_platform["ra_id"]:
                        rom_ra_h = await RAHasherService().calculate_hash(
                            ra_platform,
                            f"{abs_fs_path}/{rom.fs_name}",
                        )

                rom_files.append(
                    self._build_rom_file(
                        rom=rom,
                        rom_path=Path(rel_roms_path),
                        file_name=rom.fs_name,
                        file_hash=_make_file_hash(rom_crc_c, rom_md5_h, rom_sha1_h),
                        archive_members=members,
                    )
                )
            else:
                # Empty, malformed, unreadable, or all-excluded archive: hash the archive
                # file's raw bytes. We avoid `_calculate_rom_hashes` here because
                # it would decompress based on extension and end up hashing the
                # largest internal member, not the archive itself — and would
                # crash on an empty zip. `archive_members` stays None.
                def _hash_raw_archive(crc: int) -> int:
                    for chunk in read_basic_file(rom_dir):
                        crc = binascii.crc32(chunk, crc)
                        if rom_md5_h:
                            rom_md5_h.update(chunk)
                        if rom_sha1_h:
                            rom_sha1_h.update(chunk)
                    return crc

                rom_crc_c = await asyncio.to_thread(_hash_raw_archive, rom_crc_c)
                rom_files.append(
                    self._build_rom_file(
                        rom=rom,
                        rom_path=Path(rel_roms_path),
                        file_name=rom.fs_name,
                        file_hash=_make_file_hash(rom_crc_c, rom_md5_h, rom_sha1_h),
                    )
                )
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

            file_hash = _make_file_hash(
                crc_c,
                md5_h,
                sha1_h,
                chd_sha1_hash=(
                    extract_chd_hash(rom_dir) if is_chd_file(rom_dir) else ""
                ),
            )
            rom_file = self._build_rom_file(
                rom=rom,
                rom_path=Path(rel_roms_path),
                file_name=rom.fs_name,
                file_hash=file_hash,
            )
            if sigil_platform:
                await _extract_title_id(rom_file, rom_dir, is_rom_level=True)
            rom_files.append(rom_file)
        else:
            file_hash = FileHash(
                crc_hash="",
                md5_hash="",
                sha1_hash="",
                chd_sha1_hash="",
            )
            rom_file = self._build_rom_file(
                rom=rom,
                rom_path=Path(rel_roms_path),
                file_name=rom.fs_name,
                file_hash=file_hash,
            )
            # Archives keep hashes only; sigil reads title ids from the ROM
            # binary itself.
            if sigil_platform and rom_ext not in ARCHIVE_READERS:
                await _extract_title_id(rom_file, rom_dir, is_rom_level=True)
            rom_files.append(rom_file)

        rom_title_id, rom_save_id, rom_save_usage = _rom_level_title_values(
            rom.platform_slug, sigil_extractions
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
            title_id=rom_title_id,
            save_id=rom_save_id,
            save_usage=rom_save_usage,
            renamed_rom_fs_name=renamed_rom_fs_name,
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
            file_type = detect_mime_type(file_path)

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
