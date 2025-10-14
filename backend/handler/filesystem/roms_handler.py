import binascii
import bz2
import fnmatch
import hashlib
import os
import re
import tarfile
import zipfile
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import IO, Any, Final, Literal, TypedDict

import magic
import zipfile_inflate64  # trunk-ignore(ruff/F401): Patches zipfile to support Enhanced Deflate

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    RomAlreadyExistsException,
    RomsNotFoundException,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from utils.archive_7zip import process_file_7z
from utils.filesystem import iter_files
from utils.hashing import crc32_to_hex
from utils.structure_parser import LibraryStructure

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

# Known file extensions that are compressed
COMPRESSED_FILE_EXTENSIONS = frozenset(
    (
        ".7z",
        ".bz2",
        ".gz",
        ".tar",
        ".zip",
    )
)

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


def is_compressed_file(file_path: str) -> bool:
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)

    return file_type in COMPRESSED_MIME_TYPES or file_path.endswith(
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


def category_matches(category: str, path_parts: list[str]):
    return category in path_parts or f"{category}s" in path_parts


DEFAULT_CRC_C = 0
DEFAULT_MD5_H_DIGEST = hashlib.md5(usedforsecurity=False).digest()
DEFAULT_SHA1_H_DIGEST = hashlib.sha1(usedforsecurity=False).digest()


class FSRomsHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LIBRARY_BASE_PATH)

    def get_roms_structure(self) -> LibraryStructure:
        """Get the filesystem path for ROMs of a platform based on structure."""
        cnfg = cm.get_config()
        return LibraryStructure(cnfg.LIBRARY_STRUCTURE, "roms")

    def _find_platform_path(
        self, structure: LibraryStructure, platform_slug: str
    ) -> str:
        """Find the actual path to a platform by searching the filesystem.

        This is needed for structures with custom macros like {region}.
        """
        import os

        # Get the platforms directory
        platforms_dir = structure.get_platforms_directory()

        # Search for the platform in all subdirectories
        for root, dirs, _ in os.walk(os.path.join(self.base_path, platforms_dir)):
            # Check if this directory contains the platform we're looking for
            if platform_slug in dirs:
                # Found the platform, return the relative path
                rel_path = os.path.relpath(root, self.base_path)
                return os.path.join(rel_path, platform_slug)

        # If not found, fall back to the old method (this shouldn't happen)
        return structure.resolve_path(platform=platform_slug)

    def parse_tags(self, fs_name: str) -> tuple:
        rev = ""
        regs = []
        langs = []
        other_tags = []
        tags = [tag[0] or tag[1] for tag in TAG_REGEX.findall(fs_name)]
        tags = [tag for subtags in tags for tag in subtags.split(",")]
        tags = [tag.strip() for tag in tags]

        for tag in tags:
            if tag.lower() in REGIONS_BY_SHORTCODE.keys():
                regs.append(REGIONS_BY_SHORTCODE[tag.lower()])
                continue

            if tag.lower() in REGIONS_NAME_KEYS:
                regs.append(tag)
                continue

            if tag.lower() in LANGUAGES_BY_SHORTCODE.keys():
                langs.append(LANGUAGES_BY_SHORTCODE[tag.lower()])
                continue

            if tag.lower() in LANGUAGES_NAME_KEYS:
                langs.append(tag)
                continue

            if "reg" in tag.lower():
                match = re.match(r"^reg[\s|-](.*)$", tag, re.IGNORECASE)
                if match:
                    regs.append(
                        REGIONS_BY_SHORTCODE[match.group(1).lower()]
                        if match.group(1).lower() in REGIONS_BY_SHORTCODE.keys()
                        else match.group(1)
                    )
                    continue

            if "rev" in tag.lower():
                match = re.match(r"^rev[\s|-](.*)$", tag, re.IGNORECASE)
                if match:
                    rev = match.group(1)
                    continue

            other_tags.append(tag)
        return regs, rev, langs, other_tags

    def exclude_multi_roms(self, roms: list[str]) -> list[str]:
        excluded_names = cm.get_config().EXCLUDED_MULTI_FILES
        filtered_files: list = []

        for rom in roms:
            if rom in excluded_names:
                filtered_files.append(rom)

        return [f for f in roms if f not in filtered_files]

    def _build_rom_file(
        self, rom_path: Path, file_name: str, file_hash: FileHash
    ) -> RomFile:
        # Absolute path to roms
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
            file_name=file_name,
            file_path=str(rom_path),
            file_size_bytes=os.stat(abs_file_path).st_size,
            last_modified=os.path.getmtime(abs_file_path),
            category=matching_category,
            crc_hash=file_hash["crc_hash"],
            md5_hash=file_hash["md5_hash"],
            sha1_hash=file_hash["sha1_hash"],
        )

    async def get_rom_files(self, rom: Rom) -> tuple[list[RomFile], str, str, str, str]:
        from adapters.services.rahasher import RAHasherService
        from handler.metadata import meta_ra_handler

        rel_roms_path = self.get_roms_structure().resolve_path(
            platform=rom.platform.fs_slug
        )  # Relative path to roms
        abs_fs_path = self.validate_path(rel_roms_path)  # Absolute path to roms
        rom_files: list[RomFile] = []

        # Skip hashing games for platforms that don't have a hash database
        hashable_platform = rom.platform_slug not in NON_HASHABLE_PLATFORMS

        excluded_file_names = cm.get_config().EXCLUDED_MULTI_PARTS_FILES
        excluded_file_exts = cm.get_config().EXCLUDED_MULTI_PARTS_EXT

        rom_crc_c = 0
        rom_md5_h = hashlib.md5(usedforsecurity=False)
        rom_sha1_h = hashlib.sha1(usedforsecurity=False)
        rom_ra_h = ""

        # Check if rom is a multi-part rom
        if os.path.isdir(f"{abs_fs_path}/{rom.fs_name}"):
            # Calculate the RA hash if the platform has a slug that matches a known RA slug
            ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
            if ra_platform and ra_platform["ra_id"]:
                rom_ra_h = await RAHasherService().calculate_hash(
                    ra_platform["ra_id"],
                    f"{abs_fs_path}/{rom.fs_name}/*",
                )

            for f_path, file_name in iter_files(
                f"{abs_fs_path}/{rom.fs_name}", recursive=True
            ):
                # Check if file is excluded
                ext = self.parse_file_extension(file_name)
                if ext in excluded_file_exts:
                    continue

                if any(
                    file_name == exc_name or fnmatch.fnmatch(file_name, exc_name)
                    for exc_name in excluded_file_names
                ):
                    continue

                if hashable_platform:
                    try:
                        crc_c, rom_crc_c, md5_h, rom_md5_h, sha1_h, rom_sha1_h = (
                            self._calculate_rom_hashes(
                                Path(f_path, file_name),
                                rom_crc_c,
                                rom_md5_h,
                                rom_sha1_h,
                            )
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
                    )
                else:
                    file_hash = FileHash(
                        crc_hash="",
                        md5_hash="",
                        sha1_hash="",
                    )

                rom_files.append(
                    self._build_rom_file(
                        f_path.relative_to(self.base_path),
                        file_name,
                        file_hash,
                    )
                )
        elif hashable_platform:
            try:
                crc_c, rom_crc_c, md5_h, rom_md5_h, sha1_h, rom_sha1_h = (
                    self._calculate_rom_hashes(
                        Path(abs_fs_path, rom.fs_name), rom_crc_c, rom_md5_h, rom_sha1_h
                    )
                )
            except zlib.error:
                crc_c = 0
                md5_h = hashlib.md5(usedforsecurity=False)
                sha1_h = hashlib.sha1(usedforsecurity=False)

            # Calculate the RA hash if the platform has a slug that matches a known RA slug
            ra_platform = meta_ra_handler.get_platform(rom.platform_slug)
            if ra_platform and ra_platform["ra_id"]:
                rom_ra_h = await RAHasherService().calculate_hash(
                    ra_platform["ra_id"],
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
            )
            rom_files.append(
                self._build_rom_file(Path(rel_roms_path), rom.fs_name, file_hash)
            )
        else:
            file_hash = FileHash(
                crc_hash="",
                md5_hash="",
                sha1_hash="",
            )
            rom_files.append(
                self._build_rom_file(Path(rel_roms_path), rom.fs_name, file_hash)
            )

        return (
            rom_files,
            crc32_to_hex(rom_crc_c) if rom_crc_c != DEFAULT_CRC_C else "",
            rom_md5_h.hexdigest() if rom_md5_h.digest() != DEFAULT_MD5_H_DIGEST else "",
            (
                rom_sha1_h.hexdigest()
                if rom_sha1_h.digest() != DEFAULT_SHA1_H_DIGEST
                else ""
            ),
            rom_ra_h,
        )

    def _calculate_rom_hashes(
        self,
        file_path: Path,
        rom_crc_c: int,
        rom_md5_h: Any,
        rom_sha1_h: Any,
    ) -> tuple[int, int, Any, Any, Any, Any]:
        extension = Path(file_path).suffix.lower()
        mime = magic.Magic(mime=True)
        try:
            file_type = mime.from_file(file_path)

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

    async def list_directory_contents(self, path: str) -> list[str]:
        """List all items (files and directories) in a directory."""
        if not path:
            raise ValueError("Directory cannot be empty")

        # Validate and normalize path
        full_path = self.validate_path(path)

        # Async thread-safe directory listing
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            if not full_path.exists() or not full_path.is_dir():
                raise FileNotFoundError(f"Directory not found: {full_path}")

            return [item.name for item in full_path.iterdir()]

    async def get_roms(self, platform: Platform) -> list[FSRom]:
        """Gets all filesystem roms for a platform"""
        fs_roms: list[FSRom] = []

        try:
            structure = self.get_roms_structure()
            # For structures with custom macros, we need to find the region
            # by looking for the platform in the filesystem
            rel_roms_path = self._find_platform_path(structure, platform.fs_slug)

            all_items = await self.list_directory_contents(path=rel_roms_path)
            for item in all_items:
                item_path = os.path.join(rel_roms_path, item)
                is_directory = os.path.isdir(item_path)
                fs_roms.append(
                    FSRom(
                        {
                            "fs_name": item,
                            "flat": not is_directory,
                            "nested": is_directory,
                            "files": [],
                            "crc_hash": "",
                            "md5_hash": "",
                            "sha1_hash": "",
                            "ra_hash": "",
                        }
                    )
                )
        except FileNotFoundError as e:
            raise RomsNotFoundException(platform=platform.fs_slug) from e

        return sorted(fs_roms, key=lambda rom: rom["fs_name"])

    async def rename_fs_rom(self, old_name: str, new_name: str, fs_path: str) -> None:
        if new_name != old_name:
            file_path = f"{fs_path}/{new_name}"
            if await self.file_exists(file_path=file_path):
                raise RomAlreadyExistsException(new_name)

            await self.move_file_or_folder(
                f"{fs_path}/{old_name}", f"{fs_path}/{new_name}"
            )
