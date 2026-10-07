from typing import Any, cast

from adapters.services.retroachievements_types import RAUserCompletionProgressKind
from handler.database import db_rom_handler, db_user_handler
from handler.metadata import meta_ra_handler
from handler.metadata.ra_handler import RAUserProgression
from logger.logger import log
from models.rom import RomUserStatus
from models.user import User
from tasks.registry import SYNC_RETROACHIEVEMENTS_PROGRESS_SPEC
from tasks.tasks import PeriodicTask
from utils.context import initialize_context

from . import UpdateStats


def _get_rom_user_status_from_ra_award_kind(
    highest_award_kind: str | None,
) -> RomUserStatus | None:
    """Map a RetroAchievements award kind to a RomUser status.

    Returns:
        - COMPLETED_100 if the user has mastered or completed the game
        - FINISHED if the user has beaten the game (softcore or hardcore)
        - INCOMPLETE if the user has started but not yet beaten the game
        - None if the award kind is unrecognised
    """
    if highest_award_kind in (
        RAUserCompletionProgressKind.MASTERED,
        RAUserCompletionProgressKind.COMPLETED,
    ):
        return RomUserStatus.COMPLETED_100

    if highest_award_kind in (
        RAUserCompletionProgressKind.BEATEN_HARDCORE,
        RAUserCompletionProgressKind.BEATEN_SOFTCORE,
    ):
        return RomUserStatus.FINISHED

    if highest_award_kind is None:
        return RomUserStatus.INCOMPLETE

    return None


def _sync_rom_user_statuses(user: User, user_progression: RAUserProgression) -> None:
    """Update rom_user.status for each game in the user's RA progression.

    The status is always kept in sync with the user's latest RA award so that
    changes (e.g. beating a previously-incomplete game) are reflected on every
    sync run.
    """
    desired: dict[int, RomUserStatus] = {}
    for game_progression in user_progression.get("results", []):
        rom_ra_id = game_progression.get("rom_ra_id")
        if not rom_ra_id:
            continue

        new_status = _get_rom_user_status_from_ra_award_kind(
            game_progression.get("highest_award_kind")
        )
        if new_status is None:
            continue

        desired[rom_ra_id] = new_status

    if not desired:
        return

    # One `ra_id` routinely covers several regional ROM rows; each gets synced.
    roms = db_rom_handler.get_roms_by_ra_ids(list(desired))
    if not roms:
        return

    rom_users = db_rom_handler.get_rom_users_by_rom_ids(
        user.id, [rom.id for rom in roms]
    )

    for rom in roms:
        # `IN` never matches a NULL `ra_id`.
        new_status = desired[cast(int, rom.ra_id)]

        rom_user = rom_users.get(rom.id)
        if rom_user is None:
            rom_user = db_rom_handler.add_rom_user(rom.id, user.id)

        if rom_user.status == new_status:
            continue

        if rom_user.status in {RomUserStatus.RETIRED, RomUserStatus.NEVER_PLAYING}:
            continue

        db_rom_handler.update_rom_user(rom_user.id, {"status": new_status})
        log.debug(
            f"Set rom_user status to '{new_status}' for user '{user.username}' "
            f"and ROM {rom.id} (RA ID {rom.ra_id})"
        )


class SyncRetroAchievementsProgressTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(SYNC_RETROACHIEVEMENTS_PROGRESS_SPEC)

    @initialize_context()
    async def run(self) -> dict[str, Any]:
        update_stats = UpdateStats()

        if not meta_ra_handler.is_enabled():
            log.warning("RetroAchievements API is not enabled, skipping progress sync")
            return update_stats.to_dict()

        log.info("Scheduled RetroAchievements progress sync started...")

        users = db_user_handler.get_users(has_ra_username=True)
        total_users = len(users)
        processed_users = 0

        # Update initial progress
        update_stats.update(processed=processed_users, total=total_users)

        for user in users:
            try:
                user_progression = await meta_ra_handler.get_user_progression(
                    # `has_ra_username` above filters out users without one
                    cast(str, user.ra_username),
                    current_progression=cast(
                        RAUserProgression | None, user.ra_progression
                    ),
                )
                db_user_handler.update_user(
                    user.id,
                    {"ra_progression": user_progression},
                )
            except Exception as e:
                log.error(
                    f"Failed to update RetroAchievements progress for user: {user.username}, error: {e}"
                )
            else:
                log.debug(
                    f"Updated RetroAchievements progress for user: {user.username}"
                )
                # A concurrent rom_user write (e.g. a play session) can fail this
                # user's batch; the remaining users still sync.
                try:
                    _sync_rom_user_statuses(user, user_progression)
                except Exception as e:
                    log.error(
                        f"Failed to sync RetroAchievements statuses for user: {user.username}, error: {e}"
                    )

            processed_users += 1
            update_stats.update(processed=processed_users)

        log.info(
            f"Scheduled RetroAchievements progress sync done. Updated users: {len(users)}"
        )

        return update_stats.to_dict()


sync_retroachievements_progress_task = SyncRetroAchievementsProgressTask()
