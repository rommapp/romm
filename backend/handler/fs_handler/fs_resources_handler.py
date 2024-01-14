import datetime
import os
import shutil
from pathlib import Path
from urllib.parse import quote

import requests
from config import (
    DEFAULT_PATH_COVER_L,
    DEFAULT_PATH_COVER_S,
    DEFAULT_URL_COVER_L,
    DEFAULT_URL_COVER_S,
)
from handler.fs_handler import (
    DEFAULT_HEIGHT_COVER_L,
    DEFAULT_HEIGHT_COVER_S,
    DEFAULT_WIDTH_COVER_L,
    DEFAULT_WIDTH_COVER_S,
    RESOURCES_BASE_PATH,
    CoverSize,
)
from handler.fs_handler.fs_handler import FSHandler
from PIL import Image


class FSResourceHandler(FSHandler):
    def __init__(self) -> None:
        pass

    @staticmethod
    def _cover_exists(fs_slug: str, rom_name: str, size: CoverSize):
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

    @staticmethod
    def _resize_cover(cover_path: str, size: CoverSize) -> None:
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

    @staticmethod
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
            self._resize_cover(f"{cover_path}/{cover_file}", size)

    @staticmethod
    def _get_cover_path(fs_slug: str, rom_name: str, size: CoverSize):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom file
            size: size of the cover
        """
        strtime = str(datetime.datetime.now().timestamp())
        return f"{fs_slug}/{rom_name}/cover/{size.value}.png?timestamp={strtime}"

    def get_rom_cover(
        self, overwrite: bool, platform_fs_slug: str, rom_name: str, url_cover: str = ""
    ) -> dict:
        q_rom_name = quote(rom_name)
        if (
            overwrite or not self._cover_exists(platform_fs_slug, rom_name, CoverSize.SMALL)
        ) and url_cover:
            self._store_cover(platform_fs_slug, rom_name, url_cover, CoverSize.SMALL)
        path_cover_s = (
            self._get_cover_path(platform_fs_slug, q_rom_name, CoverSize.SMALL)
            if self._cover_exists(platform_fs_slug, rom_name, CoverSize.SMALL)
            else DEFAULT_PATH_COVER_S
        )

        if (
            overwrite or not self._cover_exists(platform_fs_slug, rom_name, CoverSize.BIG)
        ) and url_cover:
            self._store_cover(platform_fs_slug, rom_name, url_cover, CoverSize.BIG)
        path_cover_l = (
            self._get_cover_path(platform_fs_slug, q_rom_name, CoverSize.BIG)
            if self._cover_exists(platform_fs_slug, rom_name, CoverSize.BIG)
            else DEFAULT_PATH_COVER_L
        )

        return {
            "path_cover_s": path_cover_s,
            "path_cover_l": path_cover_l,
        }

    def store_default_resources(self):
        """Store default cover resources in the filesystem"""
        defaul_covers = [
            {"url": DEFAULT_URL_COVER_L, "size": CoverSize.BIG},
            {"url": DEFAULT_URL_COVER_S, "size": CoverSize.SMALL},
        ]
        for cover in defaul_covers:
            if not self._cover_exists("default", "default", cover["size"]):
                self._store_cover("default", "default", cover["url"], cover["size"])

    @staticmethod
    def build_artwork_path(rom_name: str, fs_slug: str, file_ext: str):
        q_rom_name = quote(rom_name)
        strtime = str(datetime.datetime.now().timestamp())

        path_cover_l = f"{fs_slug}/{q_rom_name}/cover/{CoverSize.BIG.value}.{file_ext}?timestamp={strtime}"
        path_cover_s = f"{fs_slug}/{q_rom_name}/cover/{CoverSize.SMALL.value}.{file_ext}?timestamp={strtime}"
        artwork_path = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/cover"
        Path(artwork_path).mkdir(parents=True, exist_ok=True)
        return path_cover_l, path_cover_s, artwork_path

    @staticmethod
    def build_avatar_path(avatar_path: str, username: str):
        avatar_user_path = f"{RESOURCES_BASE_PATH}/users/{username}"
        Path(avatar_user_path).mkdir(parents=True, exist_ok=True)
        return f"users/{username}/{avatar_path}", avatar_user_path
