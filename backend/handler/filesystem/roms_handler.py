import asyncio
import binascii
import fnmatch
import hashlib
import os
import re
import struct
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NotRequired, TypedDict

from anyio import Path as AnyioPath

from adapters.services.sigil import (
    SIGIL_PLATFORM_SLUGS,
    SWITCH_PLATFORM_SLUGS,
    SigilExtractionResult,
    SigilService,
)
from config import LIBRARY_BASE_PATH
from config.config_manager import (
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
    Config,
)
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    RomAlreadyExistsException,
    RomsNotFoundException,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.logger import log
from models.base import compute_file_extension, compute_file_name_no_ext
from models.platform import Platform
from models.rom import (
    DOCUMENT_CATEGORIES,
    Rom,
    RomFile,
    RomFileCategory,
    SaveTargetLayout,
    TrackMeta,
)
from utils import switch
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
    REGIONS_BY_SHORTCODE,
    FSHandler,
    normalize_language,
    normalize_region,
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
    save_target: NotRequired[str | None]
    save_target_layout: NotRequired[SaveTargetLayout | None]


class FileHash(TypedDict):
    crc_hash: str
    md5_hash: str
    sha1_hash: str
    chd_sha1_hash: str


def category_matches(category: str, path_parts: list[str]) -> bool:
    return any(
        form in path_parts for form in (category, f"{category}s", f"{category}es")
    )


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


def _chd_sha1_hash(file_path: Path) -> str:
    """Return the embedded CHD v5 raw+meta SHA-1, or "" for non-CHD files."""
    return extract_chd_hash(file_path) if is_chd_file(file_path) else ""


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
    # False when an incremental listing found the top-level files untouched, in
    # which case the hashes above are the stored ones rather than recomputed.
    top_level_changed: bool = True
    title_id: str | None = None
    save_target: str | None = None
    save_target_layout: SaveTargetLayout | None = None
    # Set when a single-file rom's file was renamed on disk to embed its title
    # id, so the caller can reconcile Rom.fs_name.
    renamed_rom_fs_name: str | None = None


RomFileKey = tuple[str, str]
DirEntry = tuple[Path, str, os.stat_result]


def rom_file_key(rom_file: RomFile) -> RomFileKey:
    return (rom_file.file_path, rom_file.file_name)


def mtime_matches(stored: float | None, actual: float) -> bool:
    """Compare a stored mtime with the one on disk, also accepting rows written
    through the former single-precision column."""
    if stored is None:
        return False
    return stored == actual or stored == struct.unpack("f", struct.pack("f", actual))[0]


def rom_file_unchanged(
    row: RomFile, *, size: int, mtime: float, hashable: bool
) -> bool:
    """Whether a stored row still describes the file on disk, so its hashes can
    be reused instead of re-reading the bytes."""
    return (
        row.file_size_bytes == size
        and mtime_matches(row.last_modified, mtime)
        and (not hashable or bool(row.md5_hash))
    )


async def _flat_file_unchanged(row: RomFile, file_path: Path, hashable: bool) -> bool:
    try:
        st = await asyncio.to_thread(os.stat, file_path)
    except OSError:
        return False
    return rom_file_unchanged(
        row, size=st.st_size, mtime=st.st_mtime, hashable=hashable
    )


def _top_level_changed(
    entries: list[DirEntry],
    rom_dir: Path,
    rel_rom_dir: str,
    existing_by_key: Mapping[RomFileKey, RomFile],
    hashable: bool,
) -> bool:
    """Whether a top-level file was added, changed or removed since the rows
    were written, which forces re-reading that whole level for the ROM hash."""
    seen: set[RomFileKey] = set()
    for f_path, file_name, st in entries:
        if f_path != rom_dir:
            continue
        key = (rel_rom_dir, file_name)
        seen.add(key)
        row = existing_by_key.get(key)
        if row is None or not rom_file_unchanged(
            row, size=st.st_size, mtime=st.st_mtime, hashable=hashable
        ):
            return True
    return any(key[0] == rel_rom_dir and key not in seen for key in existing_by_key)


