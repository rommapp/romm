import binascii
import hashlib

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import FirmwareNotFoundException
from utils.hashing import crc32_to_hex
from utils.structure_parser import LibraryStructure

from .base_handler import FSHandler


class FSFirmwareHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LIBRARY_BASE_PATH)

    def get_firmware_structure(self) -> LibraryStructure:
        cnfg = cm.get_config()
        return LibraryStructure(cnfg.FIRMWARE_STRUCTURE, "firmware")

    async def get_firmware(self, platform_fs_slug: str):
        """Gets all filesystem firmware for a platform

        Args:
            platform: platform where firmware belong
        Returns:
            list with all the filesystem firmware for a platform
        """
        firmware_path = self.get_firmware_structure().resolve_path(
            platform=platform_fs_slug
        )
        try:
            fs_firmware_files = await self.list_files(path=firmware_path)
        except FileNotFoundError as e:
            raise FirmwareNotFoundException(
                f"Firmware not found for platform {platform_fs_slug}"
            ) from e

        return [f for f in self.exclude_single_files(fs_firmware_files)]

    async def calculate_file_hashes(self, firmware_path: str, file_name: str):
        file_path = f"{firmware_path}/{file_name}"
        async with await self.stream_file(file_path=file_path) as f:
            crc_c = 0
            md5_h = hashlib.md5(usedforsecurity=False)
            sha1_h = hashlib.sha1(usedforsecurity=False)

            # Read in chunks to avoid memory issues
            while chunk := await f.read(8192):
                md5_h.update(chunk)
                sha1_h.update(chunk)
                crc_c = binascii.crc32(chunk, crc_c)

            return {
                "crc_hash": crc32_to_hex(crc_c),
                "md5_hash": md5_h.hexdigest(),
                "sha1_hash": sha1_h.hexdigest(),
            }
