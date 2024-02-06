import os
import shutil
from pathlib import Path
from urllib.parse import quote

import requests
from config import RESOURCES_BASE_PATH
from handler.fs_handler import (
    DEFAULT_HEIGHT_COVER_L,
    DEFAULT_HEIGHT_COVER_S,
    DEFAULT_WIDTH_COVER_L,
    DEFAULT_WIDTH_COVER_S,
    CoverSize,
    FSHandler,
)
from PIL import Image


class FSResourceHandler(FSHandler):
    def __init__(self) -> None:
        pass

    def _cover_exists(self, fs_slug: str, rom_name: str, size: CoverSize):
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
                f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover/{size.value}.png"
            )
        )

    def resize_cover(self, cover_path: str, size: CoverSize = CoverSize.BIG) -> None:
        """Resizes the cover image to the standard size

        Args:
            cover_path: path where the original cover were stored
            size: size of the cover
        """
        cover = Image.open(cover_path)
        if cover.size[1] > DEFAULT_HEIGHT_COVER_L:
            if size == CoverSize.BIG:
                big_dimensions = (DEFAULT_WIDTH_COVER_L, DEFAULT_HEIGHT_COVER_L)
                background = Image.new("RGBA", big_dimensions, (0, 0, 0, 0))
                cover.thumbnail(big_dimensions)
                offset = (
                    int(round(((DEFAULT_WIDTH_COVER_L - cover.size[0]) / 2), 0)),
                    0,
                )
            elif size == CoverSize.SMALL:
                small_dimensions = (DEFAULT_WIDTH_COVER_S, DEFAULT_HEIGHT_COVER_S)
                background = Image.new("RGBA", small_dimensions, (0, 0, 0, 0))
                cover.thumbnail(small_dimensions)
                offset = (
                    int(round(((DEFAULT_WIDTH_COVER_S - cover.size[0]) / 2), 0)),
                    0,
                )
            else:
                return
            background.paste(cover, offset)
            background.save(cover_path)

    def _store_cover(
        self, fs_slug: str, rom_name: str, url_cover: str, size: CoverSize
    ):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            url_cover: url to get the cover
            size: size of the cover
        """
        cover_file = f"{size.value}.png"
        cover_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover"
        res = requests.get(
            url_cover.replace("t_thumb", f"t_cover_{size.value}"),
            stream=True,
            timeout=120,
        )
        if res.status_code == 200:
            Path(cover_path).mkdir(parents=True, exist_ok=True)
            with open(f"{cover_path}/{cover_file}", "wb") as f:
                shutil.copyfileobj(res.raw, f)
            self.resize_cover(f"{cover_path}/{cover_file}", size)

    def _get_cover_path(self, fs_slug: str, rom_name: str, size: CoverSize):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom file
            size: size of the cover
        """
        return f"{fs_slug}/{rom_name}/cover/{size.value}.png"

    def get_rom_cover(
        self, overwrite: bool, platform_fs_slug: str, rom_name: str, url_cover: str = ""
    ) -> dict:
        q_rom_name = quote(rom_name)
        if (
            overwrite
            or not self._cover_exists(platform_fs_slug, rom_name, CoverSize.SMALL)
        ) and url_cover:
            self._store_cover(platform_fs_slug, rom_name, url_cover, CoverSize.SMALL)
        path_cover_s = (
            self._get_cover_path(platform_fs_slug, q_rom_name, CoverSize.SMALL)
            if self._cover_exists(platform_fs_slug, rom_name, CoverSize.SMALL)
            else ""
        )

        if (
            overwrite
            or not self._cover_exists(platform_fs_slug, rom_name, CoverSize.BIG)
        ) and url_cover:
            self._store_cover(platform_fs_slug, rom_name, url_cover, CoverSize.BIG)
        path_cover_l = (
            self._get_cover_path(platform_fs_slug, q_rom_name, CoverSize.BIG)
            if self._cover_exists(platform_fs_slug, rom_name, CoverSize.BIG)
            else ""
        )

        return {
            "path_cover_s": path_cover_s,
            "path_cover_l": path_cover_l,
        }

    def build_artwork_path(self, rom_name: str, fs_slug: str, file_ext: str):
        q_rom_name = quote(rom_name)

        path_cover_l = f"{fs_slug}/{q_rom_name}/cover/{CoverSize.BIG.value}.{file_ext}"
        path_cover_s = f"{fs_slug}/{q_rom_name}/cover/{CoverSize.SMALL.value}.{file_ext}"
        artwork_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover"
        Path(artwork_path).mkdir(parents=True, exist_ok=True)
        return path_cover_l, path_cover_s, artwork_path
    
    def _store_screenshot(self, fs_slug: str, rom_name: str, url: str, idx: int):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            url: url to get the screenshot
        """
        screenshot_file = f"{idx}.jpg"
        screenshot_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/screenshots"
        res = requests.get(url, stream=True, timeout=120)
        if res.status_code == 200:
            Path(screenshot_path).mkdir(parents=True, exist_ok=True)
            with open(f"{screenshot_path}/{screenshot_file}", "wb") as f:
                shutil.copyfileobj(res.raw, f)

    def _get_screenshot_path(self, fs_slug: str, rom_name: str, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            idx: index number of screenshot
        """
        return f"{fs_slug}/{rom_name}/screenshots/{idx}.jpg"

    def get_rom_screenshots(
        self, platform_fs_slug: str, rom_name: str, url_screenshots: list
    ) -> dict:
        q_rom_name = quote(rom_name)

        path_screenshots: list[str] = []
        for idx, url in enumerate(url_screenshots):
            self._store_screenshot(platform_fs_slug, rom_name, url, idx)
            path_screenshots.append(
                self._get_screenshot_path(platform_fs_slug, q_rom_name, str(idx))
            )

        return {"path_screenshots": path_screenshots}
