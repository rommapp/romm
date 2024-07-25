import shutil

import httpx
from anyio import Path, open_file
from config import RESOURCES_BASE_PATH
from fastapi import HTTPException, status
from logger.logger import log
from models.collection import Collection
from models.rom import Rom
from PIL import Image
from utils.context import ctx_httpx_client

from .base_handler import CoverSize, FSHandler


class FSResourcesHandler(FSHandler):
    @staticmethod
    async def cover_exists(entity: Rom | Collection, size: CoverSize) -> bool:
        """Check if rom cover exists in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            size: size of the cover
        Returns
            True if cover exists in filesystem else False
        """
        async for _ in Path(
            f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"
        ).glob(f"{size.value}.*"):
            # At least one file found.
            return True
        return False

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

    async def _store_cover(
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

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url_cover, timeout=120) as response:
                if response.status_code == 200:
                    await Path(cover_path).mkdir(parents=True, exist_ok=True)
                    async with await open_file(f"{cover_path}/{cover_file}", "wb") as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.NetworkError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch cover at {url_cover}: {str(exc)}",
            ) from exc
        except httpx.ProtocolError:
            log.warning(f"Failure writing cover {url_cover} to file (ProtocolError)")

        if size == CoverSize.SMALL:
            self.resize_cover_to_small(f"{cover_path}/{cover_file}")

    @staticmethod
    async def _get_cover_path(entity: Rom | Collection, size: CoverSize) -> str:
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom file
            size: size of the cover
        """
        async for matched_file in Path(
            f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"
        ).glob(f"{size.value}.*"):
            return str(matched_file.relative_to(RESOURCES_BASE_PATH))
        return ""

    async def get_cover(
        self, entity: Rom | Collection | None, overwrite: bool, url_cover: str = ""
    ) -> tuple[str, str]:
        if not entity:
            return "", ""

        small_cover_exists = await self.cover_exists(entity, CoverSize.SMALL)
        if url_cover and (overwrite or not small_cover_exists):
            await self._store_cover(entity, url_cover, CoverSize.SMALL)
            small_cover_exists = await self.cover_exists(entity, CoverSize.SMALL)
        path_cover_s = (
            (await self._get_cover_path(entity, CoverSize.SMALL))
            if small_cover_exists
            else ""
        )

        big_cover_exists = await self.cover_exists(entity, CoverSize.BIG)
        if url_cover and (overwrite or not big_cover_exists):
            await self._store_cover(entity, url_cover, CoverSize.BIG)
            big_cover_exists = await self.cover_exists(entity, CoverSize.BIG)
        path_cover_l = (
            (await self._get_cover_path(entity, CoverSize.BIG))
            if big_cover_exists
            else ""
        )

        return path_cover_s, path_cover_l

    @staticmethod
    def remove_cover(entity: Rom | Collection | None):
        if not entity:
            return {"path_cover_s": "", "path_cover_l": ""}

        cover_path = f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"
        try:
            shutil.rmtree(cover_path)
        except FileNotFoundError:
            log.warning(
                f"Couldn't remove cover from '{entity.name or entity.id}' since '{cover_path}' doesn't exists."
            )

        return {"path_cover_s": "", "path_cover_l": ""}

    @staticmethod
    async def build_artwork_path(entity: Rom | Collection | None, file_ext: str):
        if not entity:
            return "", "", ""

        path_cover = f"{entity.fs_resources_path}/cover"
        path_cover_l = f"{path_cover}/{CoverSize.BIG.value}.{file_ext}"
        path_cover_s = f"{path_cover}/{CoverSize.SMALL.value}.{file_ext}"
        artwork_path = f"{RESOURCES_BASE_PATH}/{entity.fs_resources_path}/cover"
        await Path(artwork_path).mkdir(parents=True, exist_ok=True)

        return path_cover_l, path_cover_s, artwork_path

    @staticmethod
    async def _store_screenshot(rom: Rom, url: str, idx: int):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            url: url to get the screenshot
        """
        screenshot_file = f"{idx}.jpg"
        screenshot_path = f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}/screenshots"

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url, timeout=120) as response:
                if response.status_code == 200:
                    await Path(screenshot_path).mkdir(parents=True, exist_ok=True)
                    async with await open_file(
                        f"{screenshot_path}/{screenshot_file}", "wb"
                    ) as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.NetworkError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch screenshot at {url}: {str(exc)}",
            ) from exc
        except httpx.ProtocolError:
            log.warning(f"Failure writing screenshot {url} to file (ProtocolError)")

    @staticmethod
    def _get_screenshot_path(rom: Rom, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            idx: index number of screenshot
        """
        return f"{rom.fs_resources_path}/screenshots/{idx}.jpg"

    async def get_rom_screenshots(
        self, rom: Rom | None, url_screenshots: list
    ) -> list[str]:
        if not rom:
            return []

        path_screenshots: list[str] = []
        for idx, url in enumerate(url_screenshots):
            await self._store_screenshot(rom, url, idx)
            path_screenshots.append(self._get_screenshot_path(rom, str(idx)))

        return path_screenshots
