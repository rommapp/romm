"""Match one arcade platform's games against the MAME index, on an admin's request."""

from itertools import batched
from typing import Any, Literal

from handler.database import db_platform_handler, db_rom_handler
from handler.metadata import meta_mame_handler
from logger.logger import log
from tasks.registry import MATCH_MAME_PLATFORM_SPEC
from tasks.scheduled import UpdateStats
from tasks.tasks import Task
from utils.arcade_platforms import MAME_SHORTNAME_PLATFORMS

MameMatchAction = Literal["match", "clear"]

BATCH_SIZE = 200


class MatchMamePlatformTask(Task):
    def __init__(self) -> None:
        super().__init__(MATCH_MAME_PLATFORM_SPEC)

    async def run(
        self,
        platform_id: int,
        action: MameMatchAction = "match",
        rename: bool = True,
    ) -> dict[str, int]:
        """Write each set's MAME match, leaving unmatched games as they were.

        Args:
            action: "match" by set name, or "clear" to drop every game's MAME data.
            rename: Name matched games after their MAME title, unless locked.
        """
        platform = db_platform_handler.get_platform(platform_id)
        if platform is None:
            raise ValueError(f"Platform {platform_id} not found")
        if platform.slug not in MAME_SHORTNAME_PLATFORMS:
            raise ValueError(f"{platform.slug} is not an arcade platform")

        rom_ids = db_rom_handler.get_rom_ids(platform_ids=[platform_id])
        stats = UpdateStats(total=len(rom_ids))
        stats.update(processed=0)
        changed = 0
        for chunk in batched(rom_ids, BATCH_SIZE, strict=False):
            for rom in db_rom_handler.get_roms_by_ids(list(chunk)):
                data: dict[str, Any]
                if action == "clear":
                    if rom.mame_id is None and not rom.mame_metadata:
                        continue
                    data = {"mame_id": None, "mame_metadata": None}
                else:
                    result = await meta_mame_handler.match_machine(rom.fs_name)
                    if result["mame_id"] is None:
                        continue
                    data = {
                        "mame_id": result["mame_id"],
                        "mame_metadata": result.get("mame_metadata"),
                    }
                    name = result.get("name")
                    if rename and name and not rom.is_field_locked("name"):
                        data["name"] = name
                db_rom_handler.update_rom(rom.id, data)
                changed += 1
            stats.update(processed=stats.processed + len(chunk))

        # The MAME filter values the gallery offers come from this cache.
        db_rom_handler.invalidate_filter_values_cache()
        log.info(
            f"{self.spec.title} of {platform.slug} ({action}): "
            f"{changed} of {len(rom_ids)} games changed"
        )
        return {"games": len(rom_ids), "changed": changed}


match_mame_platform_task = MatchMamePlatformTask()
