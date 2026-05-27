import re

from config import LAUNCHBOX_API_ENABLED
from handler.filesystem import fs_rom_handler
from handler.redis_handler import async_cache
from logger.logger import log
from utils.database import safe_int

from ..base_handler import MetadataHandler
from ..base_handler import UniversalPlatformSlug as UPS
from .local_source import LocalSource
from .media import build_rom, local_media_req, remote_media_req
from .platforms import get_platform
from .remote_source import RemoteSource
from .types import (
    DASH_COLON_REGEX,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_PLATFORMS_DIR,
    LAUNCHBOX_TAG_REGEX,
    LaunchboxPlatform,
    LaunchboxRom,
)


class LaunchboxHandler(MetadataHandler):
    def __init__(self) -> None:
        self._local = LocalSource()
        self._remote = RemoteSource()

    @classmethod
    def is_cloud_enabled(cls) -> bool:
        return LAUNCHBOX_API_ENABLED

    @classmethod
    def is_local_enabled(cls) -> bool:
        return LAUNCHBOX_PLATFORMS_DIR.exists()

    @classmethod
    def is_enabled(cls) -> bool:
        return cls.is_cloud_enabled() or cls.is_local_enabled()

    async def heartbeat(self) -> bool:
        return self.is_enabled()

    def get_platform(self, slug: str) -> LaunchboxPlatform:
        return get_platform(slug)

    async def get_rom(
        self,
        fs_name: str,
        platform_slug: str,
        keep_tags: bool = False,
        *,
        remote_enabled: bool = True,
    ) -> LaunchboxRom:
        fallback_rom = LaunchboxRom(launchbox_id=None)

        if not self.is_enabled():
            return fallback_rom

        local = await self._local.get_rom(fs_name, platform_slug)

        remote_available = remote_enabled and bool(
            await async_cache.exists(LAUNCHBOX_METADATA_NAME_KEY)
        )

        if local is not None:
            launchbox_id_local = safe_int(local.get("DatabaseID"))
            remote: dict | None = None
            if remote_available:
                if launchbox_id_local:
                    remote = await self._remote.get_by_id(launchbox_id_local)

                if remote is None:
                    local_title = (local.get("Title") or "").strip()
                    if local_title:
                        remote = await self._remote.get_rom(
                            local_title,
                            platform_slug,
                            assume_cache_present=True,
                        )
            platform_name = get_platform(platform_slug).get("name")
            remote_images = await self._remote.fetch_images(
                remote=remote, remote_enabled=remote_available
            )
            media_req = local_media_req(
                platform_name=platform_name,
                fs_name=fs_name,
                local=local,
                remote=remote,
                remote_images=remote_images,
                remote_enabled=remote_available,
            )
            return build_rom(
                local=local,
                remote=remote,
                launchbox_id=launchbox_id_local
                or (remote.get("DatabaseID") if remote else None),
                media_req=media_req,
            )

        match = LAUNCHBOX_TAG_REGEX.search(fs_name)
        launchbox_id_from_tag = int(match.group(1)) if match else None

        if launchbox_id_from_tag is not None:
            log.debug(f"Found LaunchBox ID tag in filename: {launchbox_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(
                launchbox_id_from_tag, remote_enabled=remote_enabled
            )
            if rom_by_id["launchbox_id"]:
                log.debug(
                    f"Successfully matched ROM by LaunchBox ID tag: {fs_name} -> {launchbox_id_from_tag}"
                )
                return rom_by_id
            else:
                log.warning(
                    f"LaunchBox ID {launchbox_id_from_tag} from filename tag not found in LaunchBox"
                )

        if not remote_available:
            return fallback_rom

        # `keep_tags` prevents stripping content that is considered a tag, e.g., anything between `()` or `[]`.
        # By default, tags are still stripped to keep scan behavior consistent with previous versions.
        # If `keep_tags` is True, the full `fs_name` is used for searching.
        if not keep_tags:
            search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        else:
            search_term = fs_name

        # Resolve MAME arcade filename (e.g. wrlok_l3.zip) to its full title
        # via LaunchBox's Mame.xml before name-based lookup.
        if platform_slug == UPS.ARCADE:
            mame_entry = await self._remote.get_mame_entry(fs_name)
            if mame_entry:
                name = (mame_entry.get("Name") or "").strip()
                if name:
                    search_term = name
                    fallback_rom = LaunchboxRom(launchbox_id=None, name=name)

        # We replace " - "/"- " with ": " to match Launchbox's naming convention
        search_term = re.sub(DASH_COLON_REGEX, ": ", search_term).lower()

        # Check if game is scummvm shortname
        if platform_slug == UPS.SCUMMVM:
            search_term = await self._scummvm_format(search_term)
            fallback_rom = LaunchboxRom(launchbox_id=None, name=search_term)

        index_entry = await self._remote.get_rom(
            search_term,
            platform_slug,
            assume_cache_present=True,
        )

        if not index_entry:
            return fallback_rom

        remote_images = await self._remote.fetch_images(
            remote=index_entry, remote_enabled=remote_available
        )
        media_req = remote_media_req(
            remote=index_entry,
            remote_images=remote_images,
            remote_enabled=remote_available,
            platform_name=get_platform(platform_slug).get("name"),
            fs_name=fs_name,
        )

        return build_rom(
            local=None,
            remote=index_entry,
            launchbox_id=index_entry["DatabaseID"],
            media_req=media_req,
        )

    async def get_rom_by_id(
        self,
        database_id: int,
        *,
        remote_enabled: bool = True,
        fs_name: str | None = None,
        platform_slug: str | None = None,
    ) -> LaunchboxRom:
        if not self.is_enabled():
            return LaunchboxRom(launchbox_id=None)

        if not remote_enabled:
            return LaunchboxRom(launchbox_id=None)

        remote = await self._remote.get_by_id(database_id)
        if not remote:
            return LaunchboxRom(launchbox_id=None)

        # Merge local-only fields when a local LaunchBox install has the same game
        local: dict[str, str] | None = None
        if fs_name and platform_slug:
            candidate = await self._local.get_rom(fs_name, platform_slug)
            if (
                candidate is not None
                and safe_int(candidate.get("DatabaseID")) == database_id
            ):
                local = candidate

        platform_name = (
            get_platform(platform_slug).get("name") if platform_slug else None
        )
        remote_images = await self._remote.fetch_images(
            remote=remote, remote_enabled=remote_enabled
        )
        if local is not None:
            media_req = local_media_req(
                platform_name=platform_name,
                fs_name=fs_name or "",
                local=local,
                remote=remote,
                remote_images=remote_images,
                remote_enabled=remote_enabled,
            )
        else:
            media_req = remote_media_req(
                remote=remote,
                remote_images=remote_images,
                remote_enabled=remote_enabled,
                platform_name=platform_name,
                fs_name=fs_name or "",
            )

        return build_rom(
            local=local,
            remote=remote,
            launchbox_id=database_id,
            media_req=media_req,
        )

    async def get_matched_roms_by_name(
        self, search_term: str, platform_slug: str
    ) -> list[LaunchboxRom]:
        if not self.is_enabled():
            return []

        rom = await self.get_rom(search_term, platform_slug, keep_tags=True)
        return [rom]

    async def get_matched_rom_by_id(self, database_id: int) -> LaunchboxRom | None:
        if not self.is_enabled():
            return None

        rom = await self.get_rom_by_id(database_id)
        return rom if rom.get("launchbox_id") else None
