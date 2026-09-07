"""The `verified` filter over the Hasheous signature-match flags.

`hasheous_metadata` is a JSON blob whose keys grow as RomM maps more of
Hasheous' signature sources (`mame_redump_match` was the latest addition), so
rows written before a key existed simply don't carry it. Extracting a missing
key yields NULL, and an OR chain containing a NULL is NULL rather than false,
which makes `NOT (...)` NULL too: the unverified side would drop every row it
should have returned.

The JSON path already collapses a missing key into false (SQLAlchemy compiles
`as_boolean()` to a CASE whose ELSE branch catches it), so only the PostgreSQL
`->>` extraction needs the coalesce. The suite runs against one driver at a
time, hence the compiled-SQL check below.
"""

import pytest

from handler.database import db_rom_handler
from handler.database.roms_handler import DBRomsHandler
from models.platform import Platform
from models.rom import Rom
from models.user import User

# The keys as they were written before `mame_redump_match` joined them.
LEGACY_KEYS = [
    "tosec_match",
    "mame_arcade_match",
    "mame_mess_match",
    "nointro_match",
    "redump_match",
    "whdload_match",
    "ra_match",
    "fbneo_match",
    "puredos_match",
]


def _add_rom(platform: Platform, user: User, name: str, metadata: dict) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            hasheous_metadata=metadata,
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)
    return rom


@pytest.fixture
def legacy_unverified_rom(platform: Platform, admin_user: User) -> Rom:
    """Scanned before `mame_redump_match` existed, and matched nothing."""
    return _add_rom(
        platform,
        admin_user,
        "legacy_unverified",
        {key: False for key in LEGACY_KEYS},
    )


@pytest.fixture
def legacy_verified_rom(platform: Platform, admin_user: User) -> Rom:
    return _add_rom(
        platform,
        admin_user,
        "legacy_verified",
        {key: key == "nointro_match" for key in LEGACY_KEYS},
    )


@pytest.fixture
def chd_verified_rom(platform: Platform, admin_user: User) -> Rom:
    """Only the newest key is set, as a CHD rescan writes it."""
    return _add_rom(
        platform,
        admin_user,
        "chd_verified",
        {key: False for key in LEGACY_KEYS} | {"mame_redump_match": True},
    )


class TestVerifiedFilter:
    def test_unverified_keeps_roms_missing_the_newest_key(
        self,
        admin_user: User,
        legacy_unverified_rom: Rom,
        legacy_verified_rom: Rom,
        chd_verified_rom: Rom,
    ):
        roms = db_rom_handler.get_roms_scalar(user_id=admin_user.id, verified=False)

        assert [r.id for r in roms] == [legacy_unverified_rom.id]

    def test_verified_matches_both_legacy_and_newest_keys(
        self,
        admin_user: User,
        legacy_unverified_rom: Rom,
        legacy_verified_rom: Rom,
        chd_verified_rom: Rom,
    ):
        roms = db_rom_handler.get_roms_scalar(user_id=admin_user.id, verified=True)

        assert sorted(r.id for r in roms) == sorted(
            [legacy_verified_rom.id, chd_verified_rom.id]
        )

    def test_unverified_keeps_roms_without_any_hasheous_metadata(
        self, admin_user: User, rom: Rom, legacy_verified_rom: Rom
    ):
        roms = db_rom_handler.get_roms_scalar(user_id=admin_user.id, verified=False)

        assert [r.id for r in roms] == [rom.id]


class TestVerifiedPostgresPredicate:
    """The PostgreSQL branch builds raw SQL, so it can only be checked by
    compiling it (the suite runs on a single driver at a time)."""

    @pytest.fixture
    def postgres_handler(self, monkeypatch: pytest.MonkeyPatch) -> DBRomsHandler:
        monkeypatch.setattr(
            "handler.database.roms_handler.ROMM_DB_DRIVER", "postgresql"
        )
        return db_rom_handler

    @pytest.mark.parametrize("verified", [True, False])
    def test_every_key_is_coalesced_to_false(
        self, postgres_handler: DBRomsHandler, verified: bool
    ):
        query, _ = postgres_handler.get_roms_query()
        filtered = postgres_handler.filter_roms(query=query, verified=verified)

        sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))

        for key in [*LEGACY_KEYS, "mame_redump_match"]:
            assert f"COALESCE((hasheous_metadata->>'{key}')::boolean, false)" in sql