# File categories that never hold a ROM binary, so sigil has nothing to read.
NON_BINARY_FILE_CATEGORIES: Final = DOCUMENT_CATEGORIES | {
    RomFileCategory.SOUNDTRACK,
    RomFileCategory.SCREENSHOT,
    RomFileCategory.CHEAT,
}


def _parse_save_target_layout(usage: str) -> SaveTargetLayout | None:
    try:
        return SaveTargetLayout(usage)
    except ValueError:
        log.warning(f"Unrecognized sigil save target layout {usage!r}")
        return None


def _rom_level_title_values(
    platform_slug: str,
    extractions: list[SigilExtractionResult],
) -> tuple[str | None, str | None, SaveTargetLayout | None]:
    if not extractions:
        return None, None, None

    if platform_slug in SWITCH_PLATFORM_SLUGS:
        chosen = next(
            (e for e in extractions if switch.is_base_title_id(e.title_id)), None
        )
        if chosen is None:
            derived = switch.derive_base_title_id(extractions[0].title_id)
            if derived is None:
                return None, None, None
            # Switch saves are keyed by the base title id itself.
            return derived, derived, SaveTargetLayout.FOLDER_EXACT
    else:
        chosen = extractions[0]

    return chosen.title_id, chosen.save_target, _parse_save_target_layout(chosen.usage)


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
            # Region by exact code, before any language check: some language
            # shortcodes differ from a region code only by case (Nl/NL, No/NO).
            if raw_tag in REGIONS_BY_SHORTCODE.keys():
                regions.append(REGIONS_BY_SHORTCODE[raw_tag])
                continue

            # Language by exact code, for the same reason
            if raw_tag in LANGUAGES_BY_SHORTCODE.keys():
                languages.append(LANGUAGES_BY_SHORTCODE[raw_tag])
                continue

            # Region by name, alternate spelling, or differently-cased code.
            # Ahead of the equivalent language pass so a lowercased code that
            # both tables claim ("nl", "no") keeps reading as a region.
            region = normalize_region(raw_tag)
            if region:
                regions.append(region)
                continue

            language = normalize_language(raw_tag)
            if language:
                languages.append(language)
                continue

            # Version
            version_match = VERSION_TAG_REGEX.match(raw_tag)
            if version_match:
                version = (version_match[1] or version_match[2] or "").strip()
                continue

            # Region prefix. An explicit "Reg-" means the user called it a
            # region, so an unrecognized code is kept rather than dropped.
            region_match = REGION_TAG_REGEX.match(raw_tag)
            if region_match:
                # Stripped because the separator class doesn't swallow a space
                # after "Reg-", which would make " PAL" its own facet value.
                raw_region = region_match[1].strip()
                if raw_region:
                    regions.append(normalize_region(raw_region) or raw_region)
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

    def is_excluded_multi_part(
        self, file_name: str, cnfg: Config | None = None
    ) -> bool:
        """Whether the scanner ignores a file with this name inside a ROM folder."""
        cnfg = cnfg or cm.get_config()
        file_name_lower = file_name.lower()
        if any(
            file_name_lower.endswith(f".{ext}") for ext in cnfg.EXCLUDED_MULTI_PARTS_EXT
        ):
            return True
        return any(
            file_name == exc_name or fnmatch.fnmatch(file_name, exc_name)
            for exc_name in cnfg.EXCLUDED_MULTI_PARTS_FILES
        )

    def _list_rom_dir(self, rom_dir: Path, cnfg: Config) -> list[DirEntry]:
        """Every file under a ROM folder, at any depth, with its stat."""
        entries: list[DirEntry] = []
        for f_path, file_name in iter_files(str(rom_dir), recursive=True):
            if self.is_excluded_multi_part(file_name, cnfg):
                continue
            try:
                entries.append((f_path, file_name, os.stat(Path(f_path, file_name))))
            except OSError as exc:
                log.warning(f"Skipping unreadable file {f_path / file_name}: {exc}")
        return entries

    async def get_rom_files(
        self,
        rom: Rom,
        calculate_hashes: bool = True,
        extract_title_ids: bool = True,
        embed_title_ids: bool = False,
        *,
        existing_files: Sequence[RomFile] | None = None,
    ) -> ParsedRomFiles:
        """Build the ROM's file rows from disk.

        Args:
            existing_files: The rows currently stored for the ROM. When given,
                files whose size and mtime still match are returned as those
                very rows with their hashes untouched, and the ROM-level hashes
                are only recomputed when a top-level file changed.
        """
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
        is_switch = rom.platform_slug in SWITCH_PLATFORM_SLUGS
        sigil_extractions: list[SigilExtractionResult] = []
        sigil_service = SigilService()

        # Embedding is Switch-only even though sigil covers more platforms.
        embed_switch = embed_title_ids and is_switch
        renamed_rom_fs_name: str | None = None

        async def _extract_title_id(rom_file: RomFile) -> str | None:
            """Populate the file's title id fields, returning its new name if
            embedding renamed it on disk."""
            # Only Switch needs a per-file content type; one extraction is
            # enough elsewhere.
            if not sigil_platform or (sigil_extractions and not is_switch):
                return None

            rel_file_path = Path(rom_file.file_path, rom_file.file_name)
            extraction = await sigil_service.extract_title_id(
                rom.platform_slug, str(Path(self.base_path, rel_file_path))
            )
            if extraction is None:
                return None
            if extraction.content_type is not None:
                category = switch.CONTENT_TYPE_CATEGORIES.get(extraction.content_type)
                if category is not None:
                    rom_file.category = category
            sigil_extractions.append(extraction)

            if not (embed_switch and extraction.title_id):
                return None

            new_name = await self._embed_switch_title_id_in_name(
                rel_file_path, extraction.title_id, extraction.version
            )
            if new_name is not None:
                rom_file.file_name = new_name
            return new_name

        cnfg = cm.get_config()
        existing_by_key: Mapping[RomFileKey, RomFile] | None = (
            {rom_file_key(f): f for f in existing_files}
            if existing_files is not None
            else None
        )

        rom_crc_c = 0
        rom_md5_h = hashlib.md5(usedforsecurity=False) if calculate_hashes else None
        rom_sha1_h = hashlib.sha1(usedforsecurity=False) if calculate_hashes else None
        rom_ra_h = ""
        top_level_changed = True

        rom_dir = Path(abs_fs_path, rom.fs_name)
        rom_ext = f".{rom.fs_extension.lower()}" if rom.fs_extension else ""

        # Check if rom is a multi-part rom
        if await AnyioPath(f"{abs_fs_path}/{rom.fs_name}").is_dir():
            rel_rom_dir = str(rom_dir.relative_to(self.base_path))
            entries = await asyncio.to_thread(self._list_rom_dir, rom_dir, cnfg)
            if existing_by_key is not None:
                top_level_changed = _top_level_changed(
                    entries, rom_dir, rel_rom_dir, existing_by_key, hashable_platform
                )

            # Calculate the RA hash if the platform has a slug that matches a known RA slug
            if calculate_hashes and top_level_changed:
                ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
                if ra_platform and ra_platform["ra_id"]:
                    # RAHasher can't process CHD files via the /* wildcard and instead expects
                    # track files (bin/cue/etc.). For CHD-only folders, find the largest
                    # CHD and pass it directly, matching single-file CHD behaviour.
                    top_level_chds = [
                        (st.st_size, Path(f_path, file_name))
                        for f_path, file_name, st in entries
                        if f_path == rom_dir and is_chd_file(Path(f_path, file_name))
                    ]
                    largest_chd = max(top_level_chds, key=lambda c: c[0], default=None)
                    ra_path = (
                        str(largest_chd[1])
                        if largest_chd
                        else f"{abs_fs_path}/{rom.fs_name}/*"
                    )
                    rom_ra_h = await RAHasherService().calculate_hash(
                        ra_platform,
                        ra_path,
                    )

            for f_path, file_name, st in entries:
                is_top_level = f_path == rom_dir
                rel_dir = f_path.relative_to(self.base_path)
                row = (
                    existing_by_key.get((str(rel_dir), file_name))
                    if existing_by_key is not None
                    else None
                )
                # An unchanged top-level file is still re-read when its level
                # changed, since the ROM-level hash spans every file in it.
                if (
                    row is not None
                    and not (is_top_level and top_level_changed)
                    and rom_file_unchanged(
                        row,
                        size=st.st_size,
                        mtime=st.st_mtime,
                        hashable=hashable_platform,
                    )
                ):
                    rom_files.append(row)
                    continue

                abs_file_path = Path(f_path, file_name)

                if hashable_platform:
                    try:
                        if is_top_level:
                            # Include this file in the main ROM hash calculation
                            crc_c, rom_crc_c, md5_h, rom_md5_h, sha1_h, rom_sha1_h = (
                                await asyncio.to_thread(
                                    self._calculate_rom_hashes,
                                    abs_file_path,
                                    rom_crc_c,
                                    rom_md5_h,
                                    rom_sha1_h,
                                )
                            )
                        else:
                            # Calculate individual file hash only
                            crc_c, _, md5_h, _, sha1_h, _ = await asyncio.to_thread(
                                self._calculate_rom_hashes,
                                abs_file_path,
                            )
                    except zlib.error:
                        crc_c = 0
                        md5_h = hashlib.md5(usedforsecurity=False)
                        sha1_h = hashlib.sha1(usedforsecurity=False)

                    file_hash = _make_file_hash(
                        crc_c,
                        md5_h,
                        sha1_h,
                        chd_sha1_hash=_chd_sha1_hash(abs_file_path),
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
                    rom_path=rel_dir,
                    file_name=file_name,
                    file_hash=file_hash,
                    file_size_bytes=st.st_size,
                    last_modified=st.st_mtime,
                )
                # Extract from every ROM file (base, updates and DLC in
                # subfolders), not just the top-level one.
                if (
                    abs_file_path.suffix.lower() not in ARCHIVE_READERS
                    and rom_file.category not in NON_BINARY_FILE_CATEGORIES
                ):
                    await _extract_title_id(rom_file)
                rom_files.append(rom_file)
        elif (
            existing_by_key is not None
            and (flat_row := existing_by_key.get((rel_roms_path, rom.fs_name)))
            is not None
            and await _flat_file_unchanged(flat_row, rom_dir, hashable_platform)
        ):
            rom_files.append(flat_row)
            top_level_changed = False
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
                    log.error(
                        f"Incomplete read of archive {rom_dir}: {e}. Hashing the "
                        "archive itself instead, which won't match a hash database."
                    )
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
        else:
            if hashable_platform:
                try:
                    crc_c, _, md5_h, _, sha1_h, _ = await asyncio.to_thread(
                        self._calculate_rom_hashes,
                        Path(abs_fs_path, rom.fs_name),
                    )
                except zlib.error:
                    crc_c = 0
                    md5_h = hashlib.md5(usedforsecurity=False)
                    sha1_h = hashlib.sha1(usedforsecurity=False)

                # A single-file ROM spans exactly one file, so its ROM-level
                # hashes are that file's hashes.
                rom_crc_c, rom_md5_h, rom_sha1_h = crc_c, md5_h, sha1_h

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
                    chd_sha1_hash=_chd_sha1_hash(rom_dir),
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
                rom_path=Path(rel_roms_path),
                file_name=rom.fs_name,
                file_hash=file_hash,
            )
            rom_files.append(rom_file)
            # Archives keep hashes only; sigil reads title ids from the ROM
            # binary itself.
            if rom_ext not in ARCHIVE_READERS:
                renamed_rom_fs_name = await _extract_title_id(rom_file)

        rom_title_id, rom_save_target, rom_save_target_layout = _rom_level_title_values(
            rom.platform_slug, sigil_extractions
        )

        if top_level_changed:
            crc_hash = crc32_to_hex(rom_crc_c) if rom_crc_c != DEFAULT_CRC_C else ""
            md5_hash = (
                rom_md5_h.hexdigest()
                if rom_md5_h and rom_md5_h.digest() != DEFAULT_MD5_H_DIGEST
                else ""
            )
            sha1_hash = (
                rom_sha1_h.hexdigest()
                if rom_sha1_h and rom_sha1_h.digest() != DEFAULT_SHA1_H_DIGEST
                else ""
            )
            ra_hash = rom_ra_h
        else:
            # Nothing was re-read at this level, so the stored identity stands.
            crc_hash = rom.crc_hash or ""
            md5_hash = rom.md5_hash or ""
            sha1_hash = rom.sha1_hash or ""
            ra_hash = rom.ra_hash or ""

        return ParsedRomFiles(
            rom_files=rom_files,
            crc_hash=crc_hash,
            md5_hash=md5_hash,
            sha1_hash=sha1_hash,
            ra_hash=ra_hash,
            top_level_changed=top_level_changed,
            title_id=rom_title_id,
            save_target=rom_save_target,
            save_target_layout=rom_save_target_layout,
            renamed_rom_fs_name=renamed_rom_fs_name,
        )

    def _calculate_rom_hashes(
        self,
        file_path: Path,
        rom_crc_c: int = 0,
        rom_md5_h: Any = None,
        rom_sha1_h: Any = None,
    ) -> tuple[int, int, Any, Any, Any, Any]:
        """Hash one file, optionally folding its bytes into ROM-level accumulators.

        A ROM-level hash spans every top-level file of a multi-file ROM, so it
        can only be built by feeding each file through a second set of hashers.
        Callers that don't need one pass no accumulators, because a second pass
        over a chunk costs as much as the first.
        """
        extension = Path(file_path).suffix.lower()
        try:
            file_type = detect_mime_type(file_path)

            crc_c = 0
            md5_h = hashlib.md5(usedforsecurity=False)
            sha1_h = hashlib.sha1(usedforsecurity=False)
            accumulate = rom_md5_h is not None and rom_sha1_h is not None

            def update_hashes(chunk: bytes | bytearray):
                nonlocal crc_c, rom_crc_c

                md5_h.update(chunk)
                sha1_h.update(chunk)
                crc_c = binascii.crc32(chunk, crc_c)

                if accumulate:
                    rom_md5_h.update(chunk)
                    rom_sha1_h.update(chunk)
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

        def build_rom(fs_name: str, *, flat: bool) -> FSRom:
            return FSRom(
                fs_name=fs_name,
                flat=flat,
                nested=not flat,
                files=[],
                crc_hash="",
                md5_hash="",
                sha1_hash="",
                ra_hash="",
            )

        # Built in one pass and sorted in place, so a platform holding tens of
        # thousands of entries never has two full copies of the list alive.
        fs_roms = [
            build_rom(rom, flat=True)
            for rom in self.exclude_single_files(fs_single_roms)
        ]
        fs_roms += [
            build_rom(rom, flat=False) for rom in self.exclude_multi_roms(fs_multi_roms)
        ]
        fs_roms.sort(key=lambda rom: rom["fs_name"])

        return fs_roms

    async def rename_fs_rom(self, old_name: str, new_name: str, fs_path: str) -> None:
        if new_name != old_name:
            file_path = f"{fs_path}/{new_name}"
            if await self.file_exists(file_path=file_path):
                raise RomAlreadyExistsException(new_name)

            await self.move_file_or_folder(
                f"{fs_path}/{old_name}", f"{fs_path}/{new_name}"
            )

    async def _embed_switch_title_id_in_name(
        self, rel_file_path: Path, title_id: str, title_version: int | None
    ) -> str | None:
        """Rename a Switch ROM file to embed ` [TITLEID][vVERSION]` before the
        extension.

        Args:
            rel_file_path: The file's path relative to the library root.
        Returns:
            The new file name, or None when the file was left untouched.
        """
        name = rel_file_path.name

        if switch.TITLE_ID_BRACKET_REGEX.search(name):
            log.debug(f"{name} already has an embedded title id, skipping rename")
            return None

        if not switch.TITLE_ID_REGEX.fullmatch(title_id):
            log.debug(f"Title id {title_id!r} is not a 16-hex value, skipping rename")
            return None

        version = title_version if title_version is not None else 0
        extension = compute_file_extension(name)
        new_name = (
            f"{compute_file_name_no_ext(name)} [{title_id.upper()}][v{version}]"
            f"{'.' + extension if extension else ''}"
        )

        try:
            await self.rename_fs_rom(name, new_name, rel_file_path.parent.as_posix())
        except RomAlreadyExistsException:
            log.warning(
                f"Cannot embed title id: target {new_name} already exists, skipping rename"
            )
            return None

        log.info(f"Embedded Switch title id: renamed {name} to {new_name}")
        return new_name

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
