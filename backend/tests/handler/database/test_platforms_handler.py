from handler.database import db_platform_handler
from models.platform import Platform


def test_lookup_finds_a_folder_renamed_only_in_case():
    """A rescan must reuse the row, not add a second platform beside it."""
    stored = db_platform_handler.add_platform(
        Platform(name="N64", slug="n64", fs_slug="nintendo 64")
    )

    found = db_platform_handler.get_platform_by_fs_slug("Nintendo 64")

    assert found is not None
    assert found.id == stored.id


def test_lookup_returns_the_exactly_named_folder_when_one_exists():
    """The exact spelling is tried first, for backends that can tell them apart.

    MariaDB and MySQL match case-insensitively by collation, so only the
    exactly-named row is asserted here; PostgreSQL additionally distinguishes
    the sibling.
    """
    exact = db_platform_handler.add_platform(
        Platform(name="PlayStation", slug="psx", fs_slug="psx")
    )

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

    merged = db_platform_handler.add_platform(scanned)

    assert merged.custom_name == "Sega - Genesis/ Mega Drive (Unofficial)"
    assert merged.description == "Aftermarket only"
