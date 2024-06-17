import os
import shutil
from pathlib import Path

import requests
from config import RESOURCES_BASE_PATH
from fastapi import HTTPException, status
from logger.logger import log
from urllib3.exceptions import ProtocolError

from .base_handler import CoverSize, FSHandler


class FSResourcesHandler(FSHandler):
    def __init__(self) -> None:
        pass

    @staticmethod
    def _cover_exists(fs_slug: str, rom_id: int, size: CoverSize):
        """Check if rom cover exists in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            size: size of the cover
        Returns
            True if cover exists in filesystem else False
        """
        return bool(
            os.path.exists(
                f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_id}/cover/{size.value}.png"
            )
        )

    def _store_cover(self, fs_slug: str, rom_id: int, url_cover: str, size: CoverSize):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            url_cover: url to get the cover
            size: size of the cover
        """
        cover_file = f"{size.value}.png"
        cover_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_id}/cover"

        try:
            res = requests.get(
                (
                    url_cover.replace("t_thumb", "t_cover_small").replace(
                        "t_cover_big", "t_cover_small"
                    )
                    if size.value == CoverSize.SMALL.value
                    else url_cover.replace("t_thumb", "t_1080p").replace(
                        "t_cover_big", "t_1080p"
                    )
                ),
                stream=True,
                timeout=120,
            )
        except requests.exceptions.ConnectionError as exc:
            log.critical("Connection error: can't connect to IGDB")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection.",
            ) from exc

        if res.status_code == 200:
            Path(cover_path).mkdir(parents=True, exist_ok=True)
            with open(f"{cover_path}/{cover_file}", "wb") as f:
                shutil.copyfileobj(res.raw, f)

    @staticmethod
    def _get_cover_path(fs_slug: str, rom_id: int, size: CoverSize):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom file
            size: size of the cover
        """
        return f"{fs_slug}/{rom_id}/cover/{size.value}.png"

    def get_rom_cover(
        self, overwrite: bool, platform_fs_slug: str, rom_id: int, url_cover: str = ""
    ) -> tuple[str, str]:
        if (
            overwrite
            or not self._cover_exists(platform_fs_slug, rom_id, CoverSize.SMALL)
        ) and url_cover:
            self._store_cover(platform_fs_slug, rom_id, url_cover, CoverSize.SMALL)
        path_cover_s = (
            self._get_cover_path(platform_fs_slug, rom_id, CoverSize.SMALL)
            if self._cover_exists(platform_fs_slug, rom_id, CoverSize.SMALL)
            else ""
        )

        if (
            overwrite or not self._cover_exists(platform_fs_slug, rom_id, CoverSize.BIG)
        ) and url_cover:
            self._store_cover(platform_fs_slug, rom_id, url_cover, CoverSize.BIG)
        path_cover_l = (
            self._get_cover_path(platform_fs_slug, rom_id, CoverSize.BIG)
            if self._cover_exists(platform_fs_slug, rom_id, CoverSize.BIG)
            else ""
        )

        return path_cover_s, path_cover_l

    @staticmethod
    def remove_cover(
        rom_id: int,
        platform_fs_slug: str,
    ):
        try:
            shutil.rmtree(
                os.path.join(
                    RESOURCES_BASE_PATH, platform_fs_slug, str(rom_id), "cover"
                )
            )
        except FileNotFoundError:
            log.warning(f"Couldn't remove {rom_id} cover")
        return {"path_cover_s": "", "path_cover_l": ""}

    @staticmethod
    def build_artwork_path(rom_id: int, platform_fs_slug: str, file_ext: str):
        path_cover_l = (
            f"{platform_fs_slug}/{rom_id}/cover/{CoverSize.BIG.value}.{file_ext}"
        )
        path_cover_s = (
            f"{platform_fs_slug}/{rom_id}/cover/{CoverSize.SMALL.value}.{file_ext}"
        )
        artwork_path = f"{RESOURCES_BASE_PATH}/{platform_fs_slug}/{rom_id}/cover"
        Path(artwork_path).mkdir(parents=True, exist_ok=True)
        return path_cover_l, path_cover_s, artwork_path

    @staticmethod
    def _store_screenshot(fs_slug: str, rom_id: int, url: str, idx: int):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            url: url to get the screenshot
        """
        screenshot_file = f"{idx}.jpg"
        screenshot_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_id}/screenshots"

        try:
            res = requests.get(url, stream=True, timeout=120)
        except requests.exceptions.ConnectionError as exc:
            log.critical("Connection error: can't connect to IGDB")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection.",
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
    def _get_screenshot_path(fs_slug: str, rom_id: int, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            idx: index number of screenshot
        """
        return f"{fs_slug}/{rom_id}/screenshots/{idx}.jpg"

    def get_rom_screenshots(
        self, platform_fs_slug: str, rom_id: int, url_screenshots: list
    ) -> list[str]:
        path_screenshots: list[str] = []
        for idx, url in enumerate(url_screenshots):
            self._store_screenshot(platform_fs_slug, rom_id, url, idx)
            path_screenshots.append(
                self._get_screenshot_path(platform_fs_slug, rom_id, str(idx))
            )
        return path_screenshots
