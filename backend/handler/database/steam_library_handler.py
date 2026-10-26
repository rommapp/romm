from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from models.platform import Platform
from models.rom import Rom
from models.steam_library import SteamLibraryEntry
from utils.database import is_non_blank

from .base_handler import DBBaseHandler, affected_rows

# Keeps each IN list well under every database's bound-parameter limit.
STEAM_ID_CHUNK_SIZE = 1000


class DBSteamLibraryHandler(DBBaseHandler):
    @begin_session
    def get_rom_ids_by_steam_app_id(
        self,
        platform_slugs: Sequence[str],
        steam_app_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> dict[int, int]:
        """The rom that stands for each Steam app on the given platforms.

        A rom with a file wins over a store-only one, then the oldest row.
        """
        rows: list[tuple[int | None, int, str | None]] = []
        ids = list(steam_app_ids)
        for start in range(0, len(ids), STEAM_ID_CHUNK_SIZE):
            rows.extend(
                (app_id, rom_id, storefront)
                for app_id, rom_id, storefront in session.execute(
                    select(Rom.steam_id, Rom.id, Rom.storefront)
                    .join(Platform, Platform.id == Rom.platform_id)
                    .where(
                        Platform.slug.in_(platform_slugs),
                        Rom.steam_id.in_(ids[start : start + STEAM_ID_CHUNK_SIZE]),
                    )
                ).all()
            )

        rom_ids: dict[int, int] = {}
        for app_id, rom_id, _ in sorted(
            rows, key=lambda row: (row[2] is not None, row[1])
        ):
            if app_id is not None:
                rom_ids.setdefault(app_id, rom_id)
        return rom_ids

    @begin_session
    def get_unmatched_store_only_rom_ids(
        self, rom_ids: Sequence[int], session: Session = INJECTED_SESSION
    ) -> list[int]:
        """The store-only roms among `rom_ids` that no metadata source matched yet."""
        # Their Steam id is set at creation, so the cover a match fills in tells instead.
        ids = list(rom_ids)
        unmatched: list[int] = []
        for start in range(0, len(ids), STEAM_ID_CHUNK_SIZE):
            unmatched.extend(
                session.scalars(
                    select(Rom.id).where(
                        Rom.id.in_(ids[start : start + STEAM_ID_CHUNK_SIZE]),
                        Rom.storefront.is_not(None),
                        ~is_non_blank(Rom.url_cover),
                    )
                ).all()
            )
        return unmatched

    @begin_session
    def get_entries(
        self, user_id: int, session: Session = INJECTED_SESSION
    ) -> Sequence[SteamLibraryEntry]:
        return session.scalars(
            select(SteamLibraryEntry).where(SteamLibraryEntry.user_id == user_id)
        ).all()

    @begin_session
    def replace_entries(
        self,
        user_id: int,
        entries: Sequence[SteamLibraryEntry],
        session: Session = INJECTED_SESSION,
    ) -> int:
        """Make `entries` the user's whole Steam library.

        Returns:
            How many entries were removed because the game is no longer owned.
        """
        existing = {
            entry.steam_app_id: entry
            for entry in session.scalars(
                select(SteamLibraryEntry).where(SteamLibraryEntry.user_id == user_id)
            ).all()
        }
        owned = {entry.steam_app_id for entry in entries}

        dropped = [app_id for app_id in existing if app_id not in owned]
        for start in range(0, len(dropped), STEAM_ID_CHUNK_SIZE):
            session.execute(
                delete(SteamLibraryEntry).where(
                    SteamLibraryEntry.user_id == user_id,
                    SteamLibraryEntry.steam_app_id.in_(
                        dropped[start : start + STEAM_ID_CHUNK_SIZE]
                    ),
                )
            )

        for entry in entries:
            current = existing.get(entry.steam_app_id)
            if current is None:
                entry.user_id = user_id
                session.add(entry)
                continue
            current.rom_id = entry.rom_id
            current.playtime_minutes = entry.playtime_minutes
            current.last_played_at = entry.last_played_at

        return len(dropped)

    @begin_session
    def delete_entries(self, user_id: int, session: Session = INJECTED_SESSION) -> int:
        return affected_rows(
            session.execute(
                delete(SteamLibraryEntry).where(SteamLibraryEntry.user_id == user_id)
            )
        )
