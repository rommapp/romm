"""Pure unit tests for the shared ROM visibility rule (no DB needed)."""

from tests.sql_dialects import MARIADB_DIALECT, compile_sql

from handler.auth.permissions import ResolvedPermissions
from handler.auth.rom_visibility import UNRESTRICTED, RomVisibilityFilter
from models.rom import RomFacets, RomVisibility


def _perms(*, is_admin: bool) -> ResolvedPermissions:
    return ResolvedPermissions(
        is_admin=is_admin,
        user_id=1,
        grants=frozenset(),
        hidden_platform_ids=frozenset({5}),
        hidden_rom_ids=frozenset({99}),
    )


def test_unrestricted_adds_no_clauses():
    assert UNRESTRICTED.is_unrestricted
    assert UNRESTRICTED.clauses() == []
    assert UNRESTRICTED.allows(RomVisibility(id=99, platform_id=5, min_age=None))


def test_hides_by_platform_and_by_rom():
    visibility = RomVisibilityFilter(
        hidden_platform_ids=frozenset({5}), hidden_rom_ids=frozenset({99})
    )

    assert not visibility.is_unrestricted
    assert not visibility.allows(RomVisibility(id=1, platform_id=5, min_age=None))
    assert not visibility.allows(RomVisibility(id=99, platform_id=6, min_age=None))
    assert visibility.allows(RomVisibility(id=1, platform_id=6, min_age=None))


def test_clauses_filter_the_given_columns():
    visibility = RomVisibilityFilter(
        hidden_platform_ids=frozenset({5}), hidden_rom_ids=frozenset({99})
    )

    clauses = visibility.clauses(
        platform_id_col=RomFacets.platform_id, rom_id_col=RomFacets.rom_id
    )

    assert [compile_sql(c, MARIADB_DIALECT) for c in clauses] == [
        "(roms_facets.platform_id NOT IN (__[POSTCOMPILE_platform_id_1]))",
        "(roms_facets.rom_id NOT IN (__[POSTCOMPILE_rom_id_1]))",
    ]


def test_row_hidden_clause_matches_the_rows_its_rules_keep_out():
    visibility = RomVisibilityFilter(
        hidden_platform_ids=frozenset({5}), hidden_rom_ids=frozenset({99})
    )

    row_hidden = visibility.row_hidden_clause()

    assert row_hidden is not None
    assert compile_sql(row_hidden, MARIADB_DIALECT) == (
        "roms.platform_id IN (__[POSTCOMPILE_platform_id_1])"
    )


def test_direct_hides_alone_need_no_row_clause():
    assert (
        RomVisibilityFilter(hidden_rom_ids=frozenset({99})).row_hidden_clause() is None
    )
    assert UNRESTRICTED.row_hidden_clause() is None


def test_admin_permissions_are_unrestricted():
    assert _perms(is_admin=True).rom_visibility is UNRESTRICTED


def test_user_permissions_carry_their_hides():
    perms = _perms(is_admin=False)

    assert perms.rom_visibility == RomVisibilityFilter(
        hidden_platform_ids=frozenset({5}), hidden_rom_ids=frozenset({99})
    )
    assert not perms.can_see_rom(RomVisibility(id=99, platform_id=6, min_age=None))


def _rom(rom_id: int, min_age: int | None, platform_id: int = 1) -> RomVisibility:
    return RomVisibility(id=rom_id, platform_id=platform_id, min_age=min_age)


def test_an_age_limit_hides_roms_rated_above_it():
    visibility = RomVisibilityFilter(age_limit=12)

    assert not visibility.is_unrestricted
    assert visibility.allows(_rom(1, 12))
    assert not visibility.allows(_rom(2, 17))
    # Unrated ROMs stay visible unless asked otherwise.
    assert visibility.allows(_rom(3, None))


def test_hide_unrated_hides_roms_no_rating_covers():
    with_limit = RomVisibilityFilter(age_limit=12, hide_unrated_roms=True)
    alone = RomVisibilityFilter(hide_unrated_roms=True)

    assert not with_limit.allows(_rom(1, None))
    assert with_limit.allows(_rom(2, 3))
    assert not alone.allows(_rom(1, None))
    assert alone.allows(_rom(2, 18))


def test_the_age_clause_compiles_per_setting():
    def sql(visibility: RomVisibilityFilter) -> list[str]:
        return [compile_sql(c, MARIADB_DIALECT) for c in visibility.clauses()]

    assert sql(RomVisibilityFilter(age_limit=12)) == [
        "roms.min_age IS NULL OR roms.min_age <= :min_age_1"
    ]
    assert sql(RomVisibilityFilter(age_limit=12, hide_unrated_roms=True)) == [
        "roms.min_age IS NOT NULL AND roms.min_age <= :min_age_1"
    ]
    assert sql(RomVisibilityFilter(hide_unrated_roms=True)) == [
        "roms.min_age IS NOT NULL"
    ]


def test_the_age_rule_reads_the_facets_mirror_when_asked():
    clauses = RomVisibilityFilter(age_limit=12, hidden_rom_ids=frozenset({7})).clauses(
        platform_id_col=RomFacets.platform_id,
        rom_id_col=RomFacets.rom_id,
        min_age_col=RomFacets.min_age,
    )

    assert [compile_sql(c, MARIADB_DIALECT) for c in clauses] == [
        "roms_facets.min_age IS NULL OR roms_facets.min_age <= :min_age_1",
        "(roms_facets.rom_id NOT IN (__[POSTCOMPILE_rom_id_1]))",
    ]


def test_user_permissions_carry_their_age_settings():
    perms = ResolvedPermissions(
        is_admin=False,
        user_id=1,
        grants=frozenset(),
        hidden_platform_ids=frozenset(),
        hidden_rom_ids=frozenset(),
        age_limit=10,
        hide_unrated_roms=True,
    )

    assert perms.rom_visibility == RomVisibilityFilter(
        age_limit=10, hide_unrated_roms=True
    )
    assert perms.can_see_rom(_rom(4, 10))
    assert not perms.can_see_rom(_rom(5, 13))
