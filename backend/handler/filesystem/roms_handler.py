import binascii
import bz2
import gzip
import hashlib
import os
import re
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import magic
import py7zr
import rarfile
from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import RomAlreadyExistsException, RomsNotFoundException
from models.platform import Platform
from utils.filesystem import iter_directories, iter_files

from .base_handler import (
    LANGUAGES_BY_SHORTCODE,
    LANGUAGES_NAME_KEYS,
    REGIONS_BY_SHORTCODE,
    REGIONS_NAME_KEYS,
    TAG_REGEX,
    FSHandler,
)

# list of known compressed file MIME types
COMPRESSED_MIME_TYPES: Final = [
    "application/zip",
    "application/x-gzip",
    "application/x-7z-compressed",
    "application/x-bzip2",
    "application/x-rar-compressed",
    "application/x-tar",
    "application/x-wii-rom",
    "application/x-gamecube-rom",
]

# list of known file extensions that are compressed
COMPRESSED_FILE_EXTENSIONS = [
    ".zip",
    ".gz",
    ".7z",
    ".bz2",
    ".rar",
    ".tar",
    ".gcz",
    ".iso",
    ".gcm",
    ".chd",
    ".pkg",
    ".xci",
    ".nsp",
    ".pck",
]

FILE_READ_CHUNK_SIZE = 1024 * 8


def is_compressed_file(file_path: str) -> bool:
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)

    return file_type in COMPRESSED_MIME_TYPES or file_path.endswith(
        tuple(COMPRESSED_FILE_EXTENSIONS)
    )


