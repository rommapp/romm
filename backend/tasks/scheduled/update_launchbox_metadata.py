import json
import zipfile
from io import BytesIO
from typing import Any, Final

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
            title="Scheduled LaunchBox metadata update",
            description="Updates the LaunchBox metadata store",
            enabled=ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
            cron_string=SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
            manual_run=True,
            func="tasks.update_launchbox_metadata.update_launchbox_metadata_task.run",
            url="https://gamesdb.launchbox-app.com/Metadata.zip",
        )

    @initialize_context()
    async def run(self, force: bool = False) -> None:
        if not LAUNCHBOX_API_ENABLED:
            log.warning("Launchbox API is not enabled, skipping metadata update")
            return None

        content = await super().run(force)
        if content is None:
            log.warning("No content received from launchbox metadata update")
            return None

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
                                current_game_images: list[dict[str, Any]] = []

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
                                        platform_elem = elem.find("Platform")
                                        if (
                                            name_elem is not None
                                            and name_elem.text
                                            and platform_elem is not None
                                            and platform_elem.text
                                        ):
                                            # Use a unique combination of name and platform as the key
                                            await pipe.hset(
                                                LAUNCHBOX_METADATA_NAME_KEY,
                                                mapping={
                                                    f"{name_elem.text}:{platform_elem.text}": json.dumps(
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

                                # Store the last game's images
                                if current_game_image_db_id is not None:
                                    await pipe.hset(
                                        LAUNCHBOX_METADATA_IMAGE_KEY,
                                        mapping={
                                            current_game_image_db_id: json.dumps(
                                                current_game_images
                                            )
                                        },
                                    )
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
            return None

        log.info("Scheduled launchbox metadata update completed!")


update_launchbox_metadata_task = UpdateLaunchboxMetadataTask()
