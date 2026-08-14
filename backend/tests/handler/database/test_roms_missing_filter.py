"""The `missing_from_fs` filter and the index that serves it.

Settings -> Library Management -> Missing filters every request on
`missing_from_fs`, and both the char index and the ordered id index sort the
result by `name_sort_key`. Without a composite index over the two the database
walked the whole `roms` table, which holds every provider's raw metadata and is
multi-gigabyte on a large library (issue #3992).

An index alone is not enough: MariaDB does not treat `col IS NOT FALSE` as an
indexable predicate (EXPLAIN reports no `possible_keys` and falls back to a full
index scan plus filesort), while `col = TRUE` gets range access. The column is
`NOT NULL` since migration 0042, so the two are equivalent and the filter uses
the sargable form.
"""

import pytest
from sqlalchemy import inspect
from tests.conftest import engine

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom
from models.user import User

INDEX_COLUMNS = ["missing_from_fs", "name_sort_key"]


@pytest.fixture
def missing_rom(rom: Rom) -> Rom:
    return db_rom_handler.update_rom(rom.id, {"missing_from_fs": True})


@pytest.fixture
def present_rom(platform: Platform) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="present_rom",
            slug="present_rom",
            fs_name="present_rom.zip",
            fs_name_no_tags="present_rom",
            fs_name_no_ext="present_rom",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )


class TestMissingFromFsIndex:
    def test_migrations_create_composite_index(self):
        indexes = [
            index["column_names"] for index in inspect(engine).get_indexes("roms")
        ]

        assert INDEX_COLUMNS in indexes


class TestMissingFromFsPredicate:
    @pytest.mark.parametrize(("missing", "literal"), [(True, "true"), (False, "false")])
    def test_predicate_is_an_indexable_equality(self, missing: bool, literal: str):
        query, _ = db_rom_handler.get_roms_query()
        filtered = db_rom_handler.filter_roms(query=query, missing=missing)

        sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))

        assert f"roms.missing_from_fs = {literal}" in sql

    def test_missing_true_returns_only_missing_roms(
        self, admin_user: User, missing_rom: Rom, present_rom: Rom
    ):
        roms = db_rom_handler.get_roms_scalar(user_id=admin_user.id, missing=True)

        assert [r.id for r in roms] == [missing_rom.id]

    def test_missing_false_returns_only_present_roms(
        self, admin_user: User, missing_rom: Rom, present_rom: Rom
    ):
        roms = db_rom_handler.get_roms_scalar(user_id=admin_user.id, missing=False)

        assert [r.id for r in roms] == [present_rom.id]
