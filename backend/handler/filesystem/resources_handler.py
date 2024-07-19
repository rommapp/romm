import glob
import shutil
from pathlib import Path

import requests
from config import RESOURCES_BASE_PATH
from fastapi import HTTPException, status
from logger.logger import log
from models.collection import Collection
from models.rom import Rom
from PIL import Image
from urllib3.exceptions import ProtocolError

from .base_handler import CoverSize, FSHandler


class FSResourcesHandler(FSHandler):
    def __init__(self) -> None:
        pass

    @staticmethod
    def cover_exists(entity: Rom | Collection, size: CoverSize) -> bool:
        """Check if rom cover exists in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            size: size of the cover
        Returns
            True if cover exists in filesystem else False
        """
        matched_files = glob.glob(
            f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover/{size.value}.*"
        )
        return len(matched_files) > 0

    @staticmethod
    def resize_cover_to_small(cover_path: str) -> None:
        """Path of the cover image to resize"""
        cover = Image.open(cover_path)
        if cover.height >= 1000:
            ratio = 0.2
        else:
            ratio = 0.4
        small_width = int(cover.width * ratio)
        small_height = int(cover.height * ratio)
        small_size = (small_width, small_height)
        small_img = cover.resize(small_size)
        small_img.save(cover_path)

    def _store_cover(
        self, entity: Rom | Collection, url_cover: str, size: CoverSize
    ) -> None:
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            url_cover: url to get the cover
            size: size of the cover
        """
        cover_file = f"{size.value}.png"
        cover_path = f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"

        try:
            res = requests.get(
                url_cover,
                stream=True,
                timeout=120,
            )
        except requests.exceptions.ConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch cover at {url_cover}: {str(exc)}",
            ) from exc

        if res.status_code == 200:
            Path(cover_path).mkdir(parents=True, exist_ok=True)
            with open(f"{cover_path}/{cover_file}", "wb") as f:
                shutil.copyfileobj(res.raw, f)
            if size == CoverSize.SMALL:
                self.resize_cover_to_small(f"{cover_path}/{cover_file}")

    @staticmethod
    def _get_cover_path(entity: Rom | Collection, size: CoverSize) -> str:
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom file
            size: size of the cover
        """
        file_path = (
            f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover/{size.value}.*"
        )
        matched_files = glob.glob(file_path, recursive=True)
        return (
            matched_files[0].replace(RESOURCES_BASE_PATH, "") if matched_files else ""
        )

    def get_cover(
        self, entity: Rom | Collection | None, overwrite: bool, url_cover: str = ""
    ) -> tuple[str, str]:
        if not entity:
            return "", ""

        if (overwrite or not self.cover_exists(entity, CoverSize.SMALL)) and url_cover:
            self._store_cover(entity, url_cover, CoverSize.SMALL)
        path_cover_s = (
            self._get_cover_path(entity, CoverSize.SMALL)
            if self.cover_exists(entity, CoverSize.SMALL)
            else ""
        )

        if (overwrite or not self.cover_exists(entity, CoverSize.BIG)) and url_cover:
            self._store_cover(entity, url_cover, CoverSize.BIG)
        path_cover_l = (
            self._get_cover_path(entity, CoverSize.BIG)
            if self.cover_exists(entity, CoverSize.BIG)
            else ""
        )

        return path_cover_s, path_cover_l

    @staticmethod
    def remove_cover(entity: Rom | Collection | None):
        if not entity:
            return {"path_cover_s": "", "path_cover_l": ""}

        try:
            cover_path = f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"
            shutil.rmtree(cover_path)
        except FileNotFoundError:
            log.warning(
                f"Couldn't remove cover from '{entity.name or entity.id}' since '{cover_path}' doesn't exists."
            )

        return {"path_cover_s": "", "path_cover_l": ""}

    @staticmethod
    def build_artwork_path(entity: Rom | Collection | None, file_ext: str):
        if not entity:
            return "", "", ""

        path_cover_l = (
            f"{entity.fs_resources_path}/cover/{CoverSize.BIG.value}.{file_ext}"
        )
        path_cover_s = (
            f"{entity.fs_resources_path}/cover/{CoverSize.SMALL.value}.{file_ext}"
        )
        artwork_path = f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"
        Path(artwork_path).mkdir(parents=True, exist_ok=True)

        return path_cover_l, path_cover_s, artwork_path

    @staticmethod
    def _store_screenshot(rom: Rom, url: str, idx: int):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            url: url to get the screenshot
        """
        screenshot_file = f"{idx}.jpg"
        screenshot_path = f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}/screenshots"

        try:
            res = requests.get(url, stream=True, timeout=120)
        except requests.exceptions.ConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch screenshot at {url}: {str(exc)}",
            ) from exc

        if res.status_code == 200:
            Path(screenshot_path).mkdir(parents=True, exist_ok=True)
            with open(f"{screenshot_path}/{screenshot_file}", "wb") as f:
                try:
                    shutil.copyfileobj(res.raw, f)
                except ProtocolError:
                    log.warning(
                        f"Failure writing screenshot {url} to file (ProtocolError)"
                    )

    @staticmethod
    def _get_screenshot_path(rom: Rom, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            idx: index number of screenshot
        """
        return f"{rom.fs_resources_path}/screenshots/{idx}.jpg"

    def get_rom_screenshots(self, rom: Rom | None, url_screenshots: list) -> list[str]:
        if not rom:
            return []

        path_screenshots: list[str] = []
        for idx, url in enumerate(url_screenshots):
            self._store_screenshot(rom, url, idx)
            path_screenshots.append(self._get_screenshot_path(rom, str(idx)))

        return path_screenshots
