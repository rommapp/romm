import json

from strsimpy.jaro_winkler import JaroWinkler

from handler.redis_handler import async_cache
from logger.logger import log

from .platforms import get_platform
from .types import (
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_METADATA_PLATFORM_NAMES_KEY,
)
from .utils import normalize_launchbox_name

_jarowinkler = JaroWinkler()
# Minimum Jaro-Winkler similarity score to accept a fuzzy match
_FUZZY_MATCH_THRESHOLD = 0.90


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

        # Build a deduplicated list of lookup candidates (at most 3):
        # 1. exact as-is, 2. lowercased, 3. normalized (OS chars stripped, NFD)
        lowered = file_name_clean.lower()
        normalized = normalize_launchbox_name(file_name_clean)
        candidates: list[str] = [file_name_clean]
        if lowered != file_name_clean:
            candidates.append(lowered)
        if normalized not in candidates:
            candidates.append(normalized)

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

        # Last resort: fuzzy match against all known titles for this platform
        return await self._fuzzy_match(file_name_clean, platform_name)

    async def _fuzzy_match(
        self, file_name: str, platform_name: str
    ) -> dict | None:
        """
        Load the per-platform names index and find the best Jaro-Winkler
        match for *file_name*.  Returns the full game entry for the best
        match if its similarity score meets _FUZZY_MATCH_THRESHOLD.
        """
        platform_names_json = await async_cache.hget(
            LAUNCHBOX_METADATA_PLATFORM_NAMES_KEY, platform_name
        )
        if not platform_names_json:
            return None

        search_norm = normalize_launchbox_name(file_name)
        if not search_norm:
            return None

        platform_names: list[dict[str, str]] = json.loads(platform_names_json)

        best_score = 0.0
        best_db_id: str | None = None

        for entry in platform_names:
            name_norm = entry.get("normalized", "")
            if not name_norm:
                continue
            score = _jarowinkler.similarity(search_norm, name_norm)
            if score > best_score:
                best_score = score
                best_db_id = entry.get("database_id")

        if best_score >= _FUZZY_MATCH_THRESHOLD and best_db_id:
            log.debug(
                f"Fuzzy-matched '{file_name}' → database ID {best_db_id} "
                f"(score {best_score:.3f})"
            )
            return await self.get_by_id(best_db_id)

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
