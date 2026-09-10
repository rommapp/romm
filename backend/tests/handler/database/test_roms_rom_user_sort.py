"""Ordering the gallery by a per-user `rom_user` field.

Sorting must keep every rom in the results and the count, with NULL sort
keys (no `rom_user` row, or an unset field) last in both directions.
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


def _set_user_props(rom: Rom, user: User, props: dict[str, object]) -> None:
    rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)
    db_rom_handler.update_rom_user(rom_user.id, props)


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
        # The user restriction lives only in the join's ON clause; repeating
        # it in the WHERE would turn the join into an inner one.
        assert sql.count("rom_user.user_id") == 1
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


class TestRomUserSortResults:
    @pytest.fixture
    def rated_library(self, admin_user: User, platform: Platform) -> None:
        _set_user_props(_make_rom(platform, "low"), admin_user, {"rating": 2})
        _set_user_props(_make_rom(platform, "high"), admin_user, {"rating": 9})
        _make_rom(platform, "untouched")

    @pytest.fixture
    def played_library(self, admin_user: User, platform: Platform) -> None:
        _set_user_props(
            _make_rom(platform, "recent"),
            admin_user,
            {"last_played": datetime(2024, 6, 1, tzinfo=timezone.utc)},
        )
        _set_user_props(
            _make_rom(platform, "older"),
            admin_user,
            {"last_played": datetime(2020, 1, 1, tzinfo=timezone.utc)},
        )
        _make_rom(platform, "never_played")

    @pytest.mark.parametrize(
        ("order_dir", "expected"),
        [
            ("asc", ["older", "recent", "never_played"]),
            ("desc", ["recent", "older", "never_played"]),
        ],
    )
    def test_last_played_keeps_unplayed_roms_last(
        self,
        admin_user: User,
        played_library: None,
        order_dir: str,
        expected: list[str],
    ):
        assert _ordered_names(admin_user, "last_played", order_dir) == expected

    def test_rating_ascending_keeps_unrated_roms_last(
        self, admin_user: User, rated_library: None
    ):
        assert _ordered_names(admin_user, "rating", "asc") == [
            "low",
            "high",
            "untouched",
        ]

    def test_count_includes_roms_without_a_rom_user_row(
        self, admin_user: User, rated_library: None
    ):
        query, _ = db_rom_handler.get_roms_query(
            order_by="rating", user_id=admin_user.id
        )

        assert db_rom_handler.get_rom_count(query=query) == 3

    def test_char_index_visits_the_null_bucket_last(
        self, admin_user: User, platform: Platform
    ):
        for name in ("first_done", "second_done"):
            _set_user_props(
                _make_rom(platform, name),
                admin_user,
                {"status": RomUserStatus.FINISHED},
            )
        _make_rom(platform, "untouched")

        query, order_column = db_rom_handler.get_roms_query(
            order_by="status", user_id=admin_user.id
        )

        # The status-less rom sorts last, so it must not shift the offsets.
        assert db_rom_handler.with_char_index(query, order_column) == [("F", 0)]
