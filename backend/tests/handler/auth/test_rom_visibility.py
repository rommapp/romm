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
    assert UNRESTRICTED.allows(RomVisibility(id=99, platform_id=5))


def test_hides_by_platform_and_by_rom():
    visibility = RomVisibilityFilter(
        hidden_platform_ids=frozenset({5}), hidden_rom_ids=frozenset({99})
    )

    assert not visibility.is_unrestricted
    assert not visibility.allows(RomVisibility(id=1, platform_id=5))
    assert not visibility.allows(RomVisibility(id=99, platform_id=6))
    assert visibility.allows(RomVisibility(id=1, platform_id=6))


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
    assert not perms.can_see_rom(RomVisibility(id=99, platform_id=6))
