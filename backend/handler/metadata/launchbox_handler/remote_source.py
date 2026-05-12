import json

from handler.redis_handler import async_cache
from logger.logger import log

from .platforms import get_platform
from .types import (
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
)


class RemoteSource:
    async def get_by_id(self, database_id: int | str) -> dict | None:
        entry = await async_cache.hget(
            LAUNCHBOX_METADATA_DATABASE_ID_KEY, str(database_id)
        )
        if not entry:
            return None
        return json.loads(entry)

    async def get_rom(
        self,
        file_name: str,
        platform_slug: str,
        *,
        assume_cache_present: bool = False,
    ) -> dict | None:
        if not assume_cache_present and not (
            await async_cache.exists(LAUNCHBOX_METADATA_NAME_KEY)
        ):
            log.error("Could not find the Launchbox Metadata.xml file in cache")
            return None

        lb_platform = get_platform(platform_slug)
        platform_name = lb_platform.get("name", None)
        if not platform_name:
            return None

        file_name_clean = (file_name or "").strip()
        if not file_name_clean:
            return None

        candidates: list[str] = [file_name_clean]
        lower = file_name_clean.lower()
        if lower != file_name_clean:
            candidates.append(lower)

        for candidate in candidates:
            metadata_name_index_entry = await async_cache.hget(
                LAUNCHBOX_METADATA_NAME_KEY, f"{candidate}:{platform_name}"
            )
            if metadata_name_index_entry:
                return json.loads(metadata_name_index_entry)

        for candidate in candidates:
            metadata_alternate_name_index_entry = await async_cache.hget(
                LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY, candidate
            )
            if not metadata_alternate_name_index_entry:
                continue

            metadata_alternate_name_index_entry = json.loads(
                metadata_alternate_name_index_entry
            )
            database_id = metadata_alternate_name_index_entry["DatabaseID"]
            metadata_database_index_entry = await async_cache.hget(
                LAUNCHBOX_METADATA_DATABASE_ID_KEY, database_id
            )
            if metadata_database_index_entry:
                return json.loads(metadata_database_index_entry)

        return None

    async def get_mame_entry(self, file_name: str) -> dict | None:
        """Resolve a MAME arcade filename to its LaunchBox MAME entry.

        LaunchBox's Mame.xml indexes `<MameFile>` records by `<FileName>` — the
        MAME short name without an extension (e.g. `wrlok_l3` for `wrlok_l3.zip`).
        The entry carries `<Name>` — the full title to search for in Metadata.xml.
        """
        file_name_clean = (file_name or "").strip()
        if not file_name_clean:
            return None

        # Try the raw filename first, then the stem (sans extension).
        candidates: list[str] = [file_name_clean]
        from pathlib import Path

        stem = Path(file_name_clean).stem
        if stem and stem != file_name_clean:
            candidates.append(stem)

        for candidate in candidates:
            entry = await async_cache.hget(LAUNCHBOX_MAME_KEY, candidate)
            if entry:
                return json.loads(entry)

        return None

    async def fetch_images(
        self,
        *,
        remote: dict | None = None,
        database_id: str | int | None = None,
        remote_enabled: bool = True,
    ) -> list[dict] | None:
        if not remote_enabled:
            return None

        resolved_id = database_id
        if resolved_id is None and remote is not None:
            resolved_id = remote.get("DatabaseID")

        if not resolved_id:
            return None

        metadata_image_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_IMAGE_KEY, str(resolved_id)
        )

        if not metadata_image_index_entry:
            return None

        return json.loads(metadata_image_index_entry)
