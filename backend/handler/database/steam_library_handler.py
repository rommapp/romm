from collections.abc import Collection, Sequence
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from logger.logger import log
from models.platform import Platform
from models.rom import Rom
from models.steam_library import SteamLibraryEntry
from models.user import User
from utils.database import is_non_blank

from .base_handler import DBBaseHandler

# Keeps each IN list well under every database's bound-parameter limit.
STEAM_ID_CHUNK_SIZE = 1000


class SteamLibraryChanges(NamedTuple):
    added: list[int]
    removed: list[int]


class StoreOnlyRoms(NamedTuple):
    rom_ids: dict[int, int]
    created: int


class DBSteamLibraryHandler(DBBaseHandler):
    @begin_session
    def get_rom_ids_by_steam_app_id(
        self,
        platform_slugs: Sequence[str],
        steam_app_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> dict[int, int]:
        """Each Steam app's rom on the given platforms, preferring one with a file."""
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
    def add_store_only_roms(
        self, roms: Sequence[Rom], session: Session = INJECTED_SESSION
    ) -> StoreOnlyRoms:
        """Insert store-only roms, reusing the row already at a rom's path.

        Returns:
            Each app's rom id, and how many rows were inserted.
        """
        rom_ids: dict[int, int] = {}
        created = 0
        for rom in roms:
            app_id = rom.steam_id
            if app_id is None:
                continue
            try:
                with session.begin_nested():
                    session.add(rom)
                    session.flush()
            except IntegrityError:
                existing = session.scalar(
                    select(Rom).where(
                        Rom.platform_id == rom.platform_id,
                        Rom.full_path_hash == rom.full_path_hash,
                    )
                )
                if existing is None:
                    log.warning(f"Skipping Steam app {app_id}: its rom can't be added")
                    continue
                # An unmatch or a complete rescan can clear it, and the sync
                # finds this rom by it.
                if existing.steam_id is None:
                    existing.steam_id = app_id
                rom_ids[app_id] = existing.id
                continue
            rom_ids[app_id] = rom.id
            created += 1
        return StoreOnlyRoms(rom_ids=rom_ids, created=created)

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
    def get_owned_app_ids(
        self, user_id: int, session: Session = INJECTED_SESSION
    ) -> list[int]:
        return list(
            session.scalars(
                select(SteamLibraryEntry.steam_app_id)
                .where(SteamLibraryEntry.user_id == user_id)
                .order_by(SteamLibraryEntry.steam_app_id)
            ).all()
        )

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
        steam_id: str,
        entries: Sequence[SteamLibraryEntry],
        session: Session = INJECTED_SESSION,
    ) -> SteamLibraryChanges | None:
        """Make `entries` the user's whole Steam library, if still linked to `steam_id`.

        Returns:
            The app ids newly owned and the ones no longer owned, or None when
            the user's linked account changed since `entries` were fetched.
        """
        # Locked so an unlink or relink can't commit between the check and the write.
        linked = session.scalar(
            select(User.steam_id).where(User.id == user_id).with_for_update()
        )
        if linked != steam_id:
            return None

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

        added: list[int] = []
        for entry in entries:
            current = existing.get(entry.steam_app_id)
            if current is None:
                entry.user_id = user_id
                session.add(entry)
                added.append(entry.steam_app_id)
                continue
            current.rom_id = entry.rom_id
            current.playtime_minutes = entry.playtime_minutes
            current.last_played_at = entry.last_played_at

        return SteamLibraryChanges(added=added, removed=dropped)

    @begin_session
    def delete_entries(
        self, user_id: int, session: Session = INJECTED_SESSION
    ) -> list[int]:
        """Forget the user's Steam library.

        Returns:
            The app ids it owned.
        """
        app_ids = list(
            session.scalars(
                select(SteamLibraryEntry.steam_app_id).where(
                    SteamLibraryEntry.user_id == user_id
                )
            ).all()
        )
        session.execute(
            delete(SteamLibraryEntry).where(SteamLibraryEntry.user_id == user_id)
        )
        return app_ids

    @begin_session
    def get_rom_ids_by_app_ids(
        self, steam_app_ids: Collection[int], session: Session = INJECTED_SESSION
    ) -> list[int]:
        """Every rom with one of the Steam app ids, on any platform."""
        app_ids = sorted(steam_app_ids)
        rom_ids: list[int] = []
        for start in range(0, len(app_ids), STEAM_ID_CHUNK_SIZE):
            rom_ids.extend(
                session.scalars(
                    select(Rom.id).where(
                        Rom.steam_id.in_(app_ids[start : start + STEAM_ID_CHUNK_SIZE])
                    )
                ).all()
            )
        return rom_ids