class FSRomsHandler(FSHandler):
    def __init__(self) -> None:
        pass

    def remove_file(self, file_name: str, file_path: str):
        try:
            os.remove(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")

    def parse_tags(self, file_name: str) -> tuple:
        rev = ""
        regs = []
        langs = []
        other_tags = []
        tags = [tag[0] or tag[1] for tag in TAG_REGEX.findall(file_name)]
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

    def _exclude_multi_roms(self, roms) -> list[str]:
        excluded_names = cm.get_config().EXCLUDED_MULTI_FILES
        filtered_files: list = []

        for rom in roms:
            if rom in excluded_names:
                filtered_files.append(rom)

        return [f for f in roms if f not in filtered_files]

    def _calculate_rom_hashes(self, file_path: Path) -> dict[str, str]:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        extension = Path(file_path).suffix.lower()

        crc_c = 0
        md5_h = hashlib.md5(usedforsecurity=False)
        sha1_h = hashlib.sha1(usedforsecurity=False)

        if extension == ".zip" or file_type == "application/zip":
            with zipfile.ZipFile(file_path, "r") as z:
                for file in z.namelist():
                    with z.open(file, "r") as f:
                        while chunk := f.read(FILE_READ_CHUNK_SIZE):
                            md5_h.update(chunk)
                            sha1_h.update(chunk)
                            crc_c = binascii.crc32(chunk, crc_c)

        elif extension == ".gz" or file_type == "application/x-gzip":
            with gzip.open(file_path, "rb") as f:
                while chunk := f.read(FILE_READ_CHUNK_SIZE):
                    md5_h.update(chunk)
                    sha1_h.update(chunk)
                    crc_c = binascii.crc32(chunk, crc_c)

        elif extension == ".7z" or file_type == "application/x-7z-compressed":
            with py7zr.SevenZipFile(file_path, "r") as f:
                for _name, bio in f.readall().items():
                    while chunk := bio.read(FILE_READ_CHUNK_SIZE):
                        md5_h.update(chunk)
                        sha1_h.update(chunk)
                        crc_c = binascii.crc32(chunk, crc_c)

        elif extension == ".bz2" or file_type == "application/x-bzip2":
            with bz2.BZ2File(file_path, "rb") as f:
                while chunk := f.read(FILE_READ_CHUNK_SIZE):
                    md5_h.update(chunk)
                    sha1_h.update(chunk)
                    crc_c = binascii.crc32(chunk, crc_c)

        elif extension == ".rar" or file_type == "application/x-rar-compressed":
            with rarfile.RarFile(file_path, "r") as f:
                for file in f.namelist():
                    with f.open(file, "r") as f:
                        while chunk := f.read(FILE_READ_CHUNK_SIZE):
                            md5_h.update(chunk)
                            sha1_h.update(chunk)
                            crc_c = binascii.crc32(chunk, crc_c)

        elif extension == ".tar" or file_type == "application/x-tar":
            with tarfile.open(file_path, "r") as f:
                for member in f.getmembers():
                    with f.extractfile(member) as ef:
                        while chunk := ef.read(FILE_READ_CHUNK_SIZE):
                            md5_h.update(chunk)
                            sha1_h.update(chunk)
                            crc_c = binascii.crc32(chunk, crc_c)

        else:
            with open(file_path, "rb") as f:
                # Read in chunks to avoid memory issues
                while chunk := f.read(FILE_READ_CHUNK_SIZE):
                    md5_h.update(chunk)
                    sha1_h.update(chunk)
                    crc_c = binascii.crc32(chunk, crc_c)

        return {
            "crc_hash": (crc_c & 0xFFFFFFFF).to_bytes(4, byteorder="big").hex(),
            "md5_hash": md5_h.hexdigest(),
            "sha1_hash": sha1_h.hexdigest(),
        }

    def get_rom_files(self, rom: str, roms_path: str) -> list[str]:
        rom_files: list[str] = []

        # Check if rom is a multi-part rom
        if os.path.isdir(f"{roms_path}/{rom}"):
            multi_files = os.listdir(f"{roms_path}/{rom}")
            for file in multi_files:
                path = Path(roms_path, rom, file)
                rom_files.append(
                    {
                        "filename": file,
                        "size": os.stat(path).st_size,
                        **self._calculate_rom_hashes(path),
                    }
                )
        else:
            path = Path(roms_path, rom)
            rom_files.append(
                {
                    "filename": rom,
                    "size": os.stat(path).st_size,
                    **self._calculate_rom_hashes(path),
                }
            )

        return rom_files

    def get_roms(self, platform: Platform):
        """Gets all filesystem roms for a platform

        Args:
            platform: platform where roms belong
        Returns:
            list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH
        """
        roms_path = self.get_roms_fs_structure(platform.fs_slug)
        roms_file_path = f"{LIBRARY_BASE_PATH}/{roms_path}"

        try:
            fs_single_roms = [f for _, f in iter_files(roms_file_path)]
        except IndexError as exc:
            raise RomsNotFoundException(platform.fs_slug) from exc

        try:
            fs_multi_roms = [d for _, d in iter_directories(roms_file_path)]
        except IndexError as exc:
            raise RomsNotFoundException(platform.fs_slug) from exc

        fs_roms: list[dict] = [
            {"multi": False, "file_name": rom}
            for rom in self._exclude_files(fs_single_roms, "single")
        ] + [
            {"multi": True, "file_name": rom}
            for rom in self._exclude_multi_roms(fs_multi_roms)
        ]

        return [
            dict(
                rom,
                files=self.get_rom_files(rom["file_name"], roms_file_path),
            )
            for rom in fs_roms
        ]

    def get_rom_file_size(
        self,
        roms_path: str,
        file_name: str,
        multi: bool,
        multi_files: list[str] | None = None,
    ):
        if multi_files is None:
            multi_files = []

        files = (
            [f"{LIBRARY_BASE_PATH}/{roms_path}/{file_name}"]
            if not multi
            else [
                f"{LIBRARY_BASE_PATH}/{roms_path}/{file_name}/{file}"
                for file in multi_files
            ]
        )
        return sum([os.stat(file).st_size for file in files])

    def file_exists(self, path: str, file_name: str):
        """Check if file exists in filesystem

        Args:
            path: path to file
            file_name: name of file
        Returns
            True if file exists in filesystem else False
        """
        return bool(os.path.exists(f"{LIBRARY_BASE_PATH}/{path}/{file_name}"))

    def rename_file(self, old_name: str, new_name: str, file_path: str):
        if new_name != old_name:
            if self.file_exists(path=file_path, file_name=new_name):
                raise RomAlreadyExistsException(new_name)

            os.rename(
                f"{LIBRARY_BASE_PATH}/{file_path}/{old_name}",
                f"{LIBRARY_BASE_PATH}/{file_path}/{new_name}",
            )

    def build_upload_file_path(self, fs_slug: str):
        file_path = self.get_roms_fs_structure(fs_slug)
        return f"{LIBRARY_BASE_PATH}/{file_path}"
