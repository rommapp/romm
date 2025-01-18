import json
import zipfile
from itertools import batched
from typing import Final

try:
    from defusedxml import ElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

from config import (
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
)
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask
from utils.context import initialize_context

LAUNCHBOX_PLATFORMS_KEY: Final = "romm:launchbox_platforms"
LAUNCHBOX_METADATA_DATABASE_ID_KEY: Final = "romm:launchbox_metadata_database_id"
LAUNCHBOX_METADATA_NAME_KEY: Final = "romm:launchbox_metadata_name"
LAUNCHBOX_METADATA_IMAGE_KEY: Final = "romm:launchbox_metadata_image"
LAUNCHBOX_MAME_KEY: Final = "romm:launchbox_mame"


class UpdateLaunchboxMetadataTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            func="tasks.update_launchbox_metadata.update_launchbox_metadata_task.run",
            description="launchbox metadata update",
            enabled=ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
            cron_string=SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
            url="https://gamesdb.launchbox-app.com/Metadata.zip",
        )

    @initialize_context()
    async def run(self, force: bool = False) -> None:
        content = await super().run(force)
        if content is None:
            return

        try:
            with zipfile.ZipFile(content) as z:
                for file in z.namelist():
                    if file == "Platforms.xml":
                        platform_dict = {}
                        with z.open(file, "r") as f:
                            for platform in ET.parse(f).getroot().findall("Platform"):
                                name_elem = platform.find("Name")
                                assert name_elem is not None
                                platform_dict[name_elem.text] = {
                                    child.tag: child.text for child in platform
                                }

                            async with async_cache.pipeline() as pipe:
                                for platform_batch in batched(
                                    platform_dict.items(), 2000
                                ):
                                    await pipe.hset(
                                        LAUNCHBOX_PLATFORMS_KEY,
                                        mapping={
                                            k: json.dumps(v)
                                            for k, v in dict(platform_batch).items()
                                        },
                                    )

                    elif file == "Metadata.xml":
                        metadata_by_id_dict: dict[str, object] = {}
                        metadata_by_name_dict: dict[str, object] = {}
                        metadata_images_by_id_dict: dict[str, list[object]] = {}

                        with z.open(file, "r") as f:
                            root = ET.parse(f).getroot()
                            for metadata in root.findall("Game"):
                                id_elem = metadata.find("DatabaseID")
                                assert id_elem is not None
                                metadata_by_id_dict[str(id_elem.text)] = {
                                    child.tag: child.text for child in metadata
                                }

                                name_elem = metadata.find("Name")
                                assert name_elem is not None
                                metadata_by_name_dict[str(name_elem.text)] = {
                                    child.tag: child.text for child in metadata
                                }

                            for image in root.findall("GameImage"):
                                id_elem = image.find("DatabaseID")
                                assert id_elem is not None

                                if id_elem.text not in metadata_images_by_id_dict:
                                    metadata_images_by_id_dict[str(id_elem.text)] = []

                                metadata_images_by_id_dict[str(id_elem.text)].append(
                                    {child.tag: child.text for child in image}
                                )

                            async with async_cache.pipeline() as pipe:
                                for mbid_batch in batched(
                                    metadata_by_id_dict.items(), 2000
                                ):
                                    await pipe.hset(
                                        LAUNCHBOX_METADATA_DATABASE_ID_KEY,
                                        mapping={
                                            k: json.dumps(v)
                                            for k, v in dict(mbid_batch).items()
                                        },
                                    )

                                for mbn_batch in batched(
                                    metadata_by_name_dict.items(), 2000
                                ):
                                    await pipe.hset(
                                        LAUNCHBOX_METADATA_NAME_KEY,
                                        mapping={
                                            k: json.dumps(v)
                                            for k, v in dict(mbn_batch).items()
                                        },
                                    )

                                for data_batch in batched(
                                    metadata_images_by_id_dict.items(), 2000
                                ):

                                    await pipe.hset(
                                        LAUNCHBOX_METADATA_IMAGE_KEY,
                                        mapping={
                                            k: json.dumps(v)
                                            for k, v in dict(data_batch).items()
                                        },
                                    )
                    elif file == "Mame.xml":
                        mame_dict = {}
                        with z.open(file, "r") as f:
                            for mame in ET.parse(f).getroot().findall("MameFile"):
                                filename_elem = mame.find("FileName")
                                assert filename_elem is not None
                                mame_dict[filename_elem.text] = {
                                    child.tag: child.text for child in mame
                                }

                            async with async_cache.pipeline() as pipe:
                                for mame_batch in batched(mame_dict.items(), 2000):
                                    await pipe.hset(
                                        LAUNCHBOX_MAME_KEY,
                                        mapping={
                                            k: json.dumps(v)
                                            for k, v in dict(mame_batch).items()
                                        },
                                    )
        except zipfile.BadZipFile:
            log.error("Bad zip file in launchbox metadata update")
            return

        log.info("Scheduled launchbox metadata update completed!")


update_launchbox_metadata_task = UpdateLaunchboxMetadataTask()
