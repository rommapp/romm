"""Ordering the gallery by a per-user `rom_user` field.

Sorting on one must keep every rom in the results and in the count, with the
unset keys last in both directions. Rating, difficulty and completion default
to 0 in an existing row, which renders as unset and sorts as unset.
"""

from datetime import datetime, timezone

import pytest

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomUser, RomUserStatus
from models.user import User


def _make_rom(platform: Platform, name: str) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )


def _set_rom_user_fields(rom: Rom, user: User, fields: dict[str, object]) -> None:
    rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)
    db_rom_handler.update_rom_user(rom_user.id, fields)


def _ordered_names(user: User, order_by: str, order_dir: str) -> list[str]:
    return [
        rom.name
        for rom in db_rom_handler.get_roms_scalar(
            order_by=order_by, order_dir=order_dir, user_id=user.id
        )
    ]


class TestRomUserSortQueryShape:
    def test_sort_keeps_the_outer_join(self):
        query, order_column = db_rom_handler.get_roms_query(
            order_by="last_played", user_id=1
        )
        sql = str(query)

        assert "LEFT OUTER JOIN rom_user" in sql
        # The user restriction belongs in the join's ON clause; in the WHERE it
        # would turn the join into an inner one and drop untouched roms.
        assert "rom_user.user_id" not in str(query.whereclause or "")
        assert order_column is RomUser.last_played

    @pytest.mark.parametrize("order_dir", ["asc", "desc"])
    def test_nulls_lead_the_order_clause(self, order_dir: str):
        query, _ = db_rom_handler.get_roms_query(
            order_by="last_played", order_dir=order_dir, user_id=1
        )

        assert (
            "ORDER BY rom_user.last_played IS NULL, "
            f"rom_user.last_played {order_dir.upper()}"
        ) in str(query)

    @pytest.mark.parametrize("order_by", ["rating", "difficulty", "completion"])
    def test_zero_default_columns_fold_zero_into_the_null_bucket(self, order_by: str):
        query, order_column = db_rom_handler.get_roms_query(
            order_by=order_by, user_id=1
        )

        # NULLIF turns the 0 default into a NULL sort key, so a touched but
        # unset rom lands in the same trailing bucket as an untouched one.
        assert (
            f"ORDER BY nullif(rom_user.{order_by}, :nullif_1) IS NULL, "
            f"nullif(rom_user.{order_by}, :nullif_1) ASC"
        ) in str(query)
        assert order_column is getattr(RomUser, order_by)


class TestRomUserSortResults:
    @pytest.fixture
    def library(self, admin_user: User, platform: Platform) -> None:
        _set_rom_user_fields(
            _make_rom(platform, "barely_touched"),
            admin_user,
            {
                "rating": 2,
                "last_played": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "status": RomUserStatus.INCOMPLETE,
            },
        )
        _set_rom_user_fields(
            _make_rom(platform, "well_loved"),
            admin_user,
            {
                "rating": 9,
                "last_played": datetime(2024, 6, 1, tzinfo=timezone.utc),
                "status": RomUserStatus.FINISHED,
            },
        )
        _make_rom(platform, "untouched")
        # Touched (the rom_user row exists) but explicitly unrated: the 0 must
        # sort with the untouched bucket, not before the real ratings.
        _set_rom_user_fields(
            _make_rom(platform, "played_unrated"),
            admin_user,
            {
                "rating": 0,
                "last_played": datetime(2022, 1, 1, tzinfo=timezone.utc),
            },
        )

    # Unset keys always trail; ties inside the unset bucket follow the rom id
    # in the sort direction (untouched was created before played_unrated).
    @pytest.mark.parametrize(
        ("order_by", "order_dir", "expected"),
        [
            (
                "last_played",
                "asc",
                ["barely_touched", "played_unrated", "well_loved", "untouched"],
            ),
            (
                "last_played",
                "desc",
                ["well_loved", "played_unrated", "barely_touched", "untouched"],
            ),
            (
                "rating",
                "asc",
                ["barely_touched", "well_loved", "untouched", "played_unrated"],
            ),
            (
                "rating",
                "desc",
                ["well_loved", "barely_touched", "played_unrated", "untouched"],
            ),
        ],
    )
    def test_unset_user_fields_sort_last(
        self,
        admin_user: User,
        library: None,
        order_by: str,
        order_dir: str,
        expected: list[str],
    ):
        assert _ordered_names(admin_user, order_by, order_dir) == expected

    def test_count_includes_roms_without_a_rom_user_row(
        self, admin_user: User, library: None
    ):
        query, _ = db_rom_handler.get_roms_query(
            order_by="rating", user_id=admin_user.id
        )

        assert db_rom_handler.get_rom_count(query=query) == 4

    @pytest.mark.parametrize("order_by", ["last_played", "status"])
    def test_char_index_skips_non_lexical_sorts(
        self, admin_user: User, library: None, order_by: str
    ):
        query, order_column = db_rom_handler.get_roms_query(
            order_by=order_by, user_id=admin_user.id
        )

        # Offsets into a non-lexical order (a date, or an enum the database
        # orders by declaration) would hand the alpha strip wrong targets.
        assert db_rom_handler.with_char_index(query, order_column) == []
