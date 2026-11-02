from typing import Any, cast

from handler.database import db_rom_handler, db_user_handler
from handler.metadata import meta_steam_handler
from handler.metadata.steam_handler import (
    SteamUserProgression,
    is_steam_game_completed,
)
from logger.logger import log
from models.rom import RomUserStatus
from models.user import User
from tasks.registry import SYNC_STEAM_ACHIEVEMENTS_PROGRESS_SPEC
from tasks.tasks import PeriodicTask
from utils.context import initialize_context

from . import UpdateStats


class SteamGameDetailsPrivateError(Exception):
    """The linked profile's game details are private, so nothing can be read."""


def _sync_rom_user_statuses(user: User, user_progression: SteamUserProgression) -> None:
    """Mark each game with every achievement unlocked as completed.

    Steam has no "beaten" signal, so no other status is written.
    """
    completed = [
        game["rom_steam_id"]
        for game in user_progression.get("results", [])
        if is_steam_game_completed(game)
    ]
    statuses = {
        rom.id: RomUserStatus.COMPLETED_100
        for rom in db_rom_handler.get_roms_by_steam_ids(completed)
    }
    updated = db_rom_handler.set_rom_user_statuses(user.id, statuses)
    if updated:
        log.debug(f"Set {updated} rom_user statuses for user '{user.username}'")


async def sync_user_progress(user: User, *, incremental: bool = True) -> None:
    """Fetch a user's Steam unlocks for the library's games and store them.

    Raises:
        SteamGameDetailsPrivateError: The profile's game details are private.
    """
    user_progression = await meta_steam_handler.get_user_progression(
        cast(str, user.steam_id),
        db_rom_handler.get_steam_ids(),
        current_progression=(
            cast(SteamUserProgression | None, user.steam_progression)
            if incremental
            else None
        ),
    )
    if user_progression is None:
        raise SteamGameDetailsPrivateError(user.steam_id)

    db_user_handler.update_user(user.id, {"steam_progression": user_progression})
    log.debug(f"Updated Steam achievements progress for user: {user.username}")
    # A failed status write (e.g. a ROM deleted mid-sync) keeps the progression.
    try:
        _sync_rom_user_statuses(user, user_progression)
    except Exception as e:
        log.error(
            f"Failed to sync Steam achievement statuses for user: {user.username}, error: {e}"
        )


class SyncSteamAchievementsProgressTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(SYNC_STEAM_ACHIEVEMENTS_PROGRESS_SPEC)

    @initialize_context()
    async def run(self) -> dict[str, Any]:
        update_stats = UpdateStats()

        if not meta_steam_handler.achievements_enabled():
            log.warning("Steam achievements are not enabled, skipping progress sync")
            return update_stats.to_dict()

        log.info("Scheduled Steam achievements progress sync started...")

        users = db_user_handler.get_users(has_steam_id=True)
        update_stats.update(processed=0, total=len(users))

        for processed, user in enumerate(users, start=1):
            try:
                await sync_user_progress(user)
            except Exception as e:
                log.error(
                    f"Failed to update Steam achievements progress for user: {user.username}, error: {e}"
                )
            update_stats.update(processed=processed)

        log.info(
            f"Scheduled Steam achievements progress sync done. Updated users: {len(users)}"
        )
        return update_stats.to_dict()


sync_steam_achievements_progress_task = SyncSteamAchievementsProgressTask()
