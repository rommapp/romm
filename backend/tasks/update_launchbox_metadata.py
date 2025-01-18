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
            with zipfile.ZipFile(
                "/Users/georges-antoine/workspace/romm/backend/tasks/Metadata.zip", "r"
            ) as z:
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
                                for data_batch in batched(platform_dict.items(), 2000):
                                    metadata_map = {
                                        k: json.dumps(v)
                                        for k, v in dict(data_batch).items()
                                    }
                                    await pipe.hset(
                                        LAUNCHBOX_PLATFORMS_KEY, mapping=metadata_map
                                    )
                    elif file == "Metadata.xml":
                        metadata_by_id_dict = {}
                        metadata_by_name_dict = {}

                        with z.open(file, "r") as f:
                            for metadata in ET.parse(f).getroot().findall("Game"):
                                id_elem = metadata.find("DatabaseID")
                                assert id_elem is not None
                                metadata_by_id_dict[id_elem.text] = {
                                    child.tag: child.text for child in metadata
                                }

                                name_elem = metadata.find("Name")
                                assert name_elem is not None
                                metadata_by_name_dict[name_elem.text] = {
                                    child.tag: child.text for child in metadata
                                }

                            async with async_cache.pipeline() as pipe:
                                for data_batch in batched(
                                    metadata_by_id_dict.items(), 2000
                                ):
                                    titledb_map = {
                                        k: json.dumps(v)
                                        for k, v in dict(data_batch).items()
                                    }
                                    await pipe.hset(
                                        LAUNCHBOX_METADATA_DATABASE_ID_KEY,
                                        mapping=titledb_map,
                                    )

                                for data_batch in batched(
                                    metadata_by_name_dict.items(), 2000
                                ):
                                    titledb_map = {
                                        k: json.dumps(v)
                                        for k, v in dict(data_batch).items()
                                    }
                                    await pipe.hset(
                                        LAUNCHBOX_METADATA_NAME_KEY, mapping=titledb_map
                                    )
        except zipfile.BadZipFile:
            log.error("Bad zip file in launchbox metadata update")
            return

        log.info("Scheduled launchbox metadata update completed!")


update_launchbox_metadata_task = UpdateLaunchboxMetadataTask()
