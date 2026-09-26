"""The `verified` filter over the Hasheous signature-match flags and RA hash match.

`hasheous_metadata` is a JSON blob whose keys grow as RomM maps more of
Hasheous' signature sources (`mame_redump_match` was the latest addition), so
rows written before a key existed simply don't carry it. Extracting a missing
key yields NULL, and an OR chain containing a NULL is NULL rather than false,
which makes `NOT (...)` NULL too: the unverified side would drop every row it
should have returned.

A coalesce folds that NULL to false on every engine. The suite runs against one
driver at a time, hence the compiled-SQL check below.
"""

import pytest

from handler.database import db_rom_handler
from handler.database.rom_filters import RomFilterParams
from models.platform import Platform
from models.rom import Rom
from models.user import User
from tests.sql_dialects import POSTGRESQL_DIALECT, compile_sql

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


def _add_rom(
    platform: Platform,
    user: User,
    name: str,
    metadata: dict,
    ra_metadata: dict | None = None,
) -> Rom:
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
            ra_metadata=ra_metadata,
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


@pytest.fixture
def ra_hash_verified_rom(platform: Platform, admin_user: User) -> Rom:
    """Hasheous flagged nothing, but the ROM's RA hash is in RA's list."""
    return _add_rom(
        platform,
        admin_user,
        "ra_hash_verified",
        {key: False for key in LEGACY_KEYS},
        ra_metadata={"achievements": [], "hash_match": True},
    )


@pytest.fixture
def ra_id_only_rom(platform: Platform, admin_user: User) -> Rom:
    """Linked to an RA game whose hash list doesn't carry this ROM's RA hash."""
    return _add_rom(
        platform,
        admin_user,
        "ra_id_only",
        {key: False for key in LEGACY_KEYS},
        ra_metadata={"achievements": [], "hash_match": False},
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

    def test_verified_includes_an_ra_hash_match(
        self,
        admin_user: User,
        ra_hash_verified_rom: Rom,
        ra_id_only_rom: Rom,
    ):
        verified = db_rom_handler.get_roms_scalar(user_id=admin_user.id, verified=True)
        unverified = db_rom_handler.get_roms_scalar(
            user_id=admin_user.id, verified=False
        )

        assert [r.id for r in verified] == [ra_hash_verified_rom.id]
        assert [r.id for r in unverified] == [ra_id_only_rom.id]


class TestVerifiedPostgresPredicate:
    @pytest.mark.parametrize("verified", [True, False])
    def test_every_key_is_coalesced_to_false(self, verified: bool):
        query, _ = db_rom_handler.get_roms_query()
        filtered = db_rom_handler.filter_roms(
            query=query, filters=RomFilterParams(verified=verified)
        )

        sql = compile_sql(filtered, POSTGRESQL_DIALECT, literal_binds=True)

        for key in [*LEGACY_KEYS, "mame_redump_match"]:
            assert (
                f"coalesce(CAST((roms.hasheous_metadata ->> '{key}') AS BOOLEAN), "
                "false)"
            ) in sql
        assert (
            "coalesce(CAST((roms.ra_metadata ->> 'hash_match') AS BOOLEAN), false)"
        ) in sql
