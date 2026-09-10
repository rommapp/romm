import zipfile
from collections.abc import Iterator
from io import BytesIO
from typing import Any, Final

from defusedxml import ElementTree as ET
from redis.asyncio.client import Pipeline

from config import (
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    LAUNCHBOX_API_ENABLED,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
    TASK_TIMEOUT,
)
from handler.dump_cache import encode
from handler.metadata import meta_launchbox_handler
from handler.metadata.launchbox_handler.types import (
    LAUNCHBOX_FILE_FIELDS,
    LAUNCHBOX_FILES_KEY,
    LAUNCHBOX_IMAGE_FIELDS,
    LAUNCHBOX_MAME_FIELDS,
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_INITIAL_IMPORT_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_METADATA_STORE,
    LAUNCHBOX_PLATFORMS_KEY,
)
from handler.metadata.launchbox_handler.utils import fold_title
from handler.redis_handler import async_binary_cache, async_cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask, TaskType
from utils.cache import drop_stale_cache_store, stamp_cache_schema
from utils.context import initialize_context

from . import UpdateStats

# The dump is ~500MB across 600k+ entries. Buffering it into one pipeline peaks
# well over a gigabyte of memory and discards everything if the job dies, so
# writes go out in batches instead.
CACHE_WRITE_BATCH_SIZE: Final[int] = 2000

# Downloading ~100MB and parsing it takes far longer than an ordinary task.
LAUNCHBOX_TASK_TIMEOUT: Final[int] = max(TASK_TIMEOUT, 30 * 60)


class BatchedCacheWriter:
    """Queues cache writes on a pipeline, flushing every `batch_size` entries."""

    def __init__(self, pipe: Pipeline, batch_size: int | None = None):
        self._pipe = pipe
        self._batch_size = batch_size or CACHE_WRITE_BATCH_SIZE
        self._queued = 0

    async def hset(self, key: str, field: str, value: Any) -> None:
        await self._pipe.hset(key, mapping={field: encode(value)})
        self._queued += 1
        if self._queued >= self._batch_size:
            await self.flush()

    async def flush(self) -> None:
        if self._queued:
            await self._pipe.execute()
            self._queued = 0


def _element_to_dict(elem: Any, fields: frozenset[str] | None = None) -> dict[str, Any]:
    if fields is None:
        return {child.tag: child.text for child in elem}
    return {child.tag: child.text for child in elem if child.tag in fields}


def _iter_elements(source: Any) -> Iterator[Any]:
    """Yield each top-level record, discarding it once the caller moves on.

    `iterparse` keeps every element it has parsed attached to the root, so
    without dropping them the whole document ends up in memory.
    """
    ctx = ET.iterparse(source, events=("start", "end"))

    try:
        _, root = next(iter(ctx))
    except StopIteration:
        return

    depth = 0
    for event, elem in ctx:
        if event == "start":
            depth += 1
            continue

        depth -= 1
        if depth > 0:
            continue

        yield elem
        root.clear()


class UpdateLaunchboxMetadataTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            title="Scheduled LaunchBox metadata update",
            description="Updates the LaunchBox metadata store",
            task_type=TaskType.UPDATE,
            enabled=ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
            cron_string=SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
            manual_run=True,
            url="https://gamesdb.launchbox-app.com/Metadata.zip",
            timeout=LAUNCHBOX_TASK_TIMEOUT,
        )

    @property
    def can_run_manually(self) -> bool:
        # The store lives only in the cache, so admins need a way to fill it
        # even when the scheduled update is off. Otherwise turning LaunchBox on
        # leaves a provider that silently matches nothing.
        return self.manual_run and (self.enabled or LAUNCHBOX_API_ENABLED)

    @initialize_context()
    async def run(self, force: bool = False) -> dict[str, Any]:
        update_stats = UpdateStats()

        if not meta_launchbox_handler.is_cloud_enabled():
            log.warning("Launchbox API is not enabled, skipping metadata update")
            return update_stats.to_dict()

        # Reaching here means either the cron fired or an admin asked for it, so
        # the pull goes ahead regardless of the scheduled-update setting.
        content = await super().run(True)
        if content is None:
            log.warning("No content received from launchbox metadata update")
            return update_stats.to_dict()

        # A refresh keeps serving the previous dump, but a first import only
        # holds the batches committed so far, so flag it to keep the provider
        # from reporting healthy off a fraction of the entries.
        if not await meta_launchbox_handler.is_remote_store_populated():
            await async_cache.set(LAUNCHBOX_METADATA_INITIAL_IMPORT_KEY, "1")

        # An import merges into its hashes, so an older release's rows go first.
        await drop_stale_cache_store(async_cache, LAUNCHBOX_METADATA_STORE)

        try:
            zip_file_bytes = BytesIO(content)
            with zipfile.ZipFile(zip_file_bytes) as z:
                file_list = z.namelist()
                total_files = len(file_list)
                processed_files = 0

                # Update initial progress
                update_stats.update(processed=processed_files, total=total_files)

                # Keys are stored the way lookups build them: stripped, and
                # lowercased wherever the lookup lowercases.
                for file in file_list:
                    if file == "Platforms.xml":
                        with z.open(file, "r") as f:
                            async with async_binary_cache.pipeline() as pipe:
                                writer = BatchedCacheWriter(pipe)

                                for elem in _iter_elements(f):
                                    if elem.tag == "Platform":
                                        name_elem = elem.find("Name")
                                        if name_elem is not None and name_elem.text:
                                            await writer.hset(
                                                LAUNCHBOX_PLATFORMS_KEY,
                                                name_elem.text.strip(),
                                                _element_to_dict(elem),
                                            )

                                await writer.flush()
                                processed_files += 1
                                update_stats.update(processed=processed_files)

                    elif file == "Metadata.xml":
                        with z.open(file, "r") as f:
                            async with async_binary_cache.pipeline() as pipe:
                                writer = BatchedCacheWriter(pipe)

                                current_game_image_db_id = None
                                current_game_images: list[dict[str, Any]] = []

                                for elem in _iter_elements(f):
                                    if elem.tag == "Game":
                                        database_id = (
                                            elem.findtext("DatabaseID") or ""
                                        ).strip()
                                        if database_id:
                                            await writer.hset(
                                                LAUNCHBOX_METADATA_DATABASE_ID_KEY,
                                                database_id,
                                                _element_to_dict(elem),
                                            )

                                        name = (elem.findtext("Name") or "").strip()
                                        platform_name = (
                                            elem.findtext("Platform") or ""
                                        ).strip()
                                        if database_id and name and platform_name:
                                            # A full copy of the record here
                                            # costs ~120MB of cache.
                                            await writer.hset(
                                                LAUNCHBOX_METADATA_NAME_KEY,
                                                f"{name.lower()}:{platform_name}",
                                                database_id,
                                            )

                                            folded = fold_title(name)
                                            if folded:
                                                await writer.hset(
                                                    LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
                                                    f"{folded}:{platform_name}",
                                                    database_id,
                                                )

                                    elif elem.tag == "GameAlternateName":
                                        alternate_name = (
                                            elem.findtext("AlternateName") or ""
                                        ).strip()
                                        alternate_id = (
                                            elem.findtext("DatabaseID") or ""
                                        ).strip()
                                        if alternate_name and alternate_id:
                                            await writer.hset(
                                                LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
                                                alternate_name.lower(),
                                                alternate_id,
                                            )

                                    elif elem.tag == "GameImage":
                                        id_elem = elem.find("DatabaseID")
                                        if id_elem is not None and id_elem.text:
                                            image_id = id_elem.text.strip()

                                            if (
                                                current_game_image_db_id is not None
                                                and image_id != current_game_image_db_id
                                            ):
                                                # Store the previous game's images
                                                await writer.hset(
                                                    LAUNCHBOX_METADATA_IMAGE_KEY,
                                                    current_game_image_db_id,
                                                    current_game_images,
                                                )
                                                current_game_images = []

                                            current_game_image_db_id = image_id
                                            current_game_images.append(
                                                _element_to_dict(
                                                    elem, LAUNCHBOX_IMAGE_FIELDS
                                                )
                                            )

                                # Store the last game's images
                                if current_game_image_db_id is not None:
                                    await writer.hset(
                                        LAUNCHBOX_METADATA_IMAGE_KEY,
                                        current_game_image_db_id,
                                        current_game_images,
                                    )
                                await writer.flush()
                                processed_files += 1
                                update_stats.update(processed=processed_files)

                    elif file == "Mame.xml":
                        with z.open(file, "r") as f:
                            async with async_binary_cache.pipeline() as pipe:
                                writer = BatchedCacheWriter(pipe)

                                for elem in _iter_elements(f):
                                    if elem.tag == "MameFile":
                                        filename_elem = elem.find("FileName")
                                        if (
                                            filename_elem is not None
                                            and filename_elem.text
                                        ):
                                            await writer.hset(
                                                LAUNCHBOX_MAME_KEY,
                                                filename_elem.text.strip(),
                                                _element_to_dict(
                                                    elem, LAUNCHBOX_MAME_FIELDS
                                                ),
                                            )

                                await writer.flush()
                                processed_files += 1
                                update_stats.update(processed=processed_files)

                    elif file == "Files.xml":
                        with z.open(file, "r") as f:
                            async with async_binary_cache.pipeline() as pipe:
                                writer = BatchedCacheWriter(pipe)

                                for elem in _iter_elements(f):
                                    if elem.tag == "File":
                                        filename_elem = elem.find("FileName")
                                        platform_elem = elem.find("Platform")
                                        if (
                                            filename_elem is not None
                                            and filename_elem.text
                                            and platform_elem is not None
                                            and platform_elem.text
                                        ):
                                            # The same dump filename exists on several platforms,
                                            # so the key has to carry the platform too.
                                            await writer.hset(
                                                LAUNCHBOX_FILES_KEY,
                                                f"{filename_elem.text.strip().lower()}"
                                                f":{platform_elem.text.strip()}",
                                                _element_to_dict(
                                                    elem, LAUNCHBOX_FILE_FIELDS
                                                ),
                                            )

                                await writer.flush()
                                processed_files += 1
                                update_stats.update(processed=processed_files)

        except (zipfile.BadZipFile, RuntimeError, OSError):
            log.error("Bad zip file in launchbox metadata update")
            return update_stats.to_dict()

        await stamp_cache_schema(async_cache, LAUNCHBOX_METADATA_STORE)

        # Also clears a flag left behind by an earlier run that died partway.
        await async_cache.delete(LAUNCHBOX_METADATA_INITIAL_IMPORT_KEY)

        log.info("Scheduled launchbox metadata update completed!")

        return update_stats.to_dict()


update_launchbox_metadata_task = UpdateLaunchboxMetadataTask()
