"""Ordering the gallery by a per-user `rom_user` field.

Sorting on one must keep every rom in the results and in the count, with the
unset keys last in both directions. Rating, difficulty and completion default
to 0 in an existing row, which renders as unset and sorts as unset.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import mysql

from handler.database import db_rom_handler
from handler.database.rom_filters import RomFilterParams
from models.platform import Platform
from models.rom import Rom, RomUser, RomUserStatus
from models.user import User


def _make_rom(
    platform: Platform,
    name: str,
    *,
    region: str | None = None,
    igdb_id: int | None = None,
) -> Rom:
    full_name = f"{name} ({region})" if region else name
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
            regions=[region] if region else [],
        )
    )


def _set_rom_user_fields(rom: Rom, user: User, fields: dict[str, object]) -> None:
    rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)
    db_rom_handler.update_rom_user(rom_user.id, fields)


def _ordered_names(
    user: User, order_by: str, order_dir: str, *, attr: str = "name", **kwargs: object
) -> list[str]:
    return [
        getattr(rom, attr)
        for rom in db_rom_handler.get_roms_scalar(
            order_by=order_by, order_dir=order_dir, user_id=user.id, **kwargs
        )
    ]


class TestRomUserSortQueryShape:
    def test_sort_keeps_the_outer_join(self):
        query, sort_key = db_rom_handler.get_roms_query(
            order_by="last_played", user_id=1
        )
        sql = str(query)

        assert "LEFT OUTER JOIN rom_user" in sql
        # The user restriction belongs in the join's ON clause; in the WHERE it
        # would turn the join into an inner one and drop untouched roms.
        assert "rom_user.user_id" not in str(query.whereclause or "")
        assert sort_key.column is RomUser.last_played

    # The dialect matrix for the shared NULL-placement block lives in
    # test_roms_metadata_sort.py; this pins the rom_user branch's shape.
    def test_zero_default_columns_fold_zero_into_the_null_bucket(
        self, mariadb_driver: None
    ):
        query, sort_key = db_rom_handler.get_roms_query(order_by="rating", user_id=1)

        # NULLIF turns the 0 default into a NULL sort key, so a touched but
        # unset rom lands in the same trailing bucket as an untouched one.
        assert (
            "ORDER BY nullif(rom_user.rating, :nullif_1) IS NULL, "
            "nullif(rom_user.rating, :nullif_1) ASC"
        ) in str(query)
        assert sort_key.column is RomUser.rating

    @pytest.mark.parametrize(
        "order_by", ["metadatum", "rom_users", "rom", "user", "__table__"]
    )
    @pytest.mark.parametrize("user_id", [None, 1])
    def test_non_column_order_by_falls_back_to_the_name_sort(
        self, order_by: str, user_id: int | None
    ):
        # A relationship or dunder name is not a sortable column; it must
        # resolve to the name sort instead of raising while ordering builds.
        query, sort_key = db_rom_handler.get_roms_query(
            order_by=order_by, user_id=user_id
        )

        assert sort_key.column is Rom.name_sort_key
        assert "ORDER BY roms.name_sort_key ASC" in str(query)


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

    # Ties inside the unset bucket follow the rom id in the sort direction.
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
    def test_char_index_skips_non_lexical_sorts(self, admin_user: User, order_by: str):
        query, sort_key = db_rom_handler.get_roms_query(
            order_by=order_by, user_id=admin_user.id
        )

        # Offsets into a non-lexical order (a date, or an enum the database
        # orders by declaration) would hand the alpha strip wrong targets.
        assert db_rom_handler.with_char_index(query, sort_key.column) == []


def _grouped_names(user: User, platform: Platform, order_dir: str) -> list[str]:
    return _ordered_names(
        user,
        "last_played",
        order_dir,
        attr="fs_name_no_ext",
        platform_ids=[platform.id],
        group_by_meta_id=True,
    )


class TestGroupedRomUserSortResults:
    """Grouped galleries sort each group by its best sibling's key (#4447)."""

    @pytest.fixture
    def grouped_library(self, admin_user: User, platform: Platform) -> None:
        # Sonic: the USA rom is the representative (region rank), but only the
        # Japan sibling was played, most recently of all.
        _make_rom(platform, "Sonic", region="USA", igdb_id=100)
        _set_rom_user_fields(
            _make_rom(platform, "Sonic", region="Japan", igdb_id=100),
            admin_user,
            {"last_played": datetime(2025, 6, 1, tzinfo=timezone.utc)},
        )
        # Tails: a played group of one.
        _set_rom_user_fields(
            _make_rom(platform, "Tails", region="USA", igdb_id=200),
            admin_user,
            {"last_played": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        )
        # Knuckles: every sibling untouched.
        _make_rom(platform, "Knuckles", region="USA", igdb_id=300)
        _make_rom(platform, "Knuckles", region="Japan", igdb_id=300)

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

    def test_hidden_sibling_does_not_drive_the_group(
        self, admin_user: User, platform: Platform, grouped_library: None
    ):
        # The newest play in the library belongs to a hidden Knuckles sibling,
        # so its group must stay in the NULL tail.
        _set_rom_user_fields(
            _make_rom(platform, "Knuckles", region="Europe", igdb_id=300),
            admin_user,
            {"last_played": datetime(2026, 1, 1, tzinfo=timezone.utc), "hidden": True},
        )

        assert _grouped_names(admin_user, platform, "desc") == [
            "Sonic (USA)",
            "Tails (USA)",
            "Knuckles (USA)",
        ]

    def test_permission_hidden_sibling_does_not_drive_the_group(
        self, admin_user: User, platform: Platform, grouped_library: None
    ):
        # The newest play belongs to a sibling an admin hid from this user, so
        # it can neither represent its group nor drive the group's key.
        admin_hidden = _make_rom(platform, "Knuckles", region="Europe", igdb_id=300)
        _set_rom_user_fields(
            admin_hidden,
            admin_user,
            {"last_played": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        )

        query, _ = db_rom_handler.get_roms_query(
            order_by="last_played", order_dir="desc", user_id=admin_user.id
        )
        grouped = db_rom_handler.filter_roms(
            filters=RomFilterParams(platform_ids=[platform.id], group_by_meta_id=True),
            query=query,
            order_by="last_played",
            order_dir="desc",
            user_id=admin_user.id,
            hidden_rom_ids=[admin_hidden.id],
        )
        by_id = {
            rom.id: rom.fs_name_no_ext
            for rom in db_rom_handler.get_roms_scalar(user_id=admin_user.id)
        }

        assert [
            by_id[rom_id] for rom_id in db_rom_handler.get_rom_id_index(query=grouped)
        ] == [
            "Sonic (USA)",
            "Tails (USA)",
            "Knuckles (USA)",
        ]

    def test_grouped_id_index_follows_the_group_order(
        self, admin_user: User, platform: Platform, grouped_library: None
    ):
        query, _ = db_rom_handler.get_roms_query(
            order_by="last_played", order_dir="desc", user_id=admin_user.id
        )
        grouped = db_rom_handler.filter_roms(
            filters=RomFilterParams(platform_ids=[platform.id], group_by_meta_id=True),
            query=query,
            order_by="last_played",
            order_dir="desc",
            user_id=admin_user.id,
        )

        ids = db_rom_handler.get_rom_id_index(query=grouped)
        by_id = {
            rom.id: rom.fs_name_no_ext
            for rom in db_rom_handler.get_roms_scalar(user_id=admin_user.id)
        }

        assert [by_id[rom_id] for rom_id in ids] == [
            "Sonic (USA)",
            "Tails (USA)",
            "Knuckles (USA)",
        ]

    def test_ungrouped_sort_still_ranks_each_rom_by_its_own_key(
        self, admin_user: User, platform: Platform, grouped_library: None
    ):
        names = _ordered_names(
            admin_user,
            "last_played",
            "desc",
            attr="fs_name_no_ext",
            platform_ids=[platform.id],
        )

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
            filters=RomFilterParams(platform_ids=[platform.id], group_by_meta_id=True),
            query=query,
            order_by="last_played",
            order_dir="desc",
            user_id=admin_user.id,
        )

        assert db_rom_handler.get_rom_count(query=grouped) == 3


class TestGroupedRomUserSortQueryShape:
    def _grouped_query(self, order_by: str, order_dir: str = "desc"):
        query, _ = db_rom_handler.get_roms_query(
            order_by=order_by, order_dir=order_dir, user_id=1
        )
        return db_rom_handler.filter_roms(
            filters=RomFilterParams(group_by_meta_id=True),
            query=query,
            order_by=order_by,
            order_dir=order_dir,
            user_id=1,
        )

    def _grouped_sql(self, order_by: str, order_dir: str = "desc") -> str:
        return str(self._grouped_query(order_by, order_dir))

    @pytest.mark.parametrize(
        ("order_dir", "aggregate"), [("desc", "max"), ("asc", "min")]
    )
    def test_group_key_aggregates_with_the_sort_direction(
        self, mariadb_driver: None, order_dir: str, aggregate: str
    ):
        sql = self._grouped_sql("last_played", order_dir)
        direction = order_dir.upper()

        # Hidden siblings are masked to NULL so they cannot drive the group.
        assert (
            f"{aggregate}(CASE WHEN (rom_user.hidden IS false OR "
            "rom_user.hidden IS NULL) THEN rom_user.last_played END) OVER"
        ) in sql
        # The aggregate reuses row_number's window spec (one sort pass), with a
        # whole-partition frame so it still covers every sibling.
        assert "ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING" in sql
        # NULLs-last carries over from the ungrouped sort: ascending needs the
        # leading IS NULL term, DESC already places NULLs last on MariaDB.
        assert ("group_sort_value IS NULL" in sql) == (order_dir == "asc")
        assert f"group_sort_value {direction}, roms.id {direction}" in sql

    def test_group_key_join_stays_outer(self):
        # Compiled for MariaDB, where the null-safe <=> is what stops the
        # optimizer from converting the join to inner and re-planning.
        sql = str(self._grouped_query("last_played").compile(dialect=mysql.dialect()))

        assert "LEFT OUTER JOIN (SELECT" in sql
        assert "<=> roms.id" in sql

    @pytest.mark.parametrize(
        ("order_by", "order_clause"),
        [
            ("name", "ORDER BY roms.name_sort_key DESC, roms.id DESC"),
            ("status", "ORDER BY rom_user.status DESC, roms.id DESC"),
        ],
    )
    def test_lexical_and_enum_sorts_keep_the_representative_key(
        self, mariadb_driver: None, order_by: str, order_clause: str
    ):
        sql = self._grouped_sql(order_by)

        # MIN/MAX diverge from ORDER BY semantics for enums, and a lexical
        # group key would disagree with the representative's displayed label.
        assert "group_sort_value" not in sql
        assert "IN (SELECT" in sql
        assert order_clause in sql
