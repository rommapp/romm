from tests.factories import make_platform, make_rom

from handler.auth.rom_visibility import UNRESTRICTED, RomVisibilityFilter
from handler.database import db_platform_handler
from handler.database.base_handler import sync_session
from models.platform import Platform


def test_lookup_finds_a_folder_renamed_only_in_case():
    """A rescan must reuse the row, not add a second platform beside it."""
    stored = make_platform("n64", fs_slug="nintendo 64")

    found = db_platform_handler.get_platform_by_fs_slug("Nintendo 64")

    assert found is not None
    assert found.id == stored.id


def test_lookup_returns_the_exactly_named_folder_when_one_exists():
    """The exact spelling is tried first, for backends that can tell them apart.

    MariaDB and MySQL match case-insensitively by collation, so only the
    exactly-named row is asserted here; PostgreSQL additionally distinguishes
    the sibling.
    """
    exact = make_platform("psx", name="PlayStation")

    found = db_platform_handler.get_platform_by_fs_slug("psx")
    assert found is not None
    assert found.id == exact.id


def test_rescan_preserves_user_authored_fields(platform):
    """A rescan merges a freshly built Platform over the existing row.

    The scan pipeline never populates `custom_name` or `description`, so both
    must survive the merge rather than being reset to their column defaults.
    """
    db_platform_handler.update_platform(
        platform.id,
        {
            "custom_name": "Sega - Genesis/ Mega Drive (Unofficial)",
            "description": "Aftermarket only",
        },
    )

    # Mirrors endpoints/sockets/scan.py: build a platform from scan metadata,
    # graft the existing id onto it, then merge.
    scanned = Platform(
        name=platform.name,
        slug=platform.slug,
        fs_slug=platform.fs_slug,
    )
    scanned.id = platform.id

    merged = db_platform_handler.add_platform(scanned)  # noqa: TID251

    assert merged.custom_name == "Sega - Genesis/ Mega Drive (Unofficial)"
    assert merged.description == "Aftermarket only"


PEGI_18 = {"age_ratings": [{"category": "PEGI", "rating": "18"}]}


def _totals(platform):
    return platform.rom_count, platform.fs_size_bytes


def test_totals_count_only_the_roms_the_visibility_shows():
    platform_a = make_platform("platform_a")
    platform_b = make_platform("platform_b")
    make_rom(platform_a, "a1", fs_size_bytes=10)
    hidden = make_rom(platform_a, "a2", fs_size_bytes=5)
    make_rom(platform_b, "b1", fs_size_bytes=7)
    visibility = RomVisibilityFilter(hidden_rom_ids=frozenset({hidden.id}))

    listed = {
        p.id: _totals(p)
        for p in db_platform_handler.get_platforms(visibility=visibility)
    }
    detail = db_platform_handler.get_platform(platform_a.id, visibility=visibility)

    assert listed[platform_a.id] == (1, 10)
    assert listed[platform_b.id] == (1, 7)
    assert detail is not None and _totals(detail) == (1, 10)


def test_totals_leave_out_roms_above_the_age_limit():
    platform = make_platform("platform_a")
    make_rom(platform, "a1", fs_size_bytes=10)
    make_rom(platform, "a2", fs_size_bytes=5, igdb_metadata=PEGI_18)

    found = db_platform_handler.get_platform(
        platform.id, visibility=RomVisibilityFilter(age_limit=16)
    )

    assert found is not None and _totals(found) == (1, 10)


def test_a_rom_hidden_both_ways_is_left_out_once():
    platform = make_platform("platform_a")
    make_rom(platform, "a1", fs_size_bytes=10)
    hidden = make_rom(platform, "a2", fs_size_bytes=5, igdb_metadata=PEGI_18)

    found = db_platform_handler.get_platform(
        platform.id,
        visibility=RomVisibilityFilter(
            hidden_rom_ids=frozenset({hidden.id}), age_limit=16
        ),
    )

    assert found is not None and _totals(found) == (1, 10)


def test_a_shared_session_rereads_the_totals():
    platform = make_platform("platform_a")
    make_rom(platform, "a1", fs_size_bytes=10)
    hidden = make_rom(platform, "a2", fs_size_bytes=5)
    visibility = RomVisibilityFilter(hidden_rom_ids=frozenset({hidden.id}))

    reads = []
    with sync_session.begin() as session:
        # Each read returns the session's one instance, so take its totals at once.
        for read_visibility in (visibility, visibility, UNRESTRICTED):
            found = db_platform_handler.get_platform(
                platform.id, visibility=read_visibility, session=session
            )
            assert found is not None
            reads.append(_totals(found))

    assert reads == [(1, 10), (1, 10), (2, 15)]


def test_totals_are_whole_without_a_visibility():
    platform = make_platform("platform_a")
    make_rom(platform, "a1", fs_size_bytes=10)
    make_rom(platform, "a2", fs_size_bytes=5)

    found = db_platform_handler.get_platform(platform.id)

    assert found is not None and _totals(found) == (2, 15)
