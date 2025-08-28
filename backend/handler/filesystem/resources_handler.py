import os
from io import BytesIO
from pathlib import Path

import httpx
from config import RESOURCES_BASE_PATH
from fastapi import status
from logger.logger import log
from models.collection import Collection
from models.rom import Rom
from PIL import Image, ImageFile, UnidentifiedImageError
from utils.context import ctx_httpx_client

from .base_handler import CoverSize, FSHandler


class FSResourcesHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=RESOURCES_BASE_PATH)

    def get_platform_resources_path(self, platform_id: int) -> str:
        return os.path.join("roms", str(platform_id))

    def cover_exists(self, entity: Rom | Collection, size: CoverSize) -> bool:
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

        small_img.save(save_path)

    def _create_webp_version(self, image_path: Path, quality: int = 85) -> Path | None:
        """Create a WebP version of the given image file.
        Args:
            image_path: Path to the original image file
            quality: WebP quality (0-100, default 85)
        Returns:
            Path to the created WebP file
        """
        webp_path = image_path.with_suffix(".webp")

        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (WebP doesn't support RGBA)
                if img.mode in ("RGBA", "LA", "P"):
                    # Create white background for transparent images
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(
                        img, mask=img.split()[-1] if img.mode == "RGBA" else None
                    )
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.save(webp_path, "WEBP", quality=quality, optimize=True)
                log.info(f"Created WebP version: {webp_path}")
                return webp_path
        except Exception as exc:
            log.error(f"Failed to create WebP version of {image_path}: {str(exc)}")
            return None

    def _get_webp_path(self, original_path: Path) -> Path | None:
        """Get the WebP version path for a given image file.
        Args:
            original_path: Path to the original image file
        Returns:
            Path to WebP file if it exists, None otherwise
        """
        webp_path = original_path.with_suffix(".webp")
        return webp_path if webp_path.exists() else None

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
        await self.make_directory(f"{cover_file}")

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url_cover, timeout=120) as response:
                if response.status_code == status.HTTP_200_OK:
                    async with await self.write_file_streamed(
                        path=cover_file, filename=f"{size.value}.png"
                    ) as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch cover at {url_cover}: {str(exc)}")
            return None

        if size == CoverSize.SMALL:
            try:
                image_path = self.validate_path(f"{cover_file}/{size.value}.png")
                with Image.open(image_path) as img:
                    self.resize_cover_to_small(img, save_path=str(image_path))
            except UnidentifiedImageError as exc:
                log.error(f"Unable to identify image {cover_file}: {str(exc)}")
                return None

    def _get_cover_path(self, entity: Rom | Collection, size: CoverSize) -> str | None:
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            entity: Rom or Collection object
            size: size of the cover
        """
        full_path = self.validate_path(f"{entity.fs_resources_path}/cover")
        for matched_file in full_path.glob(f"{size.value}.*"):
            return str(matched_file.relative_to(self.base_path))

        return None

    async def get_cover(
        self, entity: Rom | Collection | None, overwrite: bool, url_cover: str | None
    ) -> tuple[str | None, str | None]:
        if not entity:
            return None, None

        small_cover_exists = self.cover_exists(entity, CoverSize.SMALL)
        if url_cover and (overwrite or not small_cover_exists):
            await self._store_cover(entity, url_cover, CoverSize.SMALL)
            small_cover_exists = self.cover_exists(entity, CoverSize.SMALL)

        path_cover_s = (
            self._get_cover_path(entity, CoverSize.SMALL)
            if small_cover_exists
            else None
        )

        big_cover_exists = self.cover_exists(entity, CoverSize.BIG)
        if url_cover and (overwrite or not big_cover_exists):
            await self._store_cover(entity, url_cover, CoverSize.BIG)
            big_cover_exists = self.cover_exists(entity, CoverSize.BIG)

        path_cover_l = (
            self._get_cover_path(entity, CoverSize.BIG) if big_cover_exists else None
        )

        return path_cover_s, path_cover_l

    async def remove_cover(self, entity: Rom | Collection | None):
        if not entity:
            return {"path_cover_s": "", "path_cover_l": ""}

        await self.remove_directory(f"{entity.fs_resources_path}/cover")

        return {"path_cover_s": "", "path_cover_l": ""}

    async def _build_artwork_path(
        self, entity: Rom | Collection, file_ext: str
    ) -> tuple[Path, Path]:
        path_cover = f"{entity.fs_resources_path}/cover"
        path_cover_l = self.validate_path(
            f"{path_cover}/{CoverSize.BIG.value}.{file_ext}"
        )
        path_cover_s = self.validate_path(
            f"{path_cover}/{CoverSize.SMALL.value}.{file_ext}"
        )

        await self.make_directory(path_cover)

        return path_cover_l, path_cover_s

    async def store_artwork(
        self, entity: Rom | Collection, artwork: BytesIO, file_ext: str
    ) -> tuple[str | None, str | None]:
        """Store artwork in filesystem and return paths."""
        path_cover_l, path_cover_s = await self._build_artwork_path(entity, file_ext)

        try:
            with Image.open(artwork) as img:
                img.save(path_cover_l)
                self.resize_cover_to_small(img, save_path=str(path_cover_s))
        except UnidentifiedImageError as exc:
            log.error(
                f"Unable to identify image for {entity.fs_resources_path}: {str(exc)}"
            )
            return None, None

        return str(path_cover_l.relative_to(self.base_path)), str(
            path_cover_s.relative_to(self.base_path)
        )

    async def _store_screenshot(self, rom: Rom, url_screenhot: str, idx: int):
        """Store roms resources in filesystem

        Args:
            rom: Rom object
            url_screenhot: URL to get the screenshot
        """
        screenshot_path = f"{rom.fs_resources_path}/screenshots"

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream(
                "GET", url_screenhot, timeout=120
            ) as response:
                if response.status_code == status.HTTP_200_OK:
                    async with await self.write_file_streamed(
                        path=screenshot_path, filename=f"{idx}.jpg"
                    ) as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
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

    def manual_exists(self, rom: Rom) -> bool:
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
        manual_path = f"{rom.fs_resources_path}/manual"

        httpx_client = ctx_httpx_client.get()
        try:
            async with httpx_client.stream("GET", url_manual, timeout=120) as response:
                if response.status_code == status.HTTP_200_OK:
                    async with await self.write_file_streamed(
                        path=manual_path, filename=f"{rom.id}.pdf"
                    ) as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch manual at {url_manual}: {str(exc)}")
            return None

    def _get_manual_path(self, rom: Rom) -> str | None:
        """Returns rom manual filesystem path adapted to frontend folder structure

        Args:
            rom: Rom object
        """
        full_path = self.validate_path(f"{rom.fs_resources_path}/manual")
        for matched_file in full_path.glob(f"{rom.id}.pdf"):
            return str(matched_file.relative_to(self.base_path))

        return None

    async def get_manual(
        self, rom: Rom | None, overwrite: bool, url_manual: str | None
    ) -> str | None:
        if not rom:
            return None

        manual_exists = self.manual_exists(rom)
        if url_manual and (overwrite or not manual_exists):
            await self._store_manual(rom, url_manual)
            manual_exists = self.manual_exists(rom)

        path_manual = self._get_manual_path(rom) if manual_exists else None
        return path_manual

    async def store_ra_badge(self, url: str, path: str) -> None:
        httpx_client = ctx_httpx_client.get()
        directory, filename = os.path.split(path)

        if await self.file_exists(path):
            log.debug(f"Badge {path} already exists, skipping download")
            return

        try:
            async with httpx_client.stream("GET", url, timeout=120) as response:
                if response.status_code == status.HTTP_200_OK:
                    async with await self.write_file_streamed(
                        path=directory, filename=filename
                    ) as f:
                        async for chunk in response.aiter_raw():
                            await f.write(chunk)
        except httpx.TransportError as exc:
            log.error(f"Unable to fetch cover at {url}: {str(exc)}")

    def get_ra_resources_path(self, platform_id: int, rom_id: int) -> str:
        return os.path.join(
            "roms",
            str(platform_id),
            str(rom_id),
            "retroachievements",
        )

    def get_ra_badges_path(self, platform_id: int, rom_id: int) -> str:
        return os.path.join(self.get_ra_resources_path(platform_id, rom_id), "badges")

    async def create_ra_resources_path(self, platform_id: int, rom_id: int) -> None:
        await self.make_directory(self.get_ra_resources_path(platform_id, rom_id))
