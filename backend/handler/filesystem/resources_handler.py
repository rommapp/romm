import os
import shutil

import httpx
from anyio import Path, open_file
from config import RESOURCES_BASE_PATH
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.collection import Collection
from models.rom import Rom
from PIL import Image, ImageFile, UnidentifiedImageError
from utils.context import ctx_httpx_client

from .base_handler import CoverSize, FSHandler


class FSResourcesHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=RESOURCES_BASE_PATH)

    async def cover_exists(self, entity: Rom | Collection, size: CoverSize) -> bool:
        """Check if rom cover exists in filesystem

        Args:
            fs_slug: short name of the platform
            rom_name: name of rom file
            size: size of the cover
        Returns
            True if cover exists in filesystem else False
        """
        full_path = self.validate_path(f"{entity.fs_resources_path}/cover")
        for _ in full_path.glob(f"{size.value}.*"):
            return True  # At least one file found
        return False

    def resize_cover_to_small(self, cover: ImageFile.ImageFile, save_path: str) -> None:
        """Resize cover to small size, and save it to filesystem."""
        if cover.height >= 1000:
            ratio = 0.2
        else:
            ratio = 0.4

        small_width = int(cover.width * ratio)
        small_height = int(cover.height * ratio)
        small_size = (small_width, small_height)
        small_img = cover.resize(small_size)

        full_path = self.validate_path(save_path)
        small_img.save(full_path)

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
        cover_file = f"{entity.fs_resources_path}/cover"
        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url_cover, timeout=120) as response:
                if response.status_code == 200:
                    with self.write_file_streamed(
                        path=cover_file, filename="{size.value}.png"
                    ) as f:
                        async for chunk in response.aiter_raw():
                            f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch cover at {url_cover}: {str(exc)}")

        if size == CoverSize.SMALL:
            try:
                with Image.open(cover_file) as img:
                    self.resize_cover_to_small(img, save_path=cover_file)
            except UnidentifiedImageError as exc:
                log.error(f"Unable to identify image {cover_file}: {str(exc)}")
                return None

    async def _get_cover_path(self, entity: Rom | Collection, size: CoverSize) -> str:
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            entity: Rom or Collection object
            size: size of the cover
        """
        full_path = self.validate_path(f"{entity.fs_resources_path}/cover")
        for matched_file in full_path.glob(f"{size.value}.*"):
            return str(matched_file.relative_to(self.base_path))
        return ""

    async def get_cover(
        self, entity: Rom | Collection | None, overwrite: bool, url_cover: str | None
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

    def remove_cover(self, entity: Rom | Collection | None):
        if not entity:
            return {"path_cover_s": "", "path_cover_l": ""}

        self.remove_directory(f"{entity.fs_resources_path}/cover")

        return {"path_cover_s": "", "path_cover_l": ""}

    async def build_artwork_path(self, entity: Rom | Collection | None, file_ext: str):
        if not entity:
            return "", ""

        path_cover = f"{entity.fs_resources_path}/cover"
        path_cover_l = f"{path_cover}/{CoverSize.BIG.value}.{file_ext}"
        path_cover_s = f"{path_cover}/{CoverSize.SMALL.value}.{file_ext}"

        self.make_directory(path_cover)

        return path_cover_l, path_cover_s

    async def _store_screenshot(self, rom: Rom, url_screenhot: str, idx: int):
        """Store roms resources in filesystem

        Args:
            rom: Rom object
            url_screenhot: URL to get the screenshot
        """
        screenshot_file = f"{idx}.jpg"
        screenshot_path = f"{rom.fs_resources_path}/screenshots"

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream(
                "GET", url_screenhot, timeout=120
            ) as response:
                if response.status_code == 200:
                    with self.write_file_streamed(
                        path=screenshot_path, filename=screenshot_file
                    ) as f:
                        async for chunk in response.aiter_raw():
                            f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch screenshot at {url_screenhot}: {str(exc)}")
            return None

    def _get_screenshot_path(self, rom: Rom, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            rom: Rom object
            idx: index number of screenshot
        """
        return f"{rom.fs_resources_path}/screenshots/{idx}.jpg"

    async def get_rom_screenshots(
        self, rom: Rom | None, url_screenshots: list | None
    ) -> list[str]:
        if not rom or not url_screenshots:
            return []

        path_screenshots: list[str] = []
        for idx, url_screenhot in enumerate(url_screenshots):
            await self._store_screenshot(rom, url_screenhot, idx)
            path_screenshots.append(self._get_screenshot_path(rom, str(idx)))

        return path_screenshots

    async def manual_exists(self, rom: Rom) -> bool:
        """Check if rom manual exists in filesystem

        Args:
            rom: Rom object
        Returns
            True if manual exists in filesystem else False
        """
        full_path = self.validate_path(f"{rom.fs_resources_path}/manual")
        for _ in full_path.glob(f"{rom.id}.pdf"):
            return True
        return False

    async def _store_manual(self, rom: Rom, url_manual: str):
        manual_path = Path(f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}/manual")
        manual_file = manual_path / Path(f"{rom.id}.pdf")

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url_manual, timeout=120) as response:
                if response.status_code == 200:
                    await manual_path.mkdir(parents=True, exist_ok=True)
                    async with await manual_file.open("wb") as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch manual at {url_manual}: {str(exc)}")
            return None

    async def _get_manual_path(rom: Rom) -> str:
        """Returns rom manual filesystem path adapted to frontend folder structure

        Args:
            rom: Rom object
        """
        async for matched_file in Path(
            f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}/manual"
        ).glob(f"{rom.id}.pdf"):
            return str(matched_file.relative_to(RESOURCES_BASE_PATH))
        return ""

    async def get_manual(
        self, rom: Rom | None, overwrite: bool, url_manual: str | None
    ) -> str:
        if not rom:
            return ""

        manual_exists = await self.manual_exists(rom)
        if url_manual and (overwrite or not manual_exists):
            await self._store_manual(rom, url_manual)
            manual_exists = await self.manual_exists(rom)
        path_manual = (await self._get_manual_path(rom)) if manual_exists else ""

        return path_manual

    async def store_ra_badge(self, url: str, file_path: str) -> None:
        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url, timeout=120) as response:
                if response.status_code == 200:
                    await Path(f"{RESOURCES_BASE_PATH}/{file_path}").parent.mkdir(
                        parents=True, exist_ok=True
                    )
                    async with await Path(f"{RESOURCES_BASE_PATH}/{file_path}").open(
                        "wb"
                    ) as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch cover at {url}: {str(exc)}")

    def get_ra_base_path(self, platform_id: int, rom_id: int) -> str:
        return os.path.join(
            "roms",
            str(platform_id),
            str(rom_id),
            "retroachievements",
        )

    def get_ra_badges_path(self, platform_id: int, rom_id: int) -> str:
        return os.path.join(self.get_ra_base_path(platform_id, rom_id), "badges")

    def create_ra_resources_path(self, platform_id: int, rom_id: int) -> None:
        os.makedirs(
            os.path.join(
                RESOURCES_BASE_PATH,
                self.get_ra_base_path(platform_id, rom_id),
            ),
            exist_ok=True,
        )
