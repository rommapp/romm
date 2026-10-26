from typing import Any

from config import STEAM_API_KEY
from endpoints.roms import refresh_affected_smart_collections
from endpoints.sockets.scan import ScanPayload, queue_scan
from exceptions.socket_exceptions import NoScanWorkerException
from handler.database import db_steam_library_handler, db_user_handler
from handler.steam_library_handler import SteamLibraryError, sync_steam_library
from logger.logger import log
from models.user import User
from tasks.registry import SYNC_STEAM_LIBRARIES_SPEC
from tasks.tasks import PeriodicTask
from utils.context import initialize_context

from . import UpdateStats


async def _scan_unmatched_roms(rom_ids: list[int], user_id: int | None) -> None:
    try:
        await queue_scan(ScanPayload(roms_ids=rom_ids), started_by_user_id=user_id)
    except NoScanWorkerException:
        log.warning(
            f"No scan worker is running, so {len(rom_ids)} Steam games wait for "
            "the next sync to get their metadata"
        )


class SyncSteamLibrariesTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(SYNC_STEAM_LIBRARIES_SPEC)

    @initialize_context()
    async def run(self, user_id: int | None = None) -> dict[str, Any]:
        """Sync one user's Steam library, or every linked user's.

        Raises:
            SteamLibraryError: The one user asked for can't be synced.
        """
        update_stats = UpdateStats()

        if not STEAM_API_KEY:
            log.warning("STEAM_API_KEY is not set, skipping Steam library sync")
            return update_stats.to_dict()

        users: list[User]
        if user_id is None:
            users = list(db_user_handler.get_users(has_steam_id=True))
        else:
            user = db_user_handler.get_user(user_id)
            users = [user] if user is not None else []
        update_stats.update(processed=0, total=len(users))

        unmatched_rom_ids: list[int] = []
        for processed, user in enumerate(users, start=1):
            try:
                result = await sync_steam_library(user)
            except SteamLibraryError as e:
                # A sync someone asked for reports its failure to them.
                if user_id is not None:
                    raise
                log.error(f"Steam library sync failed for {user.username}: {e}")
            else:
                log.info(
                    f"Synced {user.username}'s Steam library: {result.owned} owned, "
                    f"{result.linked} already in the library, {result.created} "
                    f"added, {result.removed} no longer owned"
                )
                unmatched_rom_ids.extend(result.unmatched_rom_ids)
                refresh_affected_smart_collections(
                    db_steam_library_handler.get_rom_ids_by_app_ids(
                        result.changed_app_ids
                    ),
                    membership_only=True,
                )
            update_stats.update(processed=processed)

        if unmatched_rom_ids:
            await _scan_unmatched_roms(sorted(set(unmatched_rom_ids)), user_id)

        return update_stats.to_dict()


sync_steam_libraries_task = SyncSteamLibrariesTask()
