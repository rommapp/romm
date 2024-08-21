import binascii
import hashlib
import os
import shutil
from pathlib import Path

from config import LIBRARY_BASE_PATH
from exceptions.fs_exceptions import (
    FirmwareAlreadyExistsException,
    FirmwareNotFoundException,
)
from fastapi import UploadFile
from logger.logger import log
from utils.filesystem import iter_files
from utils.hashing import crc32_to_hex

from .base_handler import FSHandler


class FSFirmwareHandler(FSHandler):
    def __init__(self) -> None:
        pass

    def remove_file(self, file_name: str, file_path: str):
        try:
            os.remove(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")

    def get_firmware(self, platform_fs_slug: str):
        """Gets all filesystem firmware for a platform

        Args:
            platform: platform where firmware belong
        Returns:
            list with all the filesystem firmware for a platform found in the LIBRARY_BASE_PATH
        """
        firmware_path = self.get_firmware_fs_structure(platform_fs_slug)
        firmware_file_path = f"{LIBRARY_BASE_PATH}/{firmware_path}"

        try:
            fs_firmware_files = [f for _, f in iter_files(firmware_file_path)]
        except IndexError as exc:
            raise FirmwareNotFoundException(platform_fs_slug) from exc

        return [f for f in self._exclude_files(fs_firmware_files, "single")]

    def get_firmware_file_size(self, firmware_path: str, file_name: str):
        files = [f"{LIBRARY_BASE_PATH}/{firmware_path}/{file_name}"]
        return sum([os.stat(file).st_size for file in files])

    def calculate_file_hashes(self, firmware_path: str, file_name: str):
        with open(f"{LIBRARY_BASE_PATH}/{firmware_path}/{file_name}", "rb") as f:
            crc_c = 0
            md5_h = hashlib.md5(usedforsecurity=False)
            sha1_h = hashlib.sha1(usedforsecurity=False)

            # Read in chunks to avoid memory issues
            while chunk := f.read(8192):
                md5_h.update(chunk)
                sha1_h.update(chunk)
                crc_c = binascii.crc32(chunk, crc_c)

            return {
                "crc_hash": crc32_to_hex(crc_c),
                "md5_hash": md5_h.hexdigest(),
                "sha1_hash": sha1_h.hexdigest(),
            }

    def file_exists(self, path: str, file_name: str):
        return bool(os.path.exists(f"{LIBRARY_BASE_PATH}/{path}/{file_name}"))

    def rename_file(self, old_name: str, new_name: str, file_path: str):
        if new_name != old_name:
            if self.file_exists(path=file_path, file_name=new_name):
                raise FirmwareAlreadyExistsException(new_name)

            os.rename(
                f"{LIBRARY_BASE_PATH}/{file_path}/{old_name}",
                f"{LIBRARY_BASE_PATH}/{file_path}/{new_name}",
            )

    def build_upload_file_path(self, fs_slug: str):
        file_path = self.get_firmware_fs_structure(fs_slug)
        return f"{LIBRARY_BASE_PATH}/{file_path}"

    def write_file(self, file: UploadFile, path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        log.info(f" - Uploading {file.filename}")
        file_location = os.path.join(path, file.filename)

        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)
