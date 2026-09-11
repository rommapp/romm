"""Ordering the gallery by a per-user `rom_user` field.

Sorting on one must keep every rom in the results and in the count, with the
unset keys last in both directions.
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


def _make_sibling(platform: Platform, name: str, region: str, igdb_id: int) -> Rom:
    full_name = f"{name} ({region})"
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            igdb_id=igdb_id,
            name=name,
            slug=full_name,
            fs_name=f"{full_name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=full_name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            regions=[region],
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

    @pytest.mark.parametrize(
        ("order_by", "order_dir", "expected"),
        [
            ("last_played", "asc", ["barely_touched", "well_loved", "untouched"]),
            ("last_played", "desc", ["well_loved", "barely_touched", "untouched"]),
            ("rating", "asc", ["barely_touched", "well_loved", "untouched"]),
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

        assert db_rom_handler.get_rom_count(query=query) == 3

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


def _grouped_names(user: User, platform: Platform, order_dir: str) -> list[str]:
    return [
        rom.fs_name_no_ext
        for rom in db_rom_handler.get_roms_scalar(
            platform_ids=[platform.id],
            order_by="last_played",
            order_dir=order_dir,
            user_id=user.id,
            group_by_meta_id=True,
        )
    ]


class TestGroupedRomUserSortResults:
    """Grouped galleries sort each group by its best sibling's key (#4447)."""

    @pytest.fixture
    def grouped_library(self, admin_user: User, platform: Platform) -> None:
        # Sonic: the USA rom is the representative (region rank), but only the
        # Japan sibling was played, most recently of all.
        _make_sibling(platform, "Sonic", "USA", igdb_id=100)
        _set_rom_user_fields(
            _make_sibling(platform, "Sonic", "Japan", igdb_id=100),
            admin_user,
            {"last_played": datetime(2025, 6, 1, tzinfo=timezone.utc)},
        )
        # Tails: a played group of one.
        _set_rom_user_fields(
            _make_sibling(platform, "Tails", "USA", igdb_id=200),
            admin_user,
            {"last_played": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        )
        # Knuckles: every sibling untouched.
        _make_sibling(platform, "Knuckles", "USA", igdb_id=300)
        _make_sibling(platform, "Knuckles", "Japan", igdb_id=300)

    @pytest.mark.parametrize(
        ("order_dir", "expected"),
        [
            # The Japan sibling's play surfaces Sonic first, while the USA rom
            # stays the displayed representative.
            ("desc", ["Sonic (USA)", "Tails (USA)", "Knuckles (USA)"]),
            # Ascending takes each group's earliest non-NULL key; the fully
            # unplayed group stays in the NULL tail in both directions.
            ("asc", ["Tails (USA)", "Sonic (USA)", "Knuckles (USA)"]),
        ],
    )
    def test_group_sorts_by_its_best_sibling(
        self,
        admin_user: User,
        platform: Platform,
        grouped_library: None,
        order_dir: str,
        expected: list[str],
    ):
        assert _grouped_names(admin_user, platform, order_dir) == expected

    def test_ungrouped_sort_still_ranks_each_rom_by_its_own_key(
        self, admin_user: User, platform: Platform, grouped_library: None
    ):
        names = [
            rom.fs_name_no_ext
            for rom in db_rom_handler.get_roms_scalar(
                platform_ids=[platform.id],
                order_by="last_played",
                order_dir="desc",
                user_id=admin_user.id,
            )
        ]

        assert names == [
            "Sonic (Japan)",
            "Tails (USA)",
            "Knuckles (Japan)",
            "Knuckles (USA)",
            "Sonic (USA)",
        ]

    def test_grouped_count_spans_all_groups(
        self, admin_user: User, platform: Platform, grouped_library: None
    ):
        query, _ = db_rom_handler.get_roms_query(
            order_by="last_played", order_dir="desc", user_id=admin_user.id
        )
        grouped = db_rom_handler.filter_roms(
            query=query,
            order_by="last_played",
            order_dir="desc",
            platform_ids=[platform.id],
            group_by_meta_id=True,
            user_id=admin_user.id,
        )

        assert db_rom_handler.get_rom_count(query=grouped) == 3


class TestGroupedRomUserSortQueryShape:
    def _grouped_sql(self, order_by: str, order_dir: str = "desc") -> str:
        query, _ = db_rom_handler.get_roms_query(
            order_by=order_by, order_dir=order_dir, user_id=1
        )
        return str(
            db_rom_handler.filter_roms(
                query=query,
                order_by=order_by,
                order_dir=order_dir,
                group_by_meta_id=True,
                user_id=1,
            )
        )

    @pytest.mark.parametrize(
        ("order_dir", "aggregate"), [("desc", "max"), ("asc", "min")]
    )
    def test_group_key_aggregates_with_the_sort_direction(
        self, order_dir: str, aggregate: str
    ):
        sql = self._grouped_sql("last_played", order_dir)
        direction = order_dir.upper()

        assert f"{aggregate}(rom_user.last_played) OVER" in sql
        # NULLs-last emission carries over from the ungrouped rom_user sort.
        assert (
            "ORDER BY anon_1.group_sort_value IS NULL, "
            f"anon_1.group_sort_value {direction}, roms.id {direction}"
        ) in sql

    def test_group_key_join_stays_outer(self):
        sql = self._grouped_sql("last_played")

        # Made inner, MariaDB drives from the derived table and probes the
        # wide roms rows once per group instead of leading with an index.
        assert "LEFT OUTER JOIN (SELECT" in sql
        assert "IS NOT DISTINCT FROM roms.id" in sql

    @pytest.mark.parametrize("order_by", ["name", "status"])
    def test_lexical_and_enum_sorts_keep_the_representative_key(self, order_by: str):
        sql = self._grouped_sql(order_by)

        # MIN/MAX diverge from ORDER BY semantics for enums, and a lexical
        # group key would disagree with the representative's displayed label.
        assert "group_sort_value" not in sql
        assert "IN (SELECT" in sql
