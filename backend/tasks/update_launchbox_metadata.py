import json
import zipfile
from io import BytesIO
from typing import Final

from config import (
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    LAUNCHBOX_API_ENABLED,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
)
from defusedxml import ElementTree as ET
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask
from utils.context import initialize_context

LAUNCHBOX_PLATFORMS_KEY: Final = "romm:launchbox_platforms"
LAUNCHBOX_METADATA_DATABASE_ID_KEY: Final = "romm:launchbox_metadata_database_id"
LAUNCHBOX_METADATA_NAME_KEY: Final = "romm:launchbox_metadata_name"
LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY: Final = "romm:launchbox_metadata_alternate_name"
LAUNCHBOX_METADATA_IMAGE_KEY: Final = "romm:launchbox_metadata_image"
LAUNCHBOX_MAME_KEY: Final = "romm:launchbox_mame"
LAUNCHBOX_FILES_KEY: Final = "romm:launchbox_files"


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
        if not LAUNCHBOX_API_ENABLED:
            log.warning("Launchbox API is not enabled, skipping metadata update")
            return

        content = await super().run(force)
        if content is None:
            return

        try:
            zip_file_bytes = BytesIO(content)
            with zipfile.ZipFile(zip_file_bytes) as z:
                for file in z.namelist():
                    if file == "Platforms.xml":
                        with z.open(file, "r") as f:
                            async with async_cache.pipeline() as pipe:
                                ctx = ET.iterparse(f, events=("end",))

                                for _, elem in ctx:
                                    if elem.tag == "Platform":
                                        name_elem = elem.find("Name")
                                        if name_elem is not None and name_elem.text:
                                            await pipe.hset(
                                                LAUNCHBOX_PLATFORMS_KEY,
                                                mapping={
                                                    name_elem.text: json.dumps(
                                                        {
                                                            child.tag: child.text
                                                            for child in elem
                                                        }
                                                    )
                                                },
                                            )

                                        elem.clear()
                                await pipe.execute()

                    elif file == "Metadata.xml":
                        with z.open(file, "r") as f:
                            async with async_cache.pipeline() as pipe:
                                ctx = ET.iterparse(f, events=("end",))

                                current_game_image_db_id = None
                                current_game_images = []

                                for _, elem in ctx:
                                    if elem.tag == "Game":
                                        id_elem = elem.find("DatabaseID")
                                        if id_elem is not None and id_elem.text:
                                            await pipe.hset(
                                                LAUNCHBOX_METADATA_DATABASE_ID_KEY,
                                                mapping={
                                                    id_elem.text: json.dumps(
                                                        {
                                                            child.tag: child.text
                                                            for child in elem
                                                        }
                                                    )
                                                },
                                            )

                                        name_elem = elem.find("Name")
                                        if name_elem is not None and name_elem.text:
                                            await pipe.hset(
                                                LAUNCHBOX_METADATA_NAME_KEY,
                                                mapping={
                                                    name_elem.text: json.dumps(
                                                        {
                                                            child.tag: child.text
                                                            for child in elem
                                                        }
                                                    )
                                                },
                                            )
                                        elem.clear()

                                    elif elem.tag == "GameAlternateName":
                                        alternate_name_elem = elem.find("AlternateName")
                                        if (
                                            alternate_name_elem is not None
                                            and alternate_name_elem.text
                                        ):
                                            await pipe.hset(
                                                LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
                                                mapping={
                                                    alternate_name_elem.text: json.dumps(
                                                        {
                                                            child.tag: child.text
                                                            for child in elem
                                                        }
                                                    )
                                                },
                                            )

                                        elem.clear()

                                    elif elem.tag == "GameImage":
                                        id_elem = elem.find("DatabaseID")
                                        if id_elem is not None and id_elem.text:
                                            image_id = str(id_elem.text)

                                            if (
                                                current_game_image_db_id is not None
                                                and image_id != current_game_image_db_id
                                            ):
                                                # Store the previous game's images
                                                await pipe.hset(
                                                    LAUNCHBOX_METADATA_IMAGE_KEY,
                                                    mapping={
                                                        current_game_image_db_id: json.dumps(
                                                            current_game_images
                                                        )
                                                    },
                                                )
                                                current_game_images = []

                                            current_game_image_db_id = image_id
                                            current_game_images.append(
                                                {
                                                    child.tag: child.text
                                                    for child in elem
                                                }
                                            )
                                        elem.clear()
                                await pipe.execute()

                    elif file == "Mame.xml":
                        with z.open(file, "r") as f:
                            async with async_cache.pipeline() as pipe:
                                ctx = ET.iterparse(f, events=("end",))

                                for _, elem in ctx:
                                    if elem.tag == "MameFile":
                                        filename_elem = elem.find("FileName")
                                        if (
                                            filename_elem is not None
                                            and filename_elem.text
                                        ):
                                            await pipe.hset(
                                                LAUNCHBOX_MAME_KEY,
                                                mapping={
                                                    filename_elem.text: json.dumps(
                                                        {
                                                            child.tag: child.text
                                                            for child in elem
                                                        }
                                                    )
                                                },
                                            )

                                        elem.clear()
                                await pipe.execute()

                    elif file == "Files.xml":
                        with z.open(file, "r") as f:
                            async with async_cache.pipeline() as pipe:
                                ctx = ET.iterparse(f, events=("end",))

                                for _, elem in ctx:
                                    if elem.tag == "File":
                                        filename_elem = elem.find("FileName")
                                        if (
                                            filename_elem is not None
                                            and filename_elem.text
                                        ):
                                            await pipe.hset(
                                                LAUNCHBOX_FILES_KEY,
                                                mapping={
                                                    filename_elem.text: json.dumps(
                                                        {
                                                            child.tag: child.text
                                                            for child in elem
                                                        }
                                                    )
                                                },
                                            )

                                        elem.clear()
                                await pipe.execute()

        except zipfile.BadZipFile:
            log.error("Bad zip file in launchbox metadata update")
            return

        log.info("Scheduled launchbox metadata update completed!")


update_launchbox_metadata_task = UpdateLaunchboxMetadataTask()
